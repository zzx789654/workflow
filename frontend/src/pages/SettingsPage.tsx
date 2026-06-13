import { useEffect, useState } from 'react'
import { useAuthStore } from '../stores/authStore'
import { useThemeStore, PALETTES, FX_OPTIONS, MODE_OPTIONS } from '../stores/themeStore'
import { authApi } from '../api/auth'
import { orgApi } from '../api/org'
import { usersApi as usersApiClient } from '../api/users'
import { confirm } from '../stores/confirmStore'
import type { User, OrgUnit, CalendarGrant } from '../types'

// ── API helpers ───────────────────────────────────────────────
import { api } from '../api/client'

const usersApi = {
  list: () => api.get<User[]>('/users/'),
  updateRole: (userId: string, role: string) =>
    api.patch<User>(`/users/${userId}/role?role=${role}`),
  deactivate: (userId: string) =>
    api.delete(`/users/${userId}`),
  updateMe: (data: { display_name?: string; avatar_url?: string; email?: string }) =>
    api.patch<User>('/users/me', data),
  changePassword: (oldPw: string, newPw: string) =>
    api.post('/auth/change-password', { old_password: oldPw, new_password: newPw }),
}

type Tab = 'profile' | 'appearance' | 'users' | 'org' | 'system' | 'system_config'

const ROLE_LABELS: Record<string, string> = { admin: '管理員', member: '一般成員', viewer: '一般成員' }
const ROLE_COLORS: Record<string, string> = {
  admin: 'bg-red-100 text-red-600',
  member: 'bg-blue-100 text-blue-600',
  viewer: 'bg-gray-100 text-gray-500',
}

// ── 個人資料 Tab ───────────────────────────────────────────────
function ProfileTab() {
  const user = useAuthStore(s => s.user)
  const fetchMe = useAuthStore(s => s.fetchMe)
  const [displayName, setDisplayName] = useState(user?.display_name ?? '')
  const [email, setEmail] = useState(user?.email ?? '')
  const [saving, setSaving] = useState(false)
  const [oldPw, setOldPw] = useState('')
  const [newPw, setNewPw] = useState('')
  const [pwMsg, setPwMsg] = useState('')
  const [pwSaving, setPwSaving] = useState(false)

  // 遠端帳號（ldap/radius）的 Email 由目錄服務管理，本地無法修改
  const isLocal = user?.auth_source === 'local'

  const handleSaveProfile = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    try {
      const payload: { display_name: string; email?: string } = { display_name: displayName }
      if (isLocal) payload.email = email || undefined
      await usersApi.updateMe(payload)
      await fetchMe()
    } finally { setSaving(false) }
  }

  const handleChangePw = async (e: React.FormEvent) => {
    e.preventDefault()
    if (newPw.length < 8) { setPwMsg('新密碼至少 8 碼'); return }
    setPwSaving(true); setPwMsg('')
    try {
      await usersApi.changePassword(oldPw, newPw)
      setPwMsg('密碼已更新'); setOldPw(''); setNewPw('')
    } catch (err: any) {
      setPwMsg(err?.response?.data?.detail ?? '更新失敗')
    } finally { setPwSaving(false) }
  }

  return (
    <div className="max-w-md space-y-6">
      <div>
        <h3 className="text-sm font-semibold text-gray-700 mb-3">個人資料</h3>
        <form onSubmit={handleSaveProfile} className="space-y-3">
          <div>
            <label className="text-xs text-gray-500 block mb-1">帳號</label>
            <input className="input w-full bg-gray-50" value={user?.username ?? ''} disabled />
          </div>
          <div>
            <label className="text-xs text-gray-500 block mb-1">顯示名稱</label>
            <input className="input w-full" value={displayName}
              onChange={e => setDisplayName(e.target.value)} required />
          </div>
          <div>
            <label className="text-xs text-gray-500 block mb-1">
              Email{!isLocal && <span className="text-gray-400">（由目錄服務管理，無法修改）</span>}
            </label>
            <input
              className={`input w-full ${isLocal ? '' : 'bg-gray-50'}`}
              type="email"
              value={isLocal ? email : (user?.email ?? '')}
              onChange={e => setEmail(e.target.value)}
              disabled={!isLocal}
              placeholder={isLocal ? '選填' : ''}
            />
          </div>
          <div>
            <label className="text-xs text-gray-500 block mb-1">系統角色</label>
            <span className={`text-xs px-2 py-1 rounded-full font-medium ${ROLE_COLORS[user?.role ?? 'member']}`}>
              {ROLE_LABELS[user?.role ?? 'member']}
            </span>
          </div>
          <button type="submit" disabled={saving} className="btn-primary text-sm">
            {saving ? '儲存中…' : '儲存個人資料'}
          </button>
        </form>
      </div>

      <div className="border-t border-gray-100 pt-5">
        <h3 className="text-sm font-semibold text-gray-700 mb-3">變更密碼</h3>
        <form onSubmit={handleChangePw} className="space-y-3">
          <div>
            <label className="text-xs text-gray-500 block mb-1">目前密碼</label>
            <input type="password" className="input w-full" value={oldPw}
              onChange={e => setOldPw(e.target.value)} required />
          </div>
          <div>
            <label className="text-xs text-gray-500 block mb-1">新密碼（至少 8 碼）</label>
            <input type="password" className="input w-full" value={newPw}
              onChange={e => setNewPw(e.target.value)} required />
          </div>
          {pwMsg && <p className={`text-sm ${pwMsg.includes('更新') ? 'text-green-600' : 'text-red-500'}`}>{pwMsg}</p>}
          <button type="submit" disabled={pwSaving} className="btn-secondary text-sm">
            {pwSaving ? '更新中…' : '更新密碼'}
          </button>
        </form>
      </div>
    </div>
  )
}

