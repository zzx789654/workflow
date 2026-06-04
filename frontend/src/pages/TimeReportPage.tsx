import { useEffect, useState } from 'react'
import { api } from '../api/client'
import type { Project } from '../types'
import { projectsApi } from '../api/projects'
import { exportCsv } from '../utils/export'

interface ReportRow {
  user_id: string
  user_name: string
  project_id: string
  project_name: string
  total_minutes: number
  total_hours: number
}

export default function TimeReportPage() {
  const [projects, setProjects] = useState<Project[]>([])
  const [selectedProject, setSelectedProject] = useState('')
  const [rows, setRows] = useState<ReportRow[]>([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    projectsApi.list().then(r => setProjects(r.data))
  }, [])

  const fetchReport = async () => {
    setLoading(true)
    try {
      const params = new URLSearchParams()
      if (selectedProject) params.set('project_id', selectedProject)
      const res = await api.get<{ report: ReportRow[] }>(`/time-logs/report?${params}`)
      setRows(res.data.report)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchReport() }, [selectedProject])

  const totalMins = rows.reduce((s, r) => s + r.total_minutes, 0)
  const fmtMins = (m: number) => m >= 60 ? `${Math.floor(m / 60)}h ${m % 60}m` : `${m}m`

  return (
    <div className="max-w-3xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-bold text-gray-900">工時報表</h1>
        <div className="flex items-center gap-2">
          {rows.length > 0 && (
            <button
              onClick={() => exportCsv(rows.map(r => ({ 成員: r.user_name, 專案: r.project_name, 工時_分鐘: r.total_minutes, 工時_小時: r.total_hours })), 'time_report.csv')}
              className="btn-secondary text-sm"
            >
              匯出 CSV
            </button>
          )}
          <select
            className="input text-sm w-48"
            value={selectedProject}
            onChange={e => setSelectedProject(e.target.value)}
          >
            <option value="">所有專案</option>
            {projects.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
        </div>
      </div>

      {totalMins > 0 && (
        <div className="bg-primary-50 border border-primary-100 rounded-xl p-4 mb-4 flex items-center gap-3">
          <span className="text-2xl font-bold text-primary-700">{fmtMins(totalMins)}</span>
          <span className="text-sm text-primary-500">總工時（{rows.length} 筆）</span>
        </div>
      )}

      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        {loading ? (
          <div className="p-8 text-center text-gray-400 text-sm">載入中…</div>
        ) : rows.length === 0 ? (
          <div className="p-8 text-center text-gray-400 text-sm">目前尚無工時記錄</div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="text-left px-4 py-3 text-xs font-medium text-gray-500">成員</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-gray-500">專案</th>
                <th className="text-right px-4 py-3 text-xs font-medium text-gray-500">總工時</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {rows.map((r, i) => (
                <tr key={i} className="hover:bg-gray-50">
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <div className="w-7 h-7 rounded-full bg-primary-500 text-white text-xs flex items-center justify-center font-medium flex-shrink-0">
                        {(r.user_name ?? r.user_id).charAt(0).toUpperCase()}
                      </div>
                      <span className="font-medium text-gray-700">{r.user_name ?? r.user_id}</span>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-gray-500">{r.project_name ?? r.project_id}</td>
                  <td className="px-4 py-3 text-right font-medium text-primary-700">{fmtMins(r.total_minutes)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
