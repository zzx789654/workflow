import { Link, NavLink, useNavigate } from 'react-router-dom'
import { useAuthStore } from '../../stores/authStore'
import { useThemeStore } from '../../stores/themeStore'
import SearchBar from './SearchBar'
import NotificationBell from './NotificationBell'

const navItems = [
  { to: '/', label: '專案總覽', icon: '📁', end: true },
  { to: '/daily', label: '日常作業', icon: '📋', end: false },
  { to: '/templates', label: '專案範本', icon: '🗂️', end: false },
  { to: '/calendar', label: '月曆', icon: '📅', end: false },
  { to: '/time-report', label: '工時報表', icon: '⏱️', end: false },
  { to: '/weekly-report', label: '週報', icon: '📊', end: false },
  { to: '/workload', label: '工作量', icon: '⚖️', end: false },
  { to: '/insights', label: '個人分析', icon: '📈', end: false },
  { to: '/announcements', label: '公告板', icon: '📢', end: false },
  { to: '/ai-assist', label: 'AI 建議', icon: '🤖', end: false },
]

const bottomNavItems = [
  { to: '/settings', label: '設定', icon: '⚙️', end: false },
]

export default function Layout({ children }: { children: React.ReactNode }) {
  const user = useAuthStore((s) => s.user)
  const logout = useAuthStore((s) => s.logout)
  const navigate = useNavigate()
  const { dark, toggle: toggleDark } = useThemeStore()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  const navClass = ({ isActive }: { isActive: boolean }) =>
    `flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
      isActive
        ? 'bg-primary-50 text-primary-700'
        : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
    }`

  return (
    <div className="min-h-screen flex">
      {/* 側邊欄 */}
      <aside className="w-52 flex-shrink-0 bg-white border-r border-gray-200 flex flex-col">
        <div className="px-4 py-4 border-b border-gray-100">
          <Link to="/" className="text-lg font-bold text-primary-600">WorkFlow</Link>
          <p className="text-xs text-gray-400 mt-0.5 truncate">{user?.display_name}</p>
        </div>

        <nav className="flex-1 px-3 py-3 space-y-1">
          {navItems.map(item => (
            <NavLink key={item.to} to={item.to} end={item.end} className={navClass}>
              <span>{item.icon}</span>
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="px-3 pb-2 space-y-1">
          {bottomNavItems.map(item => (
            <NavLink key={item.to} to={item.to} end={item.end} className={navClass}>
              <span>{item.icon}</span>
              <span>{item.label}</span>
            </NavLink>
          ))}
        </div>

        <div className="px-4 py-3 border-t border-gray-100">
          <div className="flex items-center gap-2 mb-2">
            <div className="w-7 h-7 rounded-full bg-primary-500 text-white text-xs flex items-center justify-center font-medium flex-shrink-0">
              {user?.display_name?.charAt(0).toUpperCase()}
            </div>
            <div className="min-w-0">
              <p className="text-xs font-medium text-gray-700 truncate">{user?.display_name}</p>
              <p className="text-xs text-gray-400 capitalize">{user?.role}</p>
            </div>
          </div>
          <button onClick={handleLogout} className="text-xs text-gray-400 hover:text-gray-600 w-full text-left">
            登出
          </button>
        </div>
      </aside>

      {/* 主內容 */}
      <div className="flex-1 min-w-0 flex flex-col">
        <header className="bg-white dark:bg-gray-900 border-b border-gray-200 dark:border-gray-700 px-6 py-2.5 flex items-center justify-end gap-3">
          <SearchBar />
          <NotificationBell />
          <button
            onClick={toggleDark}
            className="text-lg text-gray-500 hover:text-gray-700 dark:text-gray-300 dark:hover:text-white"
            title={dark ? '切換淺色模式' : '切換暗色模式'}
          >
            {dark ? '☀️' : '🌙'}
          </button>
        </header>
        <main className="flex-1 p-6 bg-gray-50 overflow-y-auto">
          {children}
        </main>
      </div>
    </div>
  )
}
