import path from "path"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vite"

// 代理目标默认指向本地 8000；Playwright 用 VITE_PROXY_TARGET 把它改到自己
// 拉起的后端端口，避免真实开发后端正跑在 8000 时端到端跑不起来。
const proxyTarget = process.env.VITE_PROXY_TARGET || "http://localhost:8000"

// https://vite.dev/config/
export default defineConfig({
  base: './',
  plugins: [react()],
  build: {
    // 多页：看板（index.html）与研究页（research.html）各自独立入口；
    // base './' 下相对链接 ./research.html 在预览与静态部署里都能直达。
    rollupOptions: {
      input: {
        main: path.resolve(__dirname, 'index.html'),
        research: path.resolve(__dirname, 'research.html'),
      },
    },
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    // 开发期把 API 请求代理到本地后端，这样前端可以统一使用相对路径，
    // 生产环境交给 nginx 反代，两边行为一致。
    proxy: {
      '/api': { target: proxyTarget, changeOrigin: true },
      '/health': { target: proxyTarget, changeOrigin: true },
    },
  },
  preview: {
    // 端到端测试用 `vite preview` 提供构建产物，同样需要把 API 代理到后端
    proxy: {
      '/api': { target: proxyTarget, changeOrigin: true },
      '/health': { target: proxyTarget, changeOrigin: true },
    },
  },
});
