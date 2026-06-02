import { useEffect, useState } from 'react'
import { projectsApi } from '../../api/projects'
import { api } from '../../api/client'
import type { ProjectMember, User } from '../../types'
import { useAuthStore } from '../../stores/authStore'

interface Props { projectId: string }

export default function MembersTab({ projectId }: Props) {
  const [members, setMembers] = useState<ProjectMember[]>([])
  const [allUsers, setAllUsers] = useState<User[]>([])
  const [showAdd, setShowAdd] = useState(false)
  const [selectedUserId, setSelectedUserId] = useState('')
  const [role, setRole] = useState('member')
  const [adding, setAdding] = useState(false)
  const currentUser = useAuthStore((s) => s.user)

  const load = async () => {
    const res = await projectsApi.listMembers(projectId)
    setMembers(res.data)
  }

  useEffect(() => {
    load()
    api.get<User[]>('/users/').then((r) => setAllUsers(r.data))
  }, [projectId])

  const existingIds = new Set(members.map((m) => m.user.id))
  const availableUsers = allUsers.filter((u) => !existingIds.has(u.id))

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!selectedUserId) return
    setAdding(true)
    try {
      await projectsApi.addMember(projectId, selectedUserId, role)
      setSelectedUserId(''); setShowAdd(false)
      await load()
    } finally {
      setAdding(false)
    }
  }

  const handleRemove = async (userId: string) => {
    if (!confirm('確定移除此成員？')) return
    await projectsApi.removeMember(projectId, userId)
    await load()
  }

  const isAdmin = currentUser?.role === 'admin'

  return (
    <div>
      <div className="flex justify-end mb-4">
        {isAdmin && <button onClick={() => setShowAdd(true)} className="btn-primary">+ 新增成員</button>}
      </div>

      {showAdd && (
        <form onSubmit={handleAdd} className="card mb-4 flex gap-3 items-end">
          <div className="flex-1">
            <label className="block text-sm font-medium text-gray-700 mb-1">選擇用戶</label>
            <select className="input" value={selectedUserId} onChange={(e) => setSelectedUserId(e.target.value)} required>
              <option value="">請選擇…</option>
              {availableUsers.map((u) => (
                <option key={u.id} value={u.id}>{u.display_name} ({u.email})</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">角色</label>
            <select className="input" value={role} onChange={(e) => setRole(e.target.value)}>
              <option value="viewer">訪客</option>
              <option value="member">成員</option>
              <option value="manager">管理者</option>
            </select>
          </div>
          <button type="submit" disabled={adding} className="btn-primary">{adding ? '新增中…' : '新增'}</button>
          <button type="button" onClick={() => setShowAdd(false)} className="btn-secondary">取消</button>
        </form>
      )}

      <div className="space-y-2">
        {members.map((m) => (
          <div key={m.id} className="card flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-full bg-primary-500 text-white flex items-center justify-center font-medium">
                {m.user.display_name.charAt(0)}
              </div>
              <div>
                <p className="font-medium text-gray-900">{m.user.display_name}</p>
                <p className="text-xs text-gray-400">{m.user.email}</p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <span className="text-xs bg-gray-100 text-gray-600 px-3 py-1 rounded-full capitalize">{m.role}</span>
              {isAdmin && m.role !== 'owner' && (
                <button onClick={() => handleRemove(m.user.id)} className="text-xs text-red-400 hover:text-red-600">移除</button>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
