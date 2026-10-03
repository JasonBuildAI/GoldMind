/**
 * 真实内容截图：把一个**正在运行的真实栈**里各区块拍下来，供 README 引用。
 *
 * 为什么要有这个脚本（而不是手动截图）：
 *   1. 手动截图无法复核 —— 没人知道那张图是哪天的代码、哪天的数据；
 *   2. README 需要「图里有真实内容」这件事能被机器判一遍。本脚本在保存前会检查
 *      每个区块里必须有实质文字，并且**不含**空态标记（「暂无」「加载中」…），
 *      任何一条不满足就直接报错退出，不写出半张空图。
 *   3. 两个量化区块（预测 / 回测）挂在同一组尺度 tab 上，默认停在「1 日」——
 *      想拍 1 年或 1 季就必须先点 tab，否则拍到的是另一个尺度的数字。
 *
 * 拍摄前会先轮询 `/health` 的 bootstrap：只有引导阶段结束（done / disabled /
 * skipped，或各阶段都已落定）才开拍；字段缺失（旧后端）也会给出提示后继续，
 * 因为那种情况由每个区块自己的「非空 + 无空态标记」检查兜底。
 *
 * 选择器与 app/src/testids.ts 里的 TESTIDS 是同一批字符串；本文件是 .mjs，
 * 不能直接 import TS，改动选择器时两处必须同步（见 docs/20-前端设计规范.md 第八节）。
 *
 * 前置：真实后端（含真实 LLM）与前端 dev/preview 都要已经在跑。
 *   SCREENSHOT_BASE_URL  默认 http://localhost:5173
 *   SCREENSHOT_OUT       默认 <repo>/docs/images/screenshots
 *   SCREENSHOT_BROWSER   chrome（默认）/ msedge / chromium
 *
 * 默认用 `localhost` 而不是 `127.0.0.1`：Vite 开发服务器默认只监听 `::1`
 * （README 里的服务地址也是 `http://localhost:5173`），写死 IPv4 会连不上、
 * 卡在「读不到 /health」上。要拍别的地址用 SCREENSHOT_BASE_URL 覆盖。
 *
 * 用法（在 app/ 目录）：
 *   node scripts/capture_screenshots.mjs
 */
import { mkdir } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { chromium } from 'playwright'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const BASE_URL = process.env.SCREENSHOT_BASE_URL || 'http://localhost:5173'
// HERE = <repo>/app/scripts —— 默认落到仓库根的 docs/images/screenshots。
const OUT_DIR = path.resolve(HERE, process.env.SCREENSHOT_OUT || '../../docs/images/screenshots')
const BROWSER = process.env.SCREENSHOT_BROWSER || 'chrome'

// 空态标记：出现任意一个就说明这块还没内容，绝不允许写进 README。
// （个别区块里存在**如实标注**的不可用行，用 allowMarkers 逐块放行，不放行整张表的判据。）
const EMPTY_MARKERS = [
  '暂无',
  '不可用',
  '加载中',
  '正在加载',
  'AI 分析进行中',
  'AI分析进行中',
  '分析中',
  '正在读取',
  '失败',
  '数据获取失败',
  '重新抓取',
  '请稍后',
]
// 区块至少要有这么多字才算「有实质内容」
const MIN_CHARS = 60

