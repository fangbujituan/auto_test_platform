import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  test: {
    environment: 'node',
  },
  server: {
    watch: {
      // 忽略后端和项目根目录的文件变化，避免触发前端 full reload
      ignored: ['**/app/**', '**/tests/**', '**/.git/**', '**/.kiro/**', '**/.idea/**', '**/__pycache__/**'],
    },
    proxy: {
      // SSE 流式接口需要单独配置，禁用代理缓冲
      '/api/ai/chat/stream': {
        target: 'http://localhost:12048',
        changeOrigin: true,
        // 关键：禁用代理缓冲，让 SSE 数据实时推送到浏览器
        configure: (proxy) => {
          proxy.on('proxyRes', (proxyRes) => {
            proxyRes.headers['Cache-Control'] = 'no-cache'
            proxyRes.headers['X-Accel-Buffering'] = 'no'
          })
        }
      },
      '/api': {
        target: 'http://localhost:12048',
        changeOrigin: true
      }
    }
  }
})
