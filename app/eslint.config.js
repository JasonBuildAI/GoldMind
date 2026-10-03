import js from '@eslint/js'
import pluginVue from 'eslint-plugin-vue'
import globals from 'globals'
import tseslint from 'typescript-eslint'
import { defineConfig, globalIgnores } from 'eslint/config'

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,vue}'],
    extends: [
      js.configs.recommended,
      tseslint.configs.recommended,
      // flat/recommended 用的是 vue-eslint-parser + 官方规则集，
      // 含 vue/multi-word-component-names 等命名约定。
      pluginVue.configs['flat/recommended'],
    ],
    languageOptions: {
      ecmaVersion: 2022,
      globals: globals.browser,
      parserOptions: {
        // <script setup lang="ts"> 里是 TypeScript，交给 tseslint 的解析器
        parser: tseslint.parser,
        extraFileExtensions: ['.vue'],
        sourceType: 'module',
      },
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

      // 组件名一律 PascalCase 且多词；单文件组件本身就是文件名，不必再要求
      // 模板里写多词标签。
      'vue/multi-word-component-names': 'off',
      // 属性换行交给格式化工具；闸门只关心正确性，不关心排版。
      'vue/max-attributes-per-line': 'off',
      'vue/singleline-html-element-content-newline': 'off',
      'vue/html-self-closing': 'off',
      'vue/html-indent': 'off',
      'vue/html-closing-bracket-newline': 'off',
      'vue/attributes-order': 'off',
      'vue/first-attribute-linebreak': 'off',
    },
  },
  {
    // 图表与测试里的 SVG 坐标计算会用到 `any`（提示卡的 payload 结构由
    // 图表库决定，全量类型化收益有限）。
    files: ['src/components/charts/**/*.vue', 'src/**/__tests__/**/*.ts'],
    rules: {
      '@typescript-eslint/no-explicit-any': 'warn',
    },
  },
])
