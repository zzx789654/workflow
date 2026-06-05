import { useEffect, useState } from 'react'
import { projectsApi } from '../../api/projects'
import { toast } from '../../stores/toastStore'
import { api } from '../../api/client'
import type { ProjectMember, User, ProjectRole } from '../../types'
import { useAuthStore } from '../../stores/authStore'

interface Props { projectId: string }

const ROLE_LABELS: Record<string, string> = {
  owner: '擁有者', manager: '管理者', member: '成員', viewer: '檢視者',
}
const ROLE_COLORS: Record<string, string> = {
  owner:   'bg-purple-100 text-purple-700',
  manager: 'bg-blue-100 text-blue-600',
  member:  'bg-gray-100 text-gray-600',
  viewer:  'bg-green-50 text-green-600',
}

export default function MembersTab({ projectId }: Props) {
  const [members, setMembers] = useState<ProjectMember[]>([])
  const [allUsers, setAllUsers] = useState<User[]>([])
  const [showAdd, setShowAdd] = useState(false)
  const [selectedUserId, setSelectedUserId] = useState('')
  const [newRole, setNewRole] = useState<ProjectRole>('member')
  const [adding, setAdding] = useState(false)
  const [updatingId, setUpdatingId] = useState<string | null>(null)
  const currentUser = useAuthStore((s) => s.user)

  const load = async () => {
    const res = await projectsApi.listMembers(projectId)
    setMembers(res.data)
  }

  useEffect(() => {
    load()
    api.get<User[]>('/users/').then((r) => setAllUsers(r.data))
  }, [projectId])

  // 目前登入者在此專案的角色
  const myMembership = members.find(m => m.user.id === currentUser?.id)
  const myProjectRole = currentUser?.role === 'admin' ? 'owner' : (myMembership?.role ?? 'viewer')
  const canManage = myProjectRole === 'owner' || myProjectRole === 'manager'

  const existingIds = new Set(members.map((m) => m.user.id))
  const availableUsers = allUsers.filter((u) => !existingIds.has(u.id))

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!selectedUserId) return
    setAdding(true)
    try {
      await projectsApi.addMember(projectId, selectedUserId, newRole)
      setSelectedUserId(''); setShowAdd(false)
      await load()
    } finally { setAdding(false) }
  }

  const handleRoleChange = async (userId: string, role: ProjectRole) => {
    setUpdatingId(userId)
    try {
      await api.patch(`/projects/${projectId}/members/${userId}/role?role=${role}`)
      await load()
    } catch (err: any) {
      toast.error(err?.response?.data?.detail ?? '更新失敗')
    } finally { setUpdatingId(null) }
  }

  const handleRemove = async (userId: string, memberRole: string) => {
    if (memberRole === 'owner') { toast.error('無法移除專案擁有者'); return }
    if (!confirm('確定移除此成員？')) return
    await projectsApi.removeMember(projectId, userId)
    await load()
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div>
          <p className="text-xs text-gray-400">
            你在此專案的角色：
            <span className={`ml-1 text-xs px-2 py-0.5 rounded-full font-medium ${ROLE_COLORS[myProjectRole]}`}>
              {ROLE_LABELS[myProjectRole]}
            </span>
          </p>
        </div>
        {canManage && (
          <button onClick={() => setShowAdd(true)} className="btn-primary text-sm">+ 新增成員</button>
        )}
      </div>

      {showAdd && (
        <form onSubmit={handleAdd} className="card mb-4 flex gap-3 items-end flex-wrap">
          <div className="flex-1 min-w-40">
            <label className="block text-sm font-medium text-gray-700 mb-1">選擇用戶</label>
            <select className="input w-full" value={selectedUserId} onChange={e => setSelectedUserId(e.target.value)} required>
              <option value="">請選擇…</option>
              {availableUsers.map(u => (
                <option key={u.id} value={u.id}>{u.display_name} ({u.email})</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">專案角色</label>
            <select className="input" value={newRole} onChange={e => setNewRole(e.target.value as ProjectRole)}>
              <option value="viewer">檢視者</option>
              <option value="member">成員</option>
              <option value="manager">管理者</option>
            </select>
          </div>
          <button type="submit" disabled={adding} className="btn-primary">{adding ? '新增中…' : '新增'}</button>
          <button type="button" onClick={() => setShowAdd(false)} className="btn-secondary">取消</button>
        </form>
      )}

      {/* 角色說明 */}
      <div className="mb-4 p-3 bg-gray-50 rounded-xl text-xs text-gray-500 grid grid-cols-2 sm:grid-cols-4 gap-2">
        {[
          { role: 'owner',   desc: '完整控制、轉讓專案' },
          { role: 'manager', desc: '管理成員、任務、設定' },
          { role: 'member',  desc: '建立/修改任務' },
          { role: 'viewer',  desc: '唯讀，無法修改' },
        ].map(({ role, desc }) => (
          <div key={role} className="flex items-start gap-1.5">
            <span className={`text-xs px-1.5 py-0.5 rounded-full flex-shrink-0 ${ROLE_COLORS[role]}`}>{ROLE_LABELS[role]}</span>
            <span>{desc}</span>
          </div>
        ))}
      </div>

      <div className="space-y-2">
        {members.map(m => (
          <div key={m.id} className="card flex items-center justify-between gap-3">
            <div className="flex items-center gap-3 flex-1 min-w-0">
              <div className="w-9 h-9 rounded-full bg-primary-500 text-white flex items-center justify-center font-medium flex-shrink-0">
                {m.user.display_name.charAt(0).toUpperCase()}
              </div>
              <div className="min-w-0">
                <p className="font-medium text-gray-900 truncate">{m.user.display_name}</p>
                <p className="text-xs text-gray-400 truncate">{m.user.email}</p>
              </div>
            </div>

            <div className="flex items-center gap-2 flex-shrink-0">
              {/* owner 不可修改角色；自己不能改自己；manager 可改 member/viewer */}
              {canManage && m.role !== 'owner' && m.user.id !== currentUser?.id ? (
                <select
                  className="text-xs border border-gray-200 rounded-lg px-2 py-1 disabled:opacity-50"
                  value={m.role}
                  disabled={updatingId === m.user.id}
                  onChange={e => handleRoleChange(m.user.id, e.target.value as ProjectRole)}
                >
                  <option value="viewer">檢視者</option>
                  <option value="member">成員</option>
                  <option value="manager">管理者</option>
                </select>
              ) : (
                <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${ROLE_COLORS[m.role]}`}>
                  {ROLE_LABELS[m.role]}
                </span>
              )}

              {canManage && m.role !== 'owner' && m.user.id !== currentUser?.id && (
                <button
                  onClick={() => handleRemove(m.user.id, m.role)}
                  className="text-xs text-red-400 hover:text-red-600"
                >
                  移除
                </button>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