// ── 外觀 / 個人化 Tab（所有人可用）────────────────────────────
function AppearanceTab() {
  const { palette, mode, fx, motion, setPalette, setMode, setFx, setMotion, reset } = useThemeStore()

  return (
    <div className="max-w-xl space-y-7">
      {/* 配色主題 */}
      <section>
        <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-200 mb-1">配色主題</h3>
        <p className="text-xs text-gray-400 mb-3">變更品牌主色，狀態色（成功/警告/危險）維持不變。</p>
        <div className="grid grid-cols-5 gap-3">
          {PALETTES.map(p => (
            <button
              key={p.id}
              onClick={() => setPalette(p.id)}
              className={`flex flex-col items-center gap-1.5 p-2 rounded-xl border transition-all ${
                palette === p.id
                  ? 'border-primary-400 bg-primary-50 dark:bg-primary-500/10'
                  : 'border-gray-200 dark:border-gray-700 hover:border-gray-300'
              }`}
            >
              <span className="w-8 h-8 rounded-full shadow-inner" style={{ backgroundColor: p.swatch }} />
              <span className="text-xs text-gray-600 dark:text-gray-300">{p.label}</span>
            </button>
          ))}
        </div>
      </section>

      {/* 明暗模式 */}
      <section>
        <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-200 mb-3">明暗模式</h3>
        <div className="inline-flex rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
          {MODE_OPTIONS.map(m => (
            <button
              key={m.id}
              onClick={() => setMode(m.id)}
              className={`px-4 py-2 text-sm transition-colors ${
                mode === m.id
                  ? 'bg-primary-600 text-white'
                  : 'text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800'
              }`}
            >
              {m.label}
            </button>
          ))}
        </div>
      </section>

      {/* 視覺特效 */}
      <section>
        <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-200 mb-1">視覺特效</h3>
        <p className="text-xs text-gray-400 mb-3">改變卡片與面板的質感，不影響任何排版與按鈕位置。</p>
        <div className="grid grid-cols-3 gap-3">
          {FX_OPTIONS.map(f => (
            <button
              key={f.id}
              onClick={() => setFx(f.id)}
              className={`text-left p-3 rounded-xl border transition-all ${
                fx === f.id
                  ? 'border-primary-400 bg-primary-50 dark:bg-primary-500/10'
                  : 'border-gray-200 dark:border-gray-700 hover:border-gray-300'
              }`}
            >
              <p className="text-sm font-medium text-gray-800 dark:text-gray-100">{f.label}</p>
              <p className="text-xs text-gray-400 mt-0.5">{f.desc}</p>
            </button>
          ))}
        </div>
      </section>

      {/* 動效 */}
      <section>
        <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-200 mb-3">介面動效</h3>
        <label className="flex items-center gap-3 cursor-pointer select-none">
          <input
            type="checkbox"
            checked={motion}
            onChange={e => setMotion(e.target.checked)}
            className="w-4 h-4 accent-primary-600"
          />
          <span className="text-sm text-gray-600 dark:text-gray-300">
            啟用進場與互動動效
            <span className="text-xs text-gray-400 block">關閉後將尊重系統的「減少動態效果」設定</span>
          </span>
        </label>
      </section>

      <div className="border-t border-gray-100 dark:border-gray-800 pt-4">
        <button onClick={reset} className="btn-secondary text-sm">重設為預設外觀</button>
      </div>
    </div>
  )
}

