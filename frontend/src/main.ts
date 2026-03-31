import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import './style.css'
import { createPinia } from 'pinia'
import router from './router'
import App from './App.vue'

console.log("main.ts executing")

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.use(ElementPlus)

app.config.errorHandler = (err, instance, info) => {
  console.error("Vue Global Error:", err, info)
}

window.addEventListener('error', (event) => {
  console.error("Global JS Error:", event.error)
})

window.addEventListener('unhandledrejection', (event) => {
  console.error("Unhandled Promise Rejection:", event.reason)
})

app.mount('#app')
console.log("App mounted")
