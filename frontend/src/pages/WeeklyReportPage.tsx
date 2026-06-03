import { useEffect, useRef, useState } from 'react'
import jsPDF from 'jspdf'
import { weeklyReportsApi, type WeeklyReport } from '../api/weeklyReports'

function toMarkdown(report: WeeklyReport): string {
  const lines: string[] = []
  lines.push(`# 週報 ${report.week_start} ~ ${report.week_end}`)
  lines.push('')
  lines.push('## 本週完成')
  if (report.completed_tasks.length === 0) {
    lines.push('（無）')
  } else {
    report.completed_tasks.forEach((t) => lines.push(`- ${t.title}`))
  }
  lines.push('')
  lines.push('## 延遲任務')
  if (report.delayed_tasks.length === 0) {
    lines.push('（無）')
  } else {
    report.delayed_tasks.forEach((t) => lines.push(`- ${t.title}`))
  }
  lines.push('')
  lines.push('## 下週計畫')
  lines.push(report.next_week_plan || '（未填寫）')
  if (report.generated_at) {
    lines.push('')
    lines.push(`> 產生時間：${report.generated_at}`)
  }
  return lines.join('\n')
}

export default function WeeklyReportPage() {
  const [report, setReport] = useState<WeeklyReport | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [generating, setGenerating] = useState(false)
  const [copied, setCopied] = useState(false)
  const [plan, setPlan] = useState('')
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const handleExportPdf = () => {
    if (!report) return
    const md = toMarkdown({ ...report, next_week_plan: plan })
    const doc = new jsPDF({ unit: 'pt', format: 'a4' })
    const margin = 40
    const lineHeight = 16
    const pageWidth = doc.internal.pageSize.getWidth() - margin * 2
    let y = margin

    doc.setFontSize(16)
    md.split('\n').forEach((line) => {
      if (y > doc.internal.pageSize.getHeight() - margin) {
        doc.addPage()
        y = margin
      }
      if (line.startsWith('# ')) {
        doc.setFontSize(16)
        doc.setFont('helvetica', 'bold')
        const text = line.replace(/^# /, '')
        doc.text(text, margin, y)
        doc.setFontSize(11)
        doc.setFont('helvetica', 'normal')
      } else if (line.startsWith('## ')) {
        doc.setFontSize(13)
        doc.setFont('helvetica', 'bold')
        doc.text(line.replace(/^## /, ''), margin, y)
        doc.setFontSize(11)
        doc.setFont('helvetica', 'normal')
      } else {
        const wrapped = doc.splitTextToSize(line || ' ', pageWidth)
        doc.text(wrapped, margin, y)
        y += lineHeight * (wrapped.length - 1)
      }
      y += lineHeight
    })
    doc.save(`weekly-report-${report.week_start}.pdf`)
  }

  const load = () => {
    setLoading(true)
    setError('')
    weeklyReportsApi.getCurrent()
      .then((res) => {
        setReport(res.data)
        setPlan(res.data.next_week_plan ?? '')
      })
      .catch(() => setError('載入失敗，請稍後再試'))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  const handlePlanChange = (val: string) => {
    setPlan(val)
    if (saveTimer.current) clearTimeout(saveTimer.current)
    saveTimer.current = setTimeout(() => {
      setReport((prev) => prev ? { ...prev, next_week_plan: val } : prev)
    }, 800)
  }

  const handleGenerate = async () => {
    setGenerating(true)
    try {
      const res = await weeklyReportsApi.generate()
      setReport(res.data)
      setPlan(res.data.next_week_plan ?? '')
    } catch {
      setError('產生失敗，請稍後再試')
    } finally {
      setGenerating(false)
    }
  }

  const handleCopy = () => {
    if (!report) return
    const md = toMarkdown({ ...report, next_week_plan: plan })
    navigator.clipboard.writeText(md).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  if (loading) return <div className="text-center py-20 text-gray-400">載入中…</div>
  if (error) return <div className="text-center py-10 text-red-500">{error}</div>

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-gray-900">週報</h1>
          {report && (
            <p className="text-sm text-gray-400 mt-0.5">
              {report.week_start} ~ {report.week_end}
              {report.generated_at && (
                <span className="ml-2">（產生於 {report.generated_at}）</span>
              )}
            </p>
          )}
        </div>
        <div className="flex gap-2">
          <button onClick={handleCopy} className="btn-secondary">
            {copied ? '已複製！' : '複製 Markdown'}
          </button>
          <button onClick={handleExportPdf} disabled={!report} className="btn-secondary">
            📄 匯出 PDF
          </button>
          <button onClick={handleGenerate} disabled={generating} className="btn-primary">
            {generating ? '產生中…' : '產生報告'}
          </button>
        </div>
      </div>

      {report && (
        <>
          <div className="card">
            <h2 className="text-sm font-semibold text-gray-700 mb-3">本週完成任務</h2>
            {report.completed_tasks.length === 0 ? (
              <p className="text-sm text-gray-400">（本週無完成任務）</p>
            ) : (
              <ul className="space-y-1.5">
                {report.completed_tasks.map((t) => (
                  <li key={t.id} className="flex items-center gap-2 text-sm text-gray-700">
                    <span className="w-2 h-2 rounded-full bg-green-400 flex-shrink-0" />
                    {t.title}
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="card">
            <h2 className="text-sm font-semibold text-gray-700 mb-3">延遲任務</h2>
            {report.delayed_tasks.length === 0 ? (
              <p className="text-sm text-gray-400">（本週無延遲任務）</p>
            ) : (
              <ul className="space-y-1.5">
                {report.delayed_tasks.map((t) => (
                  <li key={t.id} className="flex items-center gap-2 text-sm text-gray-700">
                    <span className="w-2 h-2 rounded-full bg-red-400 flex-shrink-0" />
                    {t.title}
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="card">
            <h2 className="text-sm font-semibold text-gray-700 mb-3">下週計畫</h2>
            <textarea
              className="input w-full min-h-[120px] resize-y"
              placeholder="輸入下週計畫…"
              value={plan}
              onChange={(e) => handlePlanChange(e.target.value)}
            />
            <p className="text-xs text-gray-400 mt-1">自動儲存</p>
          </div>
        </>
      )}
    </div>
  )
}
