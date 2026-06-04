export function exportCsv(rows: Record<string, unknown>[], filename: string) {
  if (!rows.length) return
  const headers = Object.keys(rows[0])
  const csv = [
    headers.join(','),
    ...rows.map(r =>
      headers.map(h => {
        const v = String(r[h] ?? '')
        return v.includes(',') || v.includes('"') ? `"${v.replace(/"/g, '""')}"` : v
      }).join(',')
    ),
  ].join('\n')
  const blob = new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

export function exportMarkdownAsPdf(markdown: string, filename: string) {
  // Simplified: open in new window for browser print-to-PDF
  const win = window.open('', '_blank')
  if (!win) return
  win.document.write(`<html><body><pre style="white-space:pre-wrap;font-family:monospace">${markdown}</pre></body></html>`)
  win.document.close()
  win.print()
}