const SHOTS = [
  // 报头是 macOS 工具条（半透明 + 吸顶），class 从 .masthead 改成 .toolbar。
  { name: 'dashboard', url: '/', selector: '.toolbar', pad: 260, minChars: 40 },
  {
    name: 'price-chart',
    url: '/',
    selector: '#market',
    minChars: 200,
    requireAll: [/美元指数/, /20\d\d-\d\d-\d\d/],
  },
  { name: 'news-analysis-up', url: '/', selector: '[data-testid="bullish-factors"]', minChars: 120 },
  { name: 'news-analysis-down', url: '/', selector: '[data-testid="bearish-factors"]', minChars: 120 },
  // 机构观点表里三家机构没有可核实的目标价，如实显示「暂无最新预测」——
  // 所以放行「暂无 / 重新抓取」，但要求表里必须有一行**带预测日期与目标价**的真实记录。
  {
    name: 'institutional-views',
    url: '/',
    selector: '#institutions',
    minChars: 200,
    allowMarkers: ['暂无', '重新抓取'],
    requireAll: ['预测日期', /20\d\d-\d\d-\d\d/, /\$\d[\d,]{2,}/],
  },
  // 策略正文里引用了一句模型的原文「所有机构预测…暂无最新预测」，属于真实内容；
  // 要求三档策略词都在，防止退化成一段空话。
  {
    name: 'investment-advice',
    url: '/',
    selector: '#strategy',
    // 这一节是全站最长的一块（三档策略 + 执行细则，约 4500 CSS px），2x 会到 3.6 MB；
    // 拍 1x 供 README 缩放显示，文字仍然逐字可读。
    scale: 1,
    minChars: 400,
    allowMarkers: ['暂无'],
    requireAll: ['保守', '均衡', '机会'],
  },
  // 块里有一行**如实标注**的「不可用原因」（正常时值是「—」），放行该词；
  // 数字下限与必含词防它退化成空壳或降级块（降级标题同样含「不可用」）。
  {
    name: 'quant-fair-value',
    url: '/',
    selector: '[data-testid="quant-fair-value"]',
    minChars: 120,
    allowMarkers: ['不可用'],
    minNumbers: 10,
    requireAll: [/公允价/, /市场价/, /R²/],
  },

  // 监测表里有一行是**如实标注**的不可用（上证溢价没有可用的免密钥接口），
  // 其余空态标记仍然照拦；另外要求表里至少有 15 个数字，防整表退化成空壳。
  {
    name: 'quant-monitor',
    url: '/',
    selector: '[data-testid="quant-monitor-table"]',
    minChars: 200,
    allowMarkers: ['不可用'],
    minNumbers: 15,
  },
  // 今日结论：一行核心观点 + 关键数字，论据与生成信息收在折叠层里。
  // 「暂无」会在机构目标价为空的表格行里如实出现，放行；数字下限防退化成空壳。
  {
    name: 'market-summary',
    url: '/',
    selector: '#conclusion',
    minChars: 300,
    allowMarkers: ['暂无', '重新分析'],
    minNumbers: 4,
    requireAll: ['今日结论', '置信度'],
  },
  // 回测评估按尺度切换：不点 tab 拍到的是默认的 1 日面板。
  {
    name: 'quant-accuracy',
    url: '/',
    selector: '[data-testid="quant-accuracy-60"]',
    tab: '1 季',
    minChars: 80,
  },
  {
    name: 'quant-prediction',
    url: '/',
    selector: '[data-testid="quant-prediction-250"]',
    tab: '1 年',
    minChars: 120,
    allowMarkers: ['不可用'],
    minNumbers: 8,
  },
  // 研究页三段分开拍（整页 main 高 4500+px，拍出来在 README 里没法看）。
  // 同上：裁决块里的「不可用原因」是固定字段行；必含「前向留出期」与日期，
  // 保证拍到的是有数字的裁决正文而不是降级说明。
  {
    name: 'research-verdict',
    url: '/research.html',
    selector: 'section.section:has([data-testid="research-verdict"])',
    minChars: 150,
    allowMarkers: ['不可用'],
    minNumbers: 8,
    requireAll: ['前向留出期', /20\d\d-\d\d-\d\d/],
  },
  {
    name: 'research-forward-window',
    url: '/research.html',
    selector: 'section.section:has([data-testid="research-forward-window"])',
    minChars: 200,
  },
  {
    name: 'research-overview',
    url: '/research.html',
    selector: 'section.section:has([data-testid="research-overview"])',
    minChars: 250,
  },
]

function assertRealContent(name, text, options = {}) {
  const compact = text.replace(/\s+/g, ' ').trim()
  if (compact.length < (options.minChars ?? MIN_CHARS)) {
    throw new Error(
      `${name}: 区块只有 ${compact.length} 个字（下限 ${options.minChars ?? MIN_CHARS}），拒绝写出空图`,
    )
  }
  const allowed = new Set(options.allowMarkers ?? [])
  for (const marker of EMPTY_MARKERS) {
    if (allowed.has(marker)) continue
    if (compact.includes(marker)) {
      throw new Error(`${name}: 区块里出现了空态标记「${marker}」，拒绝写出空图`)
    }
  }
  if (options.minNumbers) {
    const numbers = compact.match(/\d+(?:\.\d+)?/g) ?? []
    if (numbers.length < options.minNumbers) {
      throw new Error(
        `${name}: 区块只有 ${numbers.length} 个数字（下限 ${options.minNumbers}），拒绝写出空表`,
      )
    }
  }
  for (const pattern of options.requireAll ?? []) {
    const probe = pattern instanceof RegExp ? pattern : new RegExp(pattern)
    if (!probe.test(compact)) {
      throw new Error(`${name}: 区块里缺了真实内容证据 ${pattern}，拒绝写出空图`)
    }
  }
}

