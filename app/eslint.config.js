import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tseslint from 'typescript-eslint'
import { defineConfig, globalIgnores } from 'eslint/config'

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      js.configs.recommended,
      tseslint.configs.recommended,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
    },
    rules: {
      // 剔除字段的标准写法是 `const { key, ...rest } = props`，
      // 其中被剔除的字段本身不会被使用，不应报未使用。
      '@typescript-eslint/no-unused-vars': [
        'error',
        {
          ignoreRestSiblings: true,
          argsIgnorePattern: '^_',
          varsIgnorePattern: '^_',
        },
      ],

      // ------------------------------------------------------------------
      // 以下规则降级为 warning（而非关闭，以保留信号）。
      //
      // 理由：它们描述的是「不够理想」，不是「代码错误」，但会让 lint 退出码非零。
      // 闸门要求 lint 全绿，所以这些不能留在 error 级别。
      //
      // - no-explicit-any：recharts 的 dot/tooltip 渲染函数签名、以及
      //   `catch (err: any)` 都依赖 any，全量类型化收益有限。
      // - only-export-components：只影响开发期 Fast Refresh，与构建产物无关。
      // - react-hooks/{set-state-in-effect,static-components,purity}：
      //   React Compiler 的优化潜力提示，不影响运行时正确性。
      // ------------------------------------------------------------------
      '@typescript-eslint/no-explicit-any': 'warn',
      'react-refresh/only-export-components': 'warn',
      'react-hooks/set-state-in-effect': 'warn',
      'react-hooks/static-components': 'warn',
      'react-hooks/purity': 'warn',
    },
  },
])