// ── 使用者組織歸屬 / 日曆授權編輯（展開列，Admin only）──────────
function UserOrgEditor({ user, units, onChanged }: { user: User; units: OrgUnit[]; onChanged: () => void }) {
  const [position, setPosition] = useState(user.position ?? '')
  const [grants, setGrants] = useState<CalendarGrant[]>([])
  const [grantUnit, setGrantUnit] = useState('')
  const [msg, setMsg] = useState('')

  // 縮排組樹供下拉
  const treeOptions = (() => {
    const byParent: Record<string, OrgUnit[]> = {}
    for (const u of units) (byParent[u.parent_id ?? 'root'] ??= []).push(u)
    const out: { unit: OrgUnit; depth: number }[] = []
    const walk = (p: string, d: number) => {
      for (const u of (byParent[p] ?? []).sort((a, b) => a.name.localeCompare(b.name, 'zh-Hant'))) {
        out.push({ unit: u, depth: d }); walk(u.id, d + 1)
      }
    }
    walk('root', 0)
    return out
  })()
  const unitName = (id: string) => units.find(u => u.id === id)?.name ?? id

  const loadGrants = async () => {
    const r = await usersApiClient.listGrants(user.id)
    setGrants(r.data)
  }
  useEffect(() => { loadGrants() }, [user.id])

  const saveUnit = async (orgUnitId: string) => {
    setMsg('')
    try {
      await usersApiClient.updateOrg(user.id, { set_org_unit: true, org_unit_id: orgUnitId || null })
      onChanged()
    } catch (err: any) { setMsg(err?.response?.data?.detail ?? '更新失敗') }
  }
  const savePosition = async () => {
    setMsg('')
    try {
      await usersApiClient.updateOrg(user.id, { set_position: true, position: position.trim() || null })
      onChanged()
    } catch (err: any) { setMsg(err?.response?.data?.detail ?? '更新失敗') }
  }
  const addGrant = async () => {
    if (!grantUnit) return
    try { await usersApiClient.addGrant(user.id, grantUnit); setGrantUnit(''); loadGrants() }
    catch (err: any) { setMsg(err?.response?.data?.detail ?? '授權失敗') }
  }
  const removeGrant = async (g: CalendarGrant) => {
    await usersApiClient.removeGrant(user.id, g.id); loadGrants()
  }

  return (
    <div className="mt-2 ml-12 mr-2 p-3 bg-gray-50 rounded-xl space-y-3 text-sm">
      <div className="grid grid-cols-[80px_1fr] gap-2 items-center">
        <label className="text-xs text-gray-500">部門 / 課別</label>
        <select className="input text-sm" value={user.org_unit_id ?? ''} onChange={e => saveUnit(e.target.value)}>
          <option value="">（未指派）</option>
          {treeOptions.map(({ unit, depth }) => (
            <option key={unit.id} value={unit.id}>{'　'.repeat(depth)}{unit.name}</option>
          ))}
        </select>
        <label className="text-xs text-gray-500">職位</label>
        <div className="flex gap-2">
          <input className="input text-sm flex-1" value={position} placeholder="例：資深工程師"
            onChange={e => setPosition(e.target.value)} onBlur={savePosition} />
        </div>
      </div>

      <div>
        <p className="text-xs text-gray-500 mb-1.5">額外日曆授權（可檢視這些單位含子樹的日常作業）</p>
        <div className="flex gap-2 flex-wrap mb-2">
          {grants.length === 0 && <span className="text-xs text-gray-400">無額外授權</span>}
          {grants.map(g => (
            <span key={g.id} className="text-xs bg-white border border-gray-200 rounded-full px-2 py-0.5 flex items-center gap-1">
              {unitName(g.org_unit_id)}
              <button onClick={() => removeGrant(g)} className="text-red-400 hover:text-red-600">×</button>
            </span>
          ))}
        </div>
        <div className="flex gap-2">
          <select className="input text-sm flex-1" value={grantUnit} onChange={e => setGrantUnit(e.target.value)}>
            <option value="">選擇要授權的單位…</option>
            {treeOptions.map(({ unit, depth }) => (
              <option key={unit.id} value={unit.id}>{'　'.repeat(depth)}{unit.name}</option>
            ))}
          </select>
          <button className="btn-secondary text-sm" onClick={addGrant} disabled={!grantUnit}>授權</button>
        </div>
      </div>
      {msg && <p className="text-red-500 text-xs">{msg}</p>}
    </div>
  )
}

