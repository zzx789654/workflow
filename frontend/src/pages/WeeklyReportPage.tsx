import { useEffect, useState } from 'react'
import { weeklyReportApi } from '../api/weeklyReport'
import { exportMarkdownAsPdf } from '../utils/export'

export default function WeeklyReportPage() {
  const [report, setReport] = useState<any>(null)
  const [nextPlan, setNextPlan] = useState('')
  const [loading, setLoading] = useState(true)
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    weeklyReportApi.get().then(r => setReport(r.data)).finally(() => setLoading(false))
  }, [])

  const fullMarkdown = report
    ? report.markdown.replace(
        '<!-- 請在此填寫下週計畫 -->',
        nextPlan || '（尚未填寫）'
      )
    : ''

  const handleCopy = () => {
    navigator.clipboard.writeText(fullMarkdown).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  if (loading) return <div className="p-8 text-center text-gray-400">載入中…</div>

  return (
    <div className="max-w-3xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-bold text-gray-900">週報自動生成</h1>
        <span className="text-sm text-gray-400">
          {report?.week_start?.slice(0, 10)} — {report?.week_end?.slice(0, 10)}
        </span>
      </div>

      {/* 統計卡片 */}
      <div className="grid grid-cols-3 gap-4 mb-6">
        <div className="bg-green-50 border border-green-100 rounded-xl p-4 text-center">
          <div className="text-2xl font-bold text-green-700">{report?.done_count ?? 0}</div>
          <div className="text-xs text-green-500 mt-1">本週完成</div>
        </div>
        <div className="bg-blue-50 border border-blue-100 rounded-xl p-4 text-center">
          <div className="text-2xl font-bold text-blue-700">{report?.wip_count ?? 0}</div>
          <div className="text-xs text-blue-500 mt-1">進行中</div>
        </div>
        <div className="bg-red-50 border border-red-100 rounded-xl p-4 text-center">
          <div className="text-2xl font-bold text-red-700">{report?.overdue_count ?? 0}</div>
          <div className="text-xs text-red-500 mt-1">延遲任務</div>
        </div>
      </div>

      {/* 下週計畫 */}
      <div className="bg-white border border-gray-200 rounded-xl p-4 mb-4">
        <label className="text-sm font-medium text-gray-700 block mb-2">下週計畫（手動填寫）</label>
        <textarea
          className="input w-full text-sm min-h-[80px]"
          placeholder="輸入下週計畫內容…"
          value={nextPlan}
          onChange={e => setNextPlan(e.target.value)}
        />
      </div>

      {/* Markdown 預覽 */}
      <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100 bg-gray-50">
          <span className="text-sm font-medium text-gray-700">Markdown 預覽</span>
          <div className="flex gap-2">
            <button
              onClick={() => exportMarkdownAsPdf(fullMarkdown, 'weekly_report.pdf')}
              className="text-xs bg-gray-600 text-white px-3 py-1.5 rounded-lg hover:bg-gray-700"
            >
              PDF
            </button>
            <button
              onClick={handleCopy}
              className="text-xs bg-primary-600 text-white px-3 py-1.5 rounded-lg hover:bg-primary-700"
            >
              {copied ? '✓ 已複製' : '複製 Markdown'}
            </button>
          </div>
        </div>
        <pre className="p-4 text-xs text-gray-700 whitespace-pre-wrap font-mono overflow-x-auto max-h-96">
          {fullMarkdown}
        </pre>
      </div>
    </div>
  )
}
