import { defineConfig, devices } from '@playwright/test'

// 端到端测试会真的把三件事跑起来：
//   1. 一个假的 OpenAI 兼容服务（不消耗真实额度）
//   2. 真正的后端（uvicorn + SQLite）
//   3. 构建产物（vite preview，通过代理把 /api 转发给后端）
// 然后由浏览器访问第 3 个，验证整条链路。

const PYTHON = process.env.E2E_PYTHON || 'python'
const API_PORT = Number(process.env.E2E_API_PORT || 8000)
const WEB_PORT = Number(process.env.E2E_WEB_PORT || 4173)
const MOCK_PORT = Number(process.env.E2E_MOCK_PORT || 8099)

// 本地默认复用已安装的 Chrome（不下载 Playwright 自带浏览器）。
// CI 的 runner 没有 Chrome，把 E2E_BROWSER 设为 chromium 即用 `playwright install`
// 装好的 Chromium；留空时仍是 chrome。
const BROWSER_CHANNEL = process.env.E2E_BROWSER || 'chrome'

export default defineConfig({
  testDir: './e2e',
  timeout: 90_000,
  expect: { timeout: 20_000 },
  fullyParallel: false,
  workers: 1,
  reporter: [['list']],
  globalSetup: './e2e/global-setup.ts',
  use: {
    baseURL: `http://127.0.0.1:${WEB_PORT}`,
    // 本机已安装 Chrome，直接复用；CI 用 E2E_BROWSER=chromium 覆盖
    channel: BROWSER_CHANNEL === 'chrome' ? 'chrome' : undefined,
    trace: 'retain-on-failure',
  },
  projects: [{ name: 'chrome', use: { ...devices['Desktop Chrome'] } }],
  webServer: [
    {
      command: `${PYTHON} scripts/dev_mock_llm.py --port ${MOCK_PORT}`,
      cwd: '../backend',
      url: `http://127.0.0.1:${MOCK_PORT}/healthz`,
      // 一律重新拉起：复用旧进程会继续提供上一次构建的产物，
      // 导致刚改完前端却断言到旧 DOM（排查起来非常费时）。
      reuseExistingServer: false,
      timeout: 30_000,
    },
    {
      command: `${PYTHON} -m uvicorn app.main:app --host 127.0.0.1 --port ${API_PORT}`,
      cwd: '../backend',
      url: `http://127.0.0.1:${API_PORT}/health`,
      env: {
        // 覆盖 backend/.env：用 SQLite、独立缓存目录与假 LLM，
        // 绝不触碰真实凭证与外部服务
        DATABASE_URL: 'sqlite:///./e2e.db',
        CACHE_DIR: './e2e-cache',
        SCHEDULER_ENABLED: 'false',
        LLM_API_KEY: 'e2e-mock-key',
        LLM_BASE_URL: `http://127.0.0.1:${MOCK_PORT}/v1`,
        LLM_MODEL: 'e2e-mock-model',
        LLM_PROVIDER: 'e2e',
        // 搜索默认就是关的；这里显式写死，避免误改默认值后 e2e 去打真实搜索端点
        LLM_SEARCH_ENABLED: 'false',
        // 前端 e2e 会在一次跑动里连续触发多次分析（远超默认的 6 次/分钟）。
        // 那个上限保护的是真实额度，这里打的是假 LLM，放开以消除与被测行为无关的 429。
        RATE_LIMIT_AI_PER_MINUTE: '100',
      },
      reuseExistingServer: false,
      timeout: 90_000,
    },
    {
      // 必须显式指定 --host 127.0.0.1：vite preview 默认绑到 localhost，
      // 在部分 Windows 环境下只监听 ::1，导致 Playwright 的就绪探测连不上。
      command: `npm run preview -- --host 127.0.0.1 --port ${WEB_PORT} --strictPort`,
      url: `http://127.0.0.1:${WEB_PORT}`,
      reuseExistingServer: false,
      timeout: 120_000,
    },
  ],
})
