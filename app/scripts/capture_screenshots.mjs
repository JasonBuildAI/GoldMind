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
// 只重拍其中几张（调版式用）：`SCREENSHOT_ONLY=dashboard,quant-* node scripts/capture_screenshots.mjs`
// 按名字里的子串过滤，不给就是全拍。整轮 15 张约一分钟，改一格时不必等整轮。
const ONLY = (process.env.SCREENSHOT_ONLY || '')
  .split(',')
  .map((part) => part.trim())
  .filter(Boolean)

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
  // 首屏：整页左上裁切 = 左栏（字标 + 导航 + 今日速览 + 数据新鲜度）+ 今日结论。
  // 只拍 .toolbar（= 左栏本体）在 README 里会变成一条光秃秃的导航，所以按页面裁切；
  // 左栏内容由 extraChecks 单独把关，防止「速览 / 新鲜度」退化成加载中的空壳。
  // 今日结论也在这张图里（旧版另外拍一张 `conclusion`，与首屏内容完全重复，2026-10-03 删）——
  // 所以结论正文的必含词并到这里，别让「拍到了空壳」蒙混过关。
  {
    name: 'dashboard',
    url: '/',
    selector: '#conclusion',
    clip: { x: 0, y: 0, width: 1440, height: 1000 },
    minChars: 150,
    minNumbers: 4,
    requireAll: ['今日结论', '置信度'],
    extraChecks: [
      {
        selector: '.toolbar',
        minChars: 120,
        minNumbers: 3,
        // 速览必须已经拿到真实报价与逐块新鲜度，而不是「行情读取中…」。
        requireAll: ['今日速览', '数据新鲜度', '美元指数', /20\d\d-\d\d-\d\d/, /\$\d[\d,.]*/],
      },
    ],
  },
  // 行情：只拍顶部一段（节标题 + 两张报价卡 + 全字段表开头）。整节 2800+ CSS px，
  // 全拍在 README 里会拖成一条长图；走势图单独拍下一张。
  {
    name: 'market',
    url: '/',
    selector: '#market',
    pad: 760,
    minChars: 200,
    requireAll: [/美元指数/, /20\d\d-\d\d-\d\d/],
  },
  // 走势图收在折叠层里，先展开再元素截图（整节截图里它默认是收起的）。
  {
    name: 'price-trend',
    url: '/',
    selector: '[data-testid="market-chart"] figure.chart',
    open: '[data-testid="market-chart"]',
    minChars: 40,
    requireAll: ['纽约黄金', '交易日'],
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
  // 消息（一等板块）：只拍顶部一段（窗口 tab + 前几条），整节 1700+ CSS px 在 README 里
  // 会拖成一张长条。窗口里可能有个别「暂无」（该条没有摘要），放行；但要求有评分与时间。
  {
    name: 'messages',
    url: '/',
    selector: '#messages',
    pad: 780,
    minChars: 300,
    minNumbers: 10,
    // 节首固定文案里就有「抓不到就如实显示不可用与原因」；个别条目也可能如实标「暂无」。
    // 下限与必含词兜底：整节退化成降级说明时数字凑不够，照样报错。
    allowMarkers: ['暂无', '不可用'],
    requireAll: ['24 小时内', '重要性', '置信度', /20\d\d-\d\d-\d\d/],
  },
  // 策略正文里引用了一句模型的原文「所有机构预测…暂无最新预测」，属于真实内容；
  // 要求三档策略词都在，防止退化成一段空话。
  {
    name: 'investment-advice',
    url: '/',
    selector: '#strategy',
    // 这一节是全站最长的一块（三档策略 + 执行细则，约 3900 CSS px），2x 会到 3.6 MB；
    // 拍 1x 供 README 缩放显示，文字仍然逐字可读。裁到「执行原则」之前 ——
    // 那里是语义边界，三档策略卡是完整的，不是把某张卡切一半。
    scale: 1,
    pad: 2900,
    padToText: '执行原则',
    minChars: 400,
    // 模型正文里真实出现过「假突破…反复失败」这类句子；「暂无」来自它引用的机构目标价。
    // 放行这两个词后仍有下限与三档策略词兜底：降级成一段说明会立刻在不满足项上报错。
    allowMarkers: ['暂无', '失败'],
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
    // 裁到「模型字段与口径」折叠之前：决策与三情景是这一屏的重点，
    // 14 行因子明细表在页面里展开可得（整拍会有 3400+ CSS px）。
    pad: 1110,
    padToText: '模型字段与口径',
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
    // 只拍「还差多少个交易日」这张表（+ 下一个块的标题）：它的下一个块是「Beta 后验与 CRPS」
    // 表，而那张表当前整表是「—」（后端响应还没透出该字段）—— 这层限制写进 README 的文字
    // 说明，不摆一张全横线的表。整块的自然高度会随字号加载 / 数据换行浮动，裁在标题下沿。
    pad: 1120,
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

/**
 * 等到区块真的有内容再拍。
 *
 * 页面每 30 秒轮询一次，抓图恰好落在刷新窗口里时，区块会短暂回到「正在读取」——
 * 这不是坏数据，是时序。读一次就断言会把这种瞬态当成空图报错（2026-10-03 实测：
 * 同一条命令两次运行，一次全绿、一次在 strategy / dashboard 上误报）。
 * 所以按 1 秒一次重试整套检查，直到通过或超时；超时仍不通过才按空图处理。
 */
async function waitForRealContent(page, name, selector, shot, timeoutMs = 45000) {
  const deadline = Date.now() + timeoutMs
  for (;;) {
    const text = await page.locator(selector).first().innerText().catch(() => '')
    try {
      assertRealContent(name, text, shot)
      for (const check of shot.extraChecks ?? []) {
        const extra = await page.locator(check.selector).first().innerText().catch(() => '')
        assertRealContent(`${name} · ${check.selector}`, extra, check)
      }
      return text
    } catch (error) {
      if (Date.now() >= deadline) throw error
      await page.waitForTimeout(1000)
    }
  }
}

/**
 * 把「裁到哪里」从写死的像素数换成语义边界：在元素内部找到指定文字所在的标题，
 * 裁到它上面一点。这样内容长短变化时（LLM 每次产出的字数是变的），裁剪仍然落在
 * 段落之间，不会把某张卡切在半句上。找不到边界时回落到 shot.pad。
 *
 * `padGap` 是往回让的余量，默认 12px：块与上一块之间常常只有十几像素的间距，贴边裁会
 * 切进上一块的最后一行。让多少是逐块实测出来的 —— 研究页的「前向留出期」表就是这样
 * 被切掉 `1 年` 行的一半（2026-10-03），那一块改用 `padGap: 0` 贴边裁。
 */
async function resolvePad(target, shot) {
  if (!shot.padToText) return shot.pad
  // 边界块本身是懒渲染的（研究页的 Beta 表要等数据到），一次找不到就等一下再找 ——
  // 直接回落会悄悄换掉裁剪位置：同一块两次拍摄裁出两个高度（2026-10-03 实测）。
  for (let attempt = 0; attempt < 12; attempt += 1) {
    const pad = await target
      .evaluate((el, text, gap) => {
        const candidates = [...el.querySelectorAll('h2, h3, h4, .panel__title, summary')]
        const hit = candidates.find((node) => node.textContent.trim().startsWith(text))
        if (!hit) return null
        // 只认真正的块级容器；如果命中的是目标自身（比如整节就是 section），就退回标题。
        const block = hit.closest('.panel, .research__block, details') ?? hit
        const anchor = block === el ? hit : block
        const offset = anchor.getBoundingClientRect().top - el.getBoundingClientRect().top
        return Math.max(40, Math.round(offset) - gap)
      }, shot.padToText, shot.padGap ?? 12)
      .catch(() => null)
    if (pad !== null) return pad
    await new Promise((resolve) => setTimeout(resolve, 500))
  }
  console.warn(`[${shot.name}] 找不到裁剪边界「${shot.padToText}」，回落到 pad=${shot.pad}`)
  return shot.pad
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
      // 先冻住「时间」：页面每 30 秒轮询一次，抓图撞上刷新窗口时区块会短暂回到
      // 「正在读取 / 暂不可用」，拍出来就是空图（2026-10-03 实测：同一条命令两次
      // 运行，一次全绿一次误报）。首屏挂载时的初始加载不受影响，所以拍到的仍是
      // 真实数据，只是拍摄期间不再被下一轮刷新改写。
      await context.addInitScript(() => {
        window.setInterval = () => 0
      })
      states.set(scale, { page: await context.newPage(), url: null, tab: null })
    }
    return states.get(scale)
  }
  const problems = []

  for (const shot of SHOTS) {
    if (ONLY.length && !ONLY.some((part) => shot.name.includes(part))) continue
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
      if (shot.open) {
        // 折叠层（<details>）里的目标：先展开，元素才可见、才有内容可拍。
        await page.locator(shot.open).first().evaluate((el) => {
          el.open = true
        })
        await page.waitForTimeout(400)
      }
      const target = page.locator(shot.selector).first()
      await target.waitFor({ state: 'visible', timeout: 60000 })
      // 折线图与表格有入场动画/延迟渲染，等一拍再拍。
      await page.waitForTimeout(1200)

      // 内容检查按「等到真的有内容」来做；附加断言（如首屏的左栏）在同一次重试里检查。
      const text = await waitForRealContent(page, shot.name, shot.selector, shot)

      const file = path.join(OUT_DIR, `${shot.name}.png`)
      if (shot.clip) {
        // 整页裁切（左上角首屏）：坐标是文档坐标，与 viewport 尺寸无关。
        await saveWithRetry(() => page.screenshot({ path: file, clip: shot.clip }), file)
      } else if (shot.pad) {
        // 只拍元素顶部一段：临时把元素裁成 pad 高，拍元素本身，再恢复样式。
        // 不能用 page.screenshot 的 clip —— 区块在文档深处时它按视口坐标解释，
        // 拍出来是一条空带（2026-10-03 实测：messages 只得到 152px 高的白图）。
        // 元素截图会自己把元素滚进视口，因此对文档任意位置的区块都成立。
        const pad = await resolvePad(target, shot)
        const prev = await target.evaluate((el, height) => {
          const previous = { maxHeight: el.style.maxHeight, overflow: el.style.overflow }
          el.style.maxHeight = `${height}px`
          el.style.overflow = 'hidden'
          return previous
        }, pad)
        try {
          await saveWithRetry(() => target.screenshot({ path: file }), file)
        } finally {
          await target.evaluate((el, previous) => {
            el.style.maxHeight = previous.maxHeight
            el.style.overflow = previous.overflow
          }, prev)
        }
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