/** 轮询 /health 的 bootstrap，直到引导阶段结束。 */
async function waitForBootstrap() {
  const deadline = Date.now() + 10 * 60 * 1000
  let last = '（读不到 /health）'
  while (Date.now() < deadline) {
    let bootstrap = null
    try {
      const resp = await fetch(new URL('/health', BASE_URL))
      if (resp.ok) bootstrap = (await resp.json()).bootstrap ?? null
    } catch {
      bootstrap = null
    }
    if (bootstrap) {
      last = `${bootstrap.status}（步骤 ${bootstrap.step?.index ?? '?'}/${bootstrap.step?.total ?? '?'}）`
      const phases = bootstrap.phases ?? []
      const settled = ['done', 'disabled', 'skipped', 'failed'].includes(bootstrap.status)
      const phasesSettled =
        phases.length > 0 &&
        phases.every((phase) => ['done', 'skipped', 'failed'].includes(phase.status))
      if (settled || phasesSettled) {
        console.log(`[bootstrap] ${last}`)
        if (bootstrap.status === 'failed') {
          console.warn('[bootstrap] 引导失败，继续拍摄；内容检查会兜底')
        }
        return
      }
    }
    await new Promise((resolve) => setTimeout(resolve, 3000))
  }
  throw new Error(`等待 /health bootstrap 完成超时（最后状态：${last}）`)
}

/** Windows 上偶见瞬时占用（杀软 / 索引 / 同步）：写图重试三次再上报失败。 */
async function saveWithRetry(write, file) {
  let lastError
  for (let attempt = 1; attempt <= 3; attempt += 1) {
    try {
      await write()
      return
    } catch (error) {
      lastError = error
      await new Promise((resolve) => setTimeout(resolve, 800 * attempt))
    }
  }
  throw lastError
}

async function main() {
  await mkdir(OUT_DIR, { recursive: true })
  await waitForBootstrap()

  const browser = await chromium.launch({ channel: BROWSER })
  // 每个缩放档一个上下文：默认 2x（文字锐利），超长区块用 1x 控制体积。
  const states = new Map()
  const stateFor = async (scale) => {
    if (!states.has(scale)) {
      const context = await browser.newContext({
        viewport: { width: 1440, height: 1000 },
        deviceScaleFactor: scale,
        locale: 'zh-CN',
      })
      states.set(scale, { page: await context.newPage(), url: null, tab: null })
    }
    return states.get(scale)
  }
  const problems = []

  for (const shot of SHOTS) {
    try {
      const state = await stateFor(shot.scale ?? 2)
      const { page } = state
      const url = new URL(shot.url, BASE_URL).toString()
      if (url !== state.url) {
        await page.goto(url, { waitUntil: 'networkidle', timeout: 60000 })
        state.url = url
        state.tab = null
      }
      if (shot.tab && shot.tab !== state.tab) {
        // 预测与回测共用一组尺度 tab；不点就会拍到默认的 1 日。
        await page.getByRole('tab', { name: shot.tab, exact: true }).last().click()
        state.tab = shot.tab
        await page.waitForTimeout(400)
      }
      const target = page.locator(shot.selector).first()
      await target.waitFor({ state: 'visible', timeout: 60000 })
      // 折线图与表格有入场动画/延迟渲染，等一拍再拍。
      await page.waitForTimeout(1200)

      const text = await target.innerText().catch(() => '')
      assertRealContent(shot.name, text, shot)

      const file = path.join(OUT_DIR, `${shot.name}.png`)
      if (shot.pad) {
        const box = await target.boundingBox()
        await saveWithRetry(
          () =>
            page.screenshot({
              path: file,
              clip: {
                x: Math.max(0, box.x - 12),
                y: Math.max(0, box.y - 12),
                width: box.width + 24,
                height: shot.pad + 24,
              },
            }),
          file,
        )
      } else {
        await saveWithRetry(() => target.screenshot({ path: file }), file)
      }
      console.log(`captured ${shot.name} (${text.replace(/\s+/g, '').length} chars)`)
    } catch (error) {
      // 任何区块失败都只记录问题、不写图；其余区块继续，最后统一非零退出。
      problems.push(`${shot.name}: ${error.message}`)
    }
  }

  await browser.close()
  if (problems.length > 0) {
    console.error('有区块没通过真实内容检查：')
    for (const problem of problems) console.error(`  - ${problem}`)
    process.exit(1)
  }
  console.log(`全部截图已写入 ${OUT_DIR}`)
}

main().catch((error) => {
  console.error(error)
  process.exit(1)
})