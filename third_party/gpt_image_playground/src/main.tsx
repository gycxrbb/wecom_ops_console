import 'core-js/actual/array/at'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import 'streamdown/styles.css'
import 'katex/dist/katex.min.css'
import './index.css'
import { installMobileViewportGuards } from './lib/viewport'

installMobileViewportGuards()

// 不再注册 Service Worker：playground 作为嵌入企业后台的功能模块，不需要离线/可安装，
// 而 SW 会把旧 index.html 锁在缓存里，导致每次升级后用户看不到新版（见 memory #150）。
// 这里在启动时注销历史遗留的 SW 并清空其 Cache Storage，让所有用户回到「每次网络最新」。
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.getRegistrations().then((registrations) => {
      registrations.forEach((registration) => registration.unregister())
    })
    if ('caches' in window) {
      caches.keys().then((keys) => {
        keys.forEach((key) => caches.delete(key))
      })
    }
  })
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
