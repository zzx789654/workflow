import { useEffect, useState } from 'react'
import { useAuthStore } from '../stores/authStore'
import { authApi } from '../api/auth'
import type { User } from '../types'

// ── API helpers ───────────────────────────────────────────────
import { api } from '../api/client'

const usersApi = {
  list: () => api.get<User[]>('/users/'),
  updateRole: (userId: string, role: string) =>
    api.patch<User>(`/users/${userId}/role?role=${role}`),
  deactivate: (userId: string) =>
    api.delete(`/users/${userId}`),
  updateMe: (data: { display_name?: string; avatar_url?: string }) =>
    api.patch<User>('/users/me', data),
  changePassword: (oldPw: string, newPw: string) =>
    api.post('/auth/change-password', { old_password: oldPw, new_password: newPw }),
}

type Tab = 'profile' | 'users' | 'system' | 'system_config'

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
  const [saving, setSaving] = useState(false)
  const [oldPw, setOldPw] = useState('')
  const [newPw, setNewPw] = useState('')
  const [pwMsg, setPwMsg] = useState('')
  const [pwSaving, setPwSaving] = useState(false)

  const handleSaveProfile = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    try {
      await usersApi.updateMe({ display_name: displayName })
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
            <label className="text-xs text-gray-500 block mb-1">顯示名稱</label>
            <input className="input w-full" value={displayName}
              onChange={e => setDisplayName(e.target.value)} required />
          </div>
          <div>
            <label className="text-xs text-gray-500 block mb-1">Email</label>
            <input className="input w-full bg-gray-50" value={user?.email ?? ''} disabled />
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

// ── 使用者管理 Tab（Admin only）────────────────────────────────
function UsersTab() {
  const me = useAuthStore(s => s.user)
  const [users, setUsers] = useState<User[]>([])
  const [loading, setLoading] = useState(true)
  const [updatingId, setUpdatingId] = useState<string | null>(null)

  const load = async () => {
    setLoading(true)
    try { const r = await usersApi.list(); setUsers(r.data) }
    finally { setLoading(false) }
  }
  useEffect(() => { load() }, [])

  const handleRoleChange = async (userId: string, role: string) => {
    setUpdatingId(userId)
    try { await usersApi.updateRole(userId, role); load() }
    finally { setUpdatingId(null) }
  }

  const handleDeactivate = async (userId: string, name: string) => {
    if (!confirm(`確定停用帳號「${name}」？`)) return
    await usersApi.deactivate(userId)
    load()
  }

  if (loading) return <div className="text-gray-400 py-8 text-center">載入中…</div>

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-gray-700">使用者管理</h3>
        <span className="text-xs text-gray-400">{users.length} 位使用者</span>
      </div>
      <div className="space-y-2">
        {users.map(u => (
          <div key={u.id} className="flex items-center gap-3 p-3 bg-white border border-gray-100 rounded-xl">
            <div className="w-9 h-9 rounded-full bg-primary-500 text-white flex items-center justify-center font-medium flex-shrink-0">
              {u.display_name.charAt(0).toUpperCase()}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-gray-900 truncate">{u.display_name}</p>
              <p className="text-xs text-gray-400 truncate">{u.email}</p>
            </div>
            <div className="flex items-center gap-2 flex-shrink-0">
              {me?.role === 'admin' && u.id !== me?.id ? (
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
              ) : (
                <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${ROLE_COLORS[u.role]}`}>
                  {ROLE_LABELS[u.role]}
                </span>
              )}
            </div>
          </div>
        ))}
      </div>
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
    <form onSubmit={handleSave} className="max-w-2xl space-y-6">

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
  )
}

// ── 主頁面 ─────────────────────────────────────────────────────
export default function SettingsPage() {
  const user = useAuthStore(s => s.user)
  const [tab, setTab] = useState<Tab>('profile')

  const tabs: { id: Tab; label: string; adminOnly?: boolean }[] = [
    { id: 'profile', label: '個人資料' },
    { id: 'users',   label: '使用者管理', adminOnly: true },
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
      {tab === 'users'         && <UsersTab />}
      {tab === 'system_config' && <SystemConfigTab />}
      {tab === 'system'        && <SystemTab />}
    </div>
  )
}
