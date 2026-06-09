// 計算 WebSocket base URL。
// 同源部署（VITE_WS_URL 未設）時依當前頁面協定動態組 ws/wss，
// 讓 HTTPS 部署自動走 wss、不需 build-time 寫死主機位址；
// 否則用設定值（dev 預設指向本機 backend）。
export function wsBase(): string {
  const configured = import.meta.env.VITE_WS_URL as string | undefined
  if (configured) return configured
  if (typeof window !== 'undefined' && window.location.host) {
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    return `${proto}//${window.location.host}`
  }
  return 'ws://localhost:8000'
}
