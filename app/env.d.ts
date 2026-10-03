/// <reference types="vite/client" />

/**
 * Vue 单文件组件在 TypeScript 里的模块声明。
 *
 * `vue-tsc` 处理 `.vue` 文件本身，但 `tsc` 语境（编辑器、eslint 的 type-aware
 * 规则）需要一个通配声明才不会把 `import X from './X.vue'` 报成找不到模块。
 */
declare module '*.vue' {
  import type { DefineComponent } from 'vue'

  const component: DefineComponent<Record<string, unknown>, Record<string, unknown>, unknown>
  export default component
}
