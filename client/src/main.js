import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import 'element-plus/theme-chalk/dark/css-vars.css'
import router from './router'
import App from './App.vue'

// 启动时应用已保存的主题设置
try {
  const saved = localStorage.getItem('atp_appearance_settings')
  if (saved) {
    const { theme } = JSON.parse(saved)
    if (theme === 'dark') {
      document.documentElement.classList.add('dark')
    }
  }
} catch (e) {
  // 忽略解析错误
}

const app = createApp(App)

app.use(ElementPlus)
app.use(router)
app.mount('#app')