// ── 使用者管理 Tab（Admin only）────────────────────────────────
function UsersTab() {
  const me = useAuthStore(s => s.user)
  const [users, setUsers] = useState<User[]>([])
  const [units, setUnits] = useState<OrgUnit[]>([])
  const [loading, setLoading] = useState(true)
  const [updatingId, setUpdatingId] = useState<string | null>(null)
  const [expandedId, setExpandedId] = useState<string | null>(null)

  const load = async () => {
    setLoading(true)
    try {
      const [r, o] = await Promise.all([usersApi.list(), orgApi.list()])
      setUsers(r.data)
      setUnits(o.data)
    } finally { setLoading(false) }
  }
  useEffect(() => { load() }, [])

  const handleRoleChange = async (userId: string, role: string) => {
    setUpdatingId(userId)
    try { await usersApi.updateRole(userId, role); load() }
    finally { setUpdatingId(null) }
  }

  const handleDeactivate = async (userId: string, name: string) => {
    if (!(await confirm({ title: '停用帳號', message: `確定停用帳號「${name}」？`, confirmLabel: '停用', danger: true }))) return
    await usersApi.deactivate(userId)
    load()
  }

  const unitName = (id: string | null) => units.find(u => u.id === id)?.name ?? null

  if (loading) return <div className="text-gray-400 py-8 text-center">載入中…</div>

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-gray-700">使用者管理</h3>
        <span className="text-xs text-gray-400">{users.length} 位使用者</span>
      </div>
      <div className="space-y-2">
        {users.map(u => (
          <div key={u.id}>
            <div className="flex items-center gap-3 p-3 bg-white border border-gray-100 rounded-xl">
              <div className="w-9 h-9 rounded-full bg-primary-500 text-white flex items-center justify-center font-medium flex-shrink-0">
                {u.display_name.charAt(0).toUpperCase()}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-gray-900 truncate">{u.display_name}</p>
                <p className="text-xs text-gray-400 truncate">
                  {[unitName(u.org_unit_id), u.position, u.email].filter(Boolean).join(' · ') || '—'}
                </p>
              </div>
              <div className="flex items-center gap-2 flex-shrink-0">
                {me?.role === 'admin' ? (
                  <>
                    <button
                      onClick={() => setExpandedId(expandedId === u.id ? null : u.id)}
                      className="text-xs text-primary-600 hover:text-primary-700"
                    >{expandedId === u.id ? '收合' : '編輯歸屬'}</button>
                    {u.id !== me?.id && (
                      <>
                        <select
                          className="text-xs border border-gray-200 rounded px-2 py-1"
                          value={u.role}
                          disabled={updatingId === u.id}
                          onChange={e => handleRoleChange(u.id, e.target.value)}
                        >
                          <option value="admin">管理員</option>
                          <option value="member">一般成員</option>
                        </select>
                        <button
                          onClick={() => handleDeactivate(u.id, u.display_name)}
                          className="text-xs text-red-400 hover:text-red-600"
                        >停用</button>
                      </>
                    )}
                  </>
                ) : (
                  <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${ROLE_COLORS[u.role]}`}>
                    {ROLE_LABELS[u.role]}
                  </span>
                )}
              </div>
            </div>
            {expandedId === u.id && me?.role === 'admin' && (
              <UserOrgEditor user={u} units={units} onChanged={load} />
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

// ── 組織管理 Tab（Admin only）──────────────────────────────────
// 以縮排呈現組織樹（部門 > 課別 > …），可新增/改名/設上層/指派主管/刪除。
function OrgTab() {
  const [units, setUnits] = useState<OrgUnit[]>([])
  const [users, setUsers] = useState<User[]>([])
  const [loading, setLoading] = useState(true)
  const [newName, setNewName] = useState('')
  const [newParent, setNewParent] = useState('')
  const [msg, setMsg] = useState('')
  const [syncing, setSyncing] = useState(false)
  const [syncMsg, setSyncMsg] = useState('')

  const load = async () => {
    setLoading(true)
    try {
      const [u, us] = await Promise.all([orgApi.list(), usersApiClient.list()])
      setUnits(u.data)
      setUsers(us.data)
    } finally { setLoading(false) }
  }
  useEffect(() => { load() }, [])

  const userName = (id: string | null) => users.find(u => u.id === id)?.display_name ?? '—'

  // 依 parent_id 組樹，回傳 [unit, depth] 的深度優先序列
  const tree = (() => {
    const byParent: Record<string, OrgUnit[]> = {}
    for (const u of units) {
      const k = u.parent_id ?? 'root'
      ;(byParent[k] ??= []).push(u)
    }
    const out: { unit: OrgUnit; depth: number }[] = []
    const walk = (parent: string, depth: number) => {
      for (const u of (byParent[parent] ?? []).sort((a, b) => a.name.localeCompare(b.name, 'zh-Hant'))) {
        out.push({ unit: u, depth })
        walk(u.id, depth + 1)
      }
    }
    walk('root', 0)
    return out
  })()

  const handleCreate = async () => {
    if (!newName.trim()) return
    setMsg('')
    try {
      await orgApi.create({ name: newName.trim(), parent_id: newParent || null })
      setNewName(''); setNewParent('')
      load()
    } catch (err: any) { setMsg(err?.response?.data?.detail ?? '建立失敗') }
  }

  const handleRename = async (u: OrgUnit) => {
    const name = prompt('單位名稱', u.name)
    if (name == null || !name.trim() || name === u.name) return
    try { await orgApi.update(u.id, { name: name.trim() }); load() }
    catch (err: any) { setMsg(err?.response?.data?.detail ?? '更新失敗') }
  }

  const handleSetParent = async (u: OrgUnit, parentId: string) => {
    setMsg('')
    try { await orgApi.update(u.id, { parent_id: parentId || null }); load() }
    catch (err: any) { setMsg(err?.response?.data?.detail ?? '更新失敗') }
  }

  const handleSetManager = async (u: OrgUnit, managerId: string) => {
    try { await orgApi.update(u.id, { manager_user_id: managerId || null }); load() }
    catch (err: any) { setMsg(err?.response?.data?.detail ?? '更新失敗') }
  }

  const handleDelete = async (u: OrgUnit) => {
    if (!(await confirm({ title: '刪除單位', message: `刪除單位「${u.name}」？子單位將升為頂層、所屬成員脫離單位（不會刪除成員）。`, confirmLabel: '刪除', danger: true }))) return
    try { await orgApi.remove(u.id); load() }
    catch (err: any) { setMsg(err?.response?.data?.detail ?? '刪除失敗') }
  }

  const handleSyncAd = async () => {
    setSyncing(true); setSyncMsg('')
    try {
      const r = await orgApi.syncAd()
      setSyncMsg(r.data.message)
      load()
    } catch (err: any) {
      setSyncMsg(err?.response?.data?.detail ?? '同步失敗')
    } finally { setSyncing(false) }
  }

  if (loading) return <div className="text-gray-400 py-8 text-center">載入中…</div>

  return (
    <div className="max-w-3xl">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-gray-700">組織架構（部門 / 課別）</h3>
        <span className="text-xs text-gray-400">{units.length} 個單位</span>
      </div>

      {/* AD 同步：手動建立與 AD 同步並行，AD 同步只碰 AD 來源的單位 */}
      <div className="flex items-center gap-3 mb-4 bg-blue-50 border border-blue-100 rounded-xl p-3">
        <div className="flex-1">
          <p className="text-sm font-medium text-blue-800">從 AD/LDAP 同步組織樹</p>
          <p className="text-xs text-blue-500">依 AD 的 OU 階層展開；只新增/更新 AD 來源單位，不影響手動建立的。需先在「系統設定」啟用 LDAP。</p>
        </div>
        <button className="btn-secondary text-sm whitespace-nowrap" onClick={handleSyncAd} disabled={syncing}>
          {syncing ? '同步中…' : '立即同步 AD'}
        </button>
      </div>
      {syncMsg && <p className="text-sm text-blue-600 mb-3">{syncMsg}</p>}

      {/* 新增單位 */}
      <div className="flex gap-2 mb-4 flex-wrap items-end bg-gray-50 rounded-xl p-3">
        <div>
          <label className="text-xs text-gray-500 block mb-1">新單位名稱</label>
          <input className="input text-sm w-44" value={newName} placeholder="例：工程部 / 後端課"
            onChange={e => setNewName(e.target.value)} />
        </div>
        <div>
          <label className="text-xs text-gray-500 block mb-1">上層單位</label>
          <select className="input text-sm w-40" value={newParent} onChange={e => setNewParent(e.target.value)}>
            <option value="">（頂層）</option>
            {tree.map(({ unit, depth }) => (
              <option key={unit.id} value={unit.id}>{'　'.repeat(depth)}{unit.name}</option>
            ))}
          </select>
        </div>
        <button className="btn-primary text-sm" onClick={handleCreate}>新增</button>
      </div>
      {msg && <p className="text-sm text-red-500 mb-3">{msg}</p>}

      {/* 組織樹 */}
      <div className="space-y-1.5">
        {tree.length === 0 && <p className="text-sm text-gray-400">尚無組織單位</p>}
        {tree.map(({ unit, depth }) => {
          const isAd = unit.source === 'ad'
          return (
          <div key={unit.id} className={`flex items-center gap-2 p-2.5 border rounded-xl ${
            unit.is_active ? 'bg-white border-gray-100' : 'bg-gray-50 border-gray-100 opacity-60'
          }`}
            style={{ marginLeft: depth * 20 }}>
            <span className="text-gray-300">{depth > 0 ? '└' : '▪'}</span>
            {isAd ? (
              <span className="text-sm font-medium text-gray-800" title="AD 來源，名稱由同步管理">{unit.name}</span>
            ) : (
              <button className="text-sm font-medium text-gray-800 hover:text-primary-600" onClick={() => handleRename(unit)}
                title="點擊改名">{unit.name}</button>
            )}
            {isAd && <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-blue-100 text-blue-600">AD</span>}
            {!unit.is_active && <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-gray-200 text-gray-500">已停用</span>}
            <div className="flex items-center gap-2 ml-auto flex-wrap">
              {/* AD 單位的層級由同步維護，這裡只開放「指派主管」（本地概念，不寫回 AD） */}
              {!isAd && (
                <select className="text-xs border border-gray-200 rounded px-1.5 py-1"
                  value={unit.parent_id ?? ''} onChange={e => handleSetParent(unit, e.target.value)} title="上層單位">
                  <option value="">（頂層）</option>
                  {tree.filter(t => t.unit.id !== unit.id && t.unit.source !== 'ad').map(({ unit: o, depth: d }) => (
                    <option key={o.id} value={o.id}>{'　'.repeat(d)}{o.name}</option>
                  ))}
                </select>
              )}
              <select className="text-xs border border-gray-200 rounded px-1.5 py-1"
                value={unit.manager_user_id ?? ''} onChange={e => handleSetManager(unit, e.target.value)} title="主管">
                <option value="">（未設主管）</option>
                {users.map(u => <option key={u.id} value={u.id}>主管：{u.display_name}</option>)}
              </select>
              {!isAd && (
                <button onClick={() => handleDelete(unit)} className="text-xs text-red-400 hover:text-red-600">刪除</button>
              )}
            </div>
          </div>
          )
        })}
      </div>
      <p className="text-xs text-gray-400 mt-3">
        主管（manager）自動可在月曆「堆疊團隊」檢視其所管單位（含子單位）成員的日常作業；
        指派主管：在上方下拉選 {userName(null)} 以外的成員即可。
      </p>
    </div>
  )
}

// ── 系統資訊 Tab ───────────────────────────────────────────────
function SystemTab() {
  return (
    <div className="max-w-md space-y-4">
      <h3 className="text-sm font-semibold text-gray-700">系統資訊</h3>
      <div className="space-y-2">
        {[
          ['系統版本', 'WorkFlow v3.0-P1'],
          ['後端框架', 'FastAPI 0.115 + Python 3.12'],
          ['資料庫', 'PostgreSQL 16'],
          ['快取', 'Redis 7'],
          ['前端框架', 'React 18 + Vite + TailwindCSS'],
        ].map(([k, v]) => (
          <div key={k} className="flex items-center gap-4 p-3 bg-gray-50 rounded-xl">
            <span className="text-xs text-gray-500 w-28 flex-shrink-0">{k}</span>
            <span className="text-sm text-gray-800 font-medium">{v}</span>
          </div>
        ))}
      </div>

      <div className="border-t border-gray-100 pt-4">
        <h3 className="text-sm font-semibold text-gray-700 mb-3">MCP Server</h3>
        <div className="bg-gray-900 rounded-xl p-4 text-xs text-green-400 font-mono space-y-1">
          <p># stdio 模式（本地 AI）</p>
          <p>claude mcp add workflow -- python mcp_server.py</p>
          <p className="mt-2 text-gray-500"># HTTP 模式（網頁 AI）</p>
          <p>python mcp_server.py --transport http --port 8765</p>
        </div>
      </div>
    </div>
  )
}

// ── 系統設定 Tab（Admin only）─────────────────────────────────
const systemSettingsApi = {
  list: () => api.get<{ key: string; value: string; is_secret: boolean }[]>('/system-settings/'),
  update: (settings: Record<string, string>) =>
    api.put('/system-settings/', { settings }),
  testLdap: (username: string, password: string) =>
    api.post('/system-settings/test-ldap', { username, password }),
  testRadius: (username: string, password: string) =>
    api.post('/system-settings/test-radius', { username, password }),
  getTlsCert: () => api.get<TlsCertInfo>('/system-settings/tls-cert'),
  uploadTlsCert: (cert: string, key: string) =>
    api.post<TlsCertInfo>('/system-settings/tls-cert', { cert, key }),
}

type TlsCertInfo = {
  configured?: boolean
  ok?: boolean
  subject_cn?: string
  issuer_cn?: string
  not_before?: string
  not_after?: string
  is_self_signed?: boolean
  is_expired?: boolean
}

type SettingRow = { key: string; value: string; is_secret: boolean }

const SETTING_LABELS: Record<string, string> = {
  auth_backend: '認證方式',
  site_name: '站台名稱',
  allow_registration: '開放自行註冊',
  session_timeout_minutes: 'Session 逾時（分鐘）',
  ldap_host: 'LDAP/AD 主機',
  ldap_port: 'LDAP 連接埠',
  ldap_use_ssl: '使用 LDAPS（SSL）',
  ldap_use_tls: '使用 StartTLS',
  ldap_bind_dn: 'Bind DN（服務帳號）',
  ldap_bind_password: 'Bind 密碼',
  ldap_search_base: '搜尋基礎（Search Base）',
  ldap_search_filter: '搜尋過濾條件',
  ldap_display_name_attr: '顯示名稱屬性',
  ldap_email_attr: 'Email 屬性',
  radius_host: 'RADIUS 主機',
  radius_port: 'RADIUS 連接埠',
  radius_secret: 'Shared Secret',
  radius_timeout: '連線逾時（秒）',
}

const GENERAL_KEYS = ['site_name', 'allow_registration', 'session_timeout_minutes', 'auth_backend']
const LDAP_KEYS = [
  'ldap_host', 'ldap_port', 'ldap_use_ssl', 'ldap_use_tls',
  'ldap_bind_dn', 'ldap_bind_password', 'ldap_search_base',
  'ldap_search_filter', 'ldap_display_name_attr', 'ldap_email_attr',
]
const RADIUS_KEYS = ['radius_host', 'radius_port', 'radius_secret', 'radius_timeout']

function SystemConfigTab() {
  const [settings, setSettings] = useState<Record<string, SettingRow>>({})
  const [draft, setDraft] = useState<Record<string, string>>({})
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [saveMsg, setSaveMsg] = useState('')
  const [testUser, setTestUser] = useState('')
  const [testPw, setTestPw] = useState('')
  const [testResult, setTestResult] = useState('')
  const [testing, setTesting] = useState(false)

  const load = async () => {
    setLoading(true)
    try {
      const r = await systemSettingsApi.list()
      const map: Record<string, SettingRow> = {}
      for (const row of r.data) map[row.key] = row
      setSettings(map)
      const d: Record<string, string> = {}
      for (const row of r.data) d[row.key] = row.value
      setDraft(d)
    } finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])

  const set = (key: string, value: string) => setDraft(p => ({ ...p, [key]: value }))

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true); setSaveMsg('')
    try {
      await systemSettingsApi.update(draft)
      setSaveMsg('儲存成功')
      await load()
    } catch (err: any) {
      setSaveMsg(err?.response?.data?.detail ?? '儲存失敗')
    } finally { setSaving(false) }
  }

  const handleTest = async () => {
    const backend = draft['auth_backend'] ?? 'local'
    if (backend === 'local') { setTestResult('目前為本地認證，無需測試遠端連線'); return }
    setTesting(true); setTestResult('')
    try {
      if (backend === 'ldap') {
        const r = await systemSettingsApi.testLdap(testUser, testPw)
        setTestResult(`連線成功：${(r.data as any).display_name} <${(r.data as any).email}>`)
      } else if (backend === 'radius') {
        await systemSettingsApi.testRadius(testUser, testPw)
        setTestResult('RADIUS 認證成功')
      }
    } catch (err: any) {
      setTestResult('連線失敗：' + (err?.response?.data?.detail ?? err?.message ?? '未知錯誤'))
    } finally { setTesting(false) }
  }

  const renderField = (key: string) => {
    const row = settings[key]
    const val = draft[key] ?? ''
    const label = SETTING_LABELS[key] ?? key
    const isSecret = row?.is_secret ?? false
    const isBool = key === 'allow_registration' || key === 'ldap_use_ssl' || key === 'ldap_use_tls'
    const isSelect = key === 'auth_backend'

    return (
      <div key={key} className="grid grid-cols-[180px_1fr] gap-3 items-start py-2 border-b border-gray-50 last:border-0">
        <label className="text-sm text-gray-600 pt-1.5">{label}</label>
        {isSelect ? (
          <select className="input text-sm" value={val} onChange={e => set(key, e.target.value)}>
            <option value="local">本地帳號（Local）</option>
            <option value="ldap">LDAP / Active Directory</option>
            <option value="radius">RADIUS</option>
          </select>
        ) : isBool ? (
          <select className="input text-sm" value={val} onChange={e => set(key, e.target.value)}>
            <option value="true">是</option>
            <option value="false">否</option>
          </select>
        ) : (
          <input
            className="input text-sm"
            type={isSecret ? 'password' : 'text'}
            autoComplete={isSecret ? 'new-password' : undefined}
            value={val}
            onChange={e => set(key, e.target.value)}
            placeholder={isSecret ? '（未更改則保持現有值）' : ''}
          />
        )}
      </div>
    )
  }

  if (loading) return <div className="text-center py-8 text-gray-400 text-sm">載入中…</div>

  const authBackend = draft['auth_backend'] ?? 'local'

  return (
    <div className="max-w-2xl space-y-6">
      <form onSubmit={handleSave} className="space-y-6">

      {/* 一般設定 */}
      <section>
        <h3 className="text-sm font-semibold text-gray-700 mb-3">一般設定</h3>
        <div className="bg-white border border-gray-100 rounded-xl px-4 py-1">
          {GENERAL_KEYS.map(renderField)}
        </div>
      </section>

      {/* LDAP / AD */}
      {(authBackend === 'ldap' || authBackend === 'local') && (
        <section>
          <h3 className="text-sm font-semibold text-gray-700 mb-1">LDAP / Active Directory</h3>
          <p className="text-xs text-gray-400 mb-3">認證方式設為「LDAP / Active Directory」時生效；本地 admin 帳號永遠使用本地密碼。</p>
          <div className="bg-white border border-gray-100 rounded-xl px-4 py-1">
            {LDAP_KEYS.map(renderField)}
          </div>
        </section>
      )}

      {/* RADIUS */}
      {(authBackend === 'radius' || authBackend === 'local') && (
        <section>
          <h3 className="text-sm font-semibold text-gray-700 mb-1">RADIUS</h3>
          <p className="text-xs text-gray-400 mb-3">認證方式設為「RADIUS」時生效；支援 PAP 模式。</p>
          <div className="bg-white border border-gray-100 rounded-xl px-4 py-1">
            {RADIUS_KEYS.map(renderField)}
          </div>
        </section>
      )}

      {/* 測試連線 */}
      {authBackend !== 'local' && (
        <section>
          <h3 className="text-sm font-semibold text-gray-700 mb-3">測試遠端認證</h3>
          <div className="bg-amber-50 border border-amber-100 rounded-xl p-4 space-y-3">
            <p className="text-xs text-amber-700">先儲存設定後再測試，測試使用真實帳號/密碼驗證。</p>
            <div className="grid grid-cols-2 gap-3">
              <input className="input text-sm" placeholder="帳號（username）" value={testUser} onChange={e => setTestUser(e.target.value)} />
              <input className="input text-sm" type="password" placeholder="密碼" value={testPw} onChange={e => setTestPw(e.target.value)} autoComplete="off" />
            </div>
            <button type="button" onClick={handleTest} disabled={testing || !testUser || !testPw} className="btn-secondary text-sm">
              {testing ? '測試中…' : '測試連線'}
            </button>
            {testResult && (
              <p className={`text-sm ${testResult.includes('成功') ? 'text-green-600' : 'text-red-500'}`}>{testResult}</p>
            )}
          </div>
        </section>
      )}

      <div className="flex items-center gap-4 pt-2">
        <button type="submit" disabled={saving} className="btn-primary">
          {saving ? '儲存中…' : '儲存設定'}
        </button>
        {saveMsg && (
          <p className={`text-sm ${saveMsg.includes('成功') ? 'text-green-600' : 'text-red-500'}`}>{saveMsg}</p>
        )}
      </div>
      </form>

      <TlsCertSection />
    </div>
  )
}

// ── TLS 憑證管理區（HTTPS 部署用，Admin only）─────────────────
function TlsCertSection() {
  const [info, setInfo] = useState<TlsCertInfo | null>(null)
  const [cert, setCert] = useState('')
  const [key, setKey] = useState('')
  const [saving, setSaving] = useState(false)
  const [msg, setMsg] = useState('')

  const load = async () => {
    try {
      const r = await systemSettingsApi.getTlsCert()
      setInfo(r.data)
    } catch { /* 非 prod 環境可能無憑證端點資料，忽略 */ }
  }
  useEffect(() => { load() }, [])

  const readFile = (file: File, set: (v: string) => void) => {
    const reader = new FileReader()
    reader.onload = () => set(String(reader.result ?? ''))
    reader.readAsText(file)
  }

  const handleUpload = async () => {
    if (!cert || !key) { setMsg('請提供憑證與私鑰'); return }
    setSaving(true); setMsg('')
    try {
      const r = await systemSettingsApi.uploadTlsCert(cert, key)
      setInfo(r.data)
      setCert(''); setKey('')
      setMsg('已套用，nginx 重載中，約 5 秒後新憑證生效')
    } catch (err: any) {
      setMsg(err?.response?.data?.detail ?? '套用失敗')
    } finally { setSaving(false) }
  }

  const fmt = (s?: string) => (s ? new Date(s).toLocaleString() : '—')

  return (
    <div className="border-t border-gray-100 pt-5 space-y-4">
      <h3 className="text-sm font-semibold text-gray-700">TLS 憑證（HTTPS）</h3>

      {info?.configured ? (
        <div className="bg-gray-50 rounded-xl p-4 text-sm space-y-1">
          <p><span className="text-gray-500">主體 CN：</span>{info.subject_cn || '—'}</p>
          <p><span className="text-gray-500">有效期：</span>{fmt(info.not_before)} ~ {fmt(info.not_after)}</p>
          <p>
            <span className="text-gray-500">類型：</span>
            {info.is_self_signed
              ? <span className="text-amber-600">自簽憑證（瀏覽器會顯示安全告警）</span>
              : <span className="text-green-600">已簽署憑證</span>}
            {info.is_expired && <span className="text-red-500 ml-2">（已過期）</span>}
          </p>
        </div>
      ) : (
        <p className="text-xs text-gray-400">尚未取得憑證資訊（僅在 HTTPS 部署環境可用）。</p>
      )}

      <div className="space-y-3">
        <div>
          <label className="text-xs text-gray-500 block mb-1">憑證檔（cert.pem）</label>
          <input type="file" accept=".pem,.crt,.cert" className="text-sm"
            onChange={e => e.target.files?.[0] && readFile(e.target.files[0], setCert)} />
          <textarea className="input w-full mt-1 font-mono text-xs" rows={3}
            placeholder="-----BEGIN CERTIFICATE-----" value={cert} onChange={e => setCert(e.target.value)} />
        </div>
        <div>
          <label className="text-xs text-gray-500 block mb-1">私鑰檔（key.pem，未加密）</label>
          <input type="file" accept=".pem,.key" className="text-sm"
            onChange={e => e.target.files?.[0] && readFile(e.target.files[0], setKey)} />
          <textarea className="input w-full mt-1 font-mono text-xs" rows={3}
            placeholder="-----BEGIN PRIVATE KEY-----" value={key} onChange={e => setKey(e.target.value)} />
        </div>
        <button type="button" onClick={handleUpload} disabled={saving || !cert || !key} className="btn-primary text-sm">
          {saving ? '套用中…' : '上傳並套用憑證'}
        </button>
        {msg && (
          <p className={`text-sm ${msg.includes('生效') ? 'text-green-600' : 'text-red-500'}`}>{msg}</p>
        )}
      </div>
    </div>
  )
}

// ── 主頁面 ─────────────────────────────────────────────────────
export default function SettingsPage() {
  const user = useAuthStore(s => s.user)
  const [tab, setTab] = useState<Tab>('profile')

  const tabs: { id: Tab; label: string; adminOnly?: boolean }[] = [
    { id: 'profile', label: '個人資料' },
    { id: 'appearance', label: '外觀' },
    { id: 'users',   label: '使用者管理', adminOnly: true },
    { id: 'org',     label: '組織管理', adminOnly: true },
    { id: 'system_config', label: '系統設定', adminOnly: true },
    { id: 'system',  label: '系統資訊', adminOnly: true },
  ]

  const tabClass = (id: Tab) =>
    `px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
      tab === id
        ? 'border-primary-600 text-primary-600'
        : 'border-transparent text-gray-500 hover:text-gray-700'
    }`

  return (
    <div className="max-w-3xl mx-auto">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">設定</h1>

      <nav className="flex gap-1 border-b border-gray-200 mb-6">
        {tabs.filter(t => !t.adminOnly || user?.role === 'admin').map(t => (
          <button key={t.id} className={tabClass(t.id)} onClick={() => setTab(t.id)}>
            {t.label}
          </button>
        ))}
      </nav>

      {tab === 'profile'       && <ProfileTab />}
      {tab === 'appearance'    && <AppearanceTab />}
      {tab === 'users'         && <UsersTab />}
      {tab === 'org'           && <OrgTab />}
      {tab === 'system_config' && <SystemConfigTab />}
      {tab === 'system'        && <SystemTab />}
    </div>
  )
}
