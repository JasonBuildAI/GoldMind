import { defineConfig, devices } from '@playwright/test'

// 端到端测试会真的把三件事跑起来：
//   1. 一个假的 OpenAI 兼容服务（不消耗真实额度）
//   2. 真正的后端（uvicorn + SQLite）
//   3. 构建产物（vite preview，通过代理把 /api 转发给后端）
// 然后由浏览器访问第 3 个，验证整条链路。
//
// E2E_LLM=real 切到「真栈档」：不拉起假 LLM、不覆盖后端的环境变量，
// 后端沿用 backend/.env 里的真实凭证与数据源；真栈用例在 e2e-live/，
// 不设该变量时整组跳过（默认 npm run test:e2e 仍是全离线档）。

const PYTHON = process.env.E2E_PYTHON || 'python'
// 默认避开 8000：真实开发后端常年占用它，e2e 换用不常见端口，互不打扰
const API_PORT = Number(process.env.E2E_API_PORT || 8123)
const WEB_PORT = Number(process.env.E2E_WEB_PORT || 4173)
const MOCK_PORT = Number(process.env.E2E_MOCK_PORT || 8099)
const LIVE = process.env.E2E_LLM === 'real'

// 本地默认复用已安装的 Chrome（不下载 Playwright 自带浏览器）；Windows 自带 Edge，
// 没有 Chrome 时把 E2E_BROWSER 设为 msedge 也能跑。CI 的 runner 两者都没有，
// 设为 chromium 即用 `playwright install` 装好的 Chromium；留空时仍是 chrome。
// 只认识 chrome / msedge / chromium 三个值，其它值按 chromium（Playwright 默认）处理。
const BROWSER_CHANNEL = process.env.E2E_BROWSER || 'chrome'
const BROWSER_CHANNELS: Record<string, string | undefined> = {
  chrome: 'chrome',
  msedge: 'msedge',
  chromium: undefined,
}

// 离线档：假 LLM 服务 + 覆盖成 SQLite / 独立缓存的后端。
const MOCK_LLM_SERVER = {
  command: `${PYTHON} scripts/dev_mock_llm.py --port ${MOCK_PORT}`,
  cwd: '../backend',
  url: `http://127.0.0.1:${MOCK_PORT}/healthz`,
  // 一律重新拉起：复用旧进程会继续提供上一次构建的产物，
  // 导致刚改完前端却断言到旧 DOM（排查起来非常费时）。
  reuseExistingServer: false,
  timeout: 30_000,
}

const BACKEND_SERVER = {
  command: `${PYTHON} -m uvicorn app.main:app --host 127.0.0.1 --port ${API_PORT}`,
  cwd: '../backend',
  url: `http://127.0.0.1:${API_PORT}/health`,
  env: LIVE
    ? {
        // 真栈档：DATABASE_URL / 缓存目录 / LLM 凭证一律沿用 backend/.env，
        // 只放开浏览器连续加载页面才会撞到的限流（与具体被测行为无关）。
        RATE_LIMIT_AI_PER_MINUTE: '100',
        RATE_LIMIT_PER_MINUTE: '2000',
      }
    : {
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
        // 同理：一次完整跑动里浏览器要发出上百次请求（每个用例都重新加载页面），
        // 默认的 60 次/分钟会在最后一个用例（研究页）上撞出 429 ——
        // CI 没有 backend/.env，用的是默认值，因此这会表现为「本地过、CI 红」。
        // 这里显式放开，让端到端结果只取决于代码，不取决于跑在哪台机器、有没有 .env。
        RATE_LIMIT_PER_MINUTE: '2000',
      },
  // 真栈档允许复用一台已经在跑的真实后端；离线档一律重新拉起，保证种子库是新的
  reuseExistingServer: LIVE,
  timeout: 90_000,
}

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
    // 本机已安装的 Chrome / Edge 直接复用；CI 用 E2E_BROWSER=chromium 覆盖为自带 Chromium
    channel: BROWSER_CHANNELS[BROWSER_CHANNEL],
    trace: 'retain-on-failure',
  },
  projects: [
    { name: BROWSER_CHANNEL, testDir: './e2e', use: { ...devices['Desktop Chrome'] } },
    // 真栈用例：E2E_LLM != real 时用例自行 skip；跑真栈用
    //   E2E_LLM=real npx playwright test e2e-live
    { name: 'e2e-live', testDir: './e2e-live', use: { ...devices['Desktop Chrome'] } },
  ],
  webServer: [
    ...(LIVE ? [] : [MOCK_LLM_SERVER]),
    BACKEND_SERVER,
    {
      // 必须显式指定 --host 127.0.0.1：vite preview 默认绑到 localhost，
      // 在部分 Windows 环境下只监听 ::1，导致 Playwright 的就绪探测连不上。
      command: `npm run preview -- --host 127.0.0.1 --port ${WEB_PORT} --strictPort`,
      url: `http://127.0.0.1:${WEB_PORT}`,
      // preview 的 /api 与 /health 代理指向本配置拉起的后端端口（见 vite.config.ts）
      env: { VITE_PROXY_TARGET: `http://127.0.0.1:${API_PORT}` },
      reuseExistingServer: false,
      timeout: 120_000,
    },
  ],
})