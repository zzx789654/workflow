import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useAuthStore } from '../stores/authStore'

export default function LoginPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const login = useAuthStore((s) => s.login)
  const navigate = useNavigate()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await login(email, password)
      navigate('/')
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(msg ?? '登入失敗，請確認帳號密碼')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-primary-50 via-white to-gray-50">
      <div className="card w-full max-w-md shadow-lg" style={{ animation: 'slide-up 0.25s ease-out' }}>
        <div className="text-center mb-6">
          <span className="text-3xl font-bold text-primary-600 tracking-tight">WorkFlow</span>
          <p className="text-sm text-gray-500 mt-1">登入您的帳號</p>
        </div>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">電子郵件</label>
            <input className="input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoFocus />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">密碼</label>
            <input className="input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
          </div>
          {error && (
            <p className="text-red-500 text-sm bg-red-50 border border-red-100 rounded-lg px-3 py-2">
              {error}
            </p>
          )}
          <button type="submit" disabled={loading} className="btn-primary w-full">
            {loading ? (
              <span className="flex items-center justify-center gap-2">
                <span className="w-4 h-4 border-2 border-white/40 border-t-white rounded-full animate-spin" />
                登入中…
              </span>
            ) : '登入'}
          </button>
        </form>
        <p className="mt-4 text-center text-sm text-gray-600">
          還沒有帳號？ <Link to="/register" className="text-primary-600 hover:underline">立即註冊</Link>
        </p>
      </div>
    </div>
  )
}
