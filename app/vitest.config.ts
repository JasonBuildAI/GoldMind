import path from 'path'
import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vitest/config'

// 独立的 vitest 配置：不复用 vite.config.ts，避免把开发服务器代理等
// 与测试无关的配置带进来。
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  test: {
    // 用 happy-dom 而不是 jsdom：jsdom 的依赖链里
    // html-encoding-sniffer → @exodus/bytes 存在 ESM/CJS 冲突，
    // 在当前 Node 版本下 vitest 无法启动 worker。
    environment: 'happy-dom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    // 测试与被测代码放在一起，目录名 __tests__；不用 *.test.* 散落在 src 根下。
    include: ['src/**/__tests__/**/*.{test,spec}.ts'],
    // 组件只测逻辑与可访问性，不测样式，跳过 CSS 处理以加快速度
    css: false,
  },
})
