/** @type {import('tailwindcss').Config} */
// 视觉语言见 docs/20-前端设计规范.md：颜色、字体与字号令牌都在
// src/styles/tokens.css，这里只保留内容扫描与 Tailwind 默认调色板 ——
// 不再维护 shadcn 的主题变量映射（主题类只剩 ui/tabs.tsx 一处，已改为自有样式）。
module.exports = {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {},
  },
  plugins: [],
}
