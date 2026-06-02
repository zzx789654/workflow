import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { searchApi, type SearchResult } from '../../api/search'

const TYPE_LABEL: Record<string, string> = { project: '專案', task: '任務', daily: '日常作業' }
const TYPE_COLOR: Record<string, string> = {
  project: 'bg-purple-100 text-purple-700',
  task: 'bg-blue-100 text-blue-700',
  daily: 'bg-green-100 text-green-700',
}

export default function SearchBar() {
  const [q, setQ] = useState('')
  const [results, setResults] = useState<SearchResult[]>([])
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const navigate = useNavigate()

  useEffect(() => {
    if (!q.trim()) { setResults([]); setOpen(false); return }
    if (timerRef.current) clearTimeout(timerRef.current)
    timerRef.current = setTimeout(async () => {
      setLoading(true)
      try {
        const res = await searchApi.search(q.trim())
        setResults(res.data.results)
        setOpen(true)
      } catch {
        setResults([])
      } finally {
        setLoading(false)
      }
    }, 280)
    return () => { if (timerRef.current) clearTimeout(timerRef.current) }
  }, [q])

  const handleSelect = (r: SearchResult) => {
    setOpen(false)
    setQ('')
    if (r.type === 'project') navigate(`/projects/${r.project_id}`)
    else if (r.type === 'task') navigate(`/projects/${r.project_id}`)
    else navigate('/daily')
  }

  return (
    <div className="relative w-72">
      <input
        className="input w-full pl-8 text-sm"
        placeholder="搜尋任務、專案…"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        onFocus={() => q && results.length > 0 && setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
      />
      <span className="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-400 text-sm">🔍</span>
      {loading && (
        <span className="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-400 text-xs">…</span>
      )}

      {open && results.length > 0 && (
        <div className="absolute top-full left-0 right-0 mt-1 bg-white border border-gray-200 rounded-xl shadow-lg z-50 max-h-80 overflow-y-auto">
          {results.map((r) => (
            <button
              key={`${r.type}-${r.id}`}
              className="w-full flex items-center gap-3 px-3 py-2.5 hover:bg-gray-50 text-left transition-colors"
              onMouseDown={() => handleSelect(r)}
            >
              <span className={`text-xs px-2 py-0.5 rounded-full flex-shrink-0 ${TYPE_COLOR[r.type]}`}>
                {TYPE_LABEL[r.type]}
              </span>
              <div className="min-w-0 flex-1">
                <p className="text-sm text-gray-800 truncate">{r.title}</p>
                {r.project_name && r.type !== 'project' && (
                  <p className="text-xs text-gray-400 truncate">{r.project_name}</p>
                )}
              </div>
            </button>
          ))}
        </div>
      )}
      {open && !loading && q && results.length === 0 && (
        <div className="absolute top-full left-0 right-0 mt-1 bg-white border border-gray-200 rounded-xl shadow-lg z-50 px-3 py-3 text-sm text-gray-400 text-center">
          無結果
        </div>
      )}
    </div>
  )
}
