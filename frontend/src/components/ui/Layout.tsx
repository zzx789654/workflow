import { Link, NavLink, useNavigate } from 'react-router-dom'
import { useAuthStore } from '../../stores/authStore'
import { useThemeStore } from '../../stores/themeStore'
import { useNotificationWs } from '../../hooks/useNotificationWs'
import SearchBar from './SearchBar'
import NotificationBell from './NotificationBell'
import ThemeSwitcher from './ThemeSwitcher'

const navItems = [
  { to: '/', label: '儀表板', icon: '🏠', end: true },
  { to: '/overview', label: '專案總覽', icon: '🗂️', end: false },
  { to: '/daily', label: '日常作業', icon: '📋', end: false },
  { to: '/templates', label: '專案範本', icon: '📄', end: false },
  { to: '/calendar', label: '月曆', icon: '📅', end: false },
  { to: '/archived', label: '任務整理', icon: '📦', end: false },
  { to: '/history', label: '歷史記錄', icon: '🗄️', end: false },
]

const bottomNavItems = [
  { to: '/settings', label: '設定', icon: '⚙️', end: false },
]

const ROLE_LABEL: Record<string, string> = {
  admin: '管理員', member: '一般成員', viewer: '訪客',
}

export default function Layout({ children }: { children: React.ReactNode }) {
  const user = useAuthStore((s) => s.user)
  const logout = useAuthStore((s) => s.logout)
  const navigate = useNavigate()
  const { dark, toggle: toggleDark } = useThemeStore()
  useNotificationWs()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  const navClass = ({ isActive }: { isActive: boolean }) =>
    isActive ? 'nav-item-active' : 'nav-item-inactive'

  return (
    <div className="h-screen overflow-hidden flex app-surface">
      {/* 側邊欄 */}
      <aside className="w-52 flex-shrink-0 border-r border-gray-200 dark:border-gray-800 flex flex-col surface-panel">
        {/* Logo */}
        <div className="px-4 py-4 border-b border-gray-100 dark:border-gray-800">
          <Link to="/" className="block">
            <span className="text-lg font-bold text-primary-600 dark:text-primary-400 tracking-tight">
              WorkFlow
            </span>
          </Link>
          <p className="text-xs text-gray-400 dark:text-gray-500 mt-0.5 truncate">{user?.display_name}</p>
        </div>

        {/* Nav */}
        <nav className="flex-1 px-2 py-3 space-y-0.5 scrollbar-thin overflow-y-auto">
          {navItems.map(item => (
            <NavLink key={item.to} to={item.to} end={item.end} className={navClass}>
              <span className="text-base leading-none">{item.icon}</span>
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>

        {/* Bottom nav */}
        <div className="px-2 pb-2 space-y-0.5 border-t border-gray-100 dark:border-gray-800 pt-2">
          {bottomNavItems.map(item => (
            <NavLink key={item.to} to={item.to} end={item.end} className={navClass}>
              <span className="text-base leading-none">{item.icon}</span>
              <span>{item.label}</span>
            </NavLink>
          ))}
        </div>

        {/* User badge */}
        <div className="px-4 py-3 border-t border-gray-100 dark:border-gray-800">
          <div className="flex items-center gap-2 mb-2">
            <div className="w-7 h-7 rounded-full bg-primary-500 text-white text-xs flex items-center justify-center font-bold flex-shrink-0">
              {user?.display_name?.charAt(0).toUpperCase()}
            </div>
            <div className="min-w-0">
              <p className="text-xs font-medium text-gray-700 dark:text-gray-200 truncate">{user?.display_name}</p>
              <p className="text-[10px] text-gray-400 dark:text-gray-500">
                {ROLE_LABEL[user?.role ?? 'member'] ?? user?.role}
              </p>
            </div>
          </div>
          <button
            onClick={handleLogout}
            className="text-xs text-gray-400 hover:text-red-500 dark:text-gray-500 dark:hover:text-red-400 w-full text-left transition-colors duration-150"
          >
            登出
          </button>
        </div>
      </aside>

      {/* 主內容 */}
      <div className="flex-1 min-w-0 flex flex-col">
        <header className="surface-panel border-b border-gray-200 dark:border-gray-800 px-6 py-2.5 flex items-center justify-end gap-3 sticky top-0 z-30">
          <SearchBar />
          <NotificationBell />
          <ThemeSwitcher />
          <button
            onClick={toggleDark}
            className="w-8 h-8 flex items-center justify-center rounded-lg text-gray-500 hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-gray-800 transition-colors duration-150"
            title={dark ? '切換淺色模式' : '切換暗色模式'}
          >
            <span className="text-base">{dark ? '☀️' : '🌙'}</span>
          </button>
        </header>
        <main className="flex-1 p-6 app-surface overflow-y-auto scrollbar-thin page-enter">
          {children}
        </main>
      </div>
    </div>
  )
}
