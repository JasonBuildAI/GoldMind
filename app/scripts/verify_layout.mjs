/**
 * 页面自检：在真实浏览器里核对版式判据（配套 docs/20-前端设计规范.md 第四、九节）。
 *
 * 为什么要有这个脚本：单元测试跑在 happy-dom 里，**没有排版引擎** ——
 * 「整页横向滚动」这类问题它在结构上就看不见（本轮实测踩到两次：图表没清
 * `figure` 的默认 40px 外边距、栅格子项没有 `min-width: 0`）。本脚本实测：
 *   - 1440×900 与 390×844 两档无横向溢出（越界元素点名，排除刻意横向滚动的表格）；
 *   - 两栏壳铺满视口：左栏吸顶 + 右侧发丝线，内容区吃掉剩余宽度；窄屏落成单栏；
 *   - 设计令牌真的生效（窗口底、侧边栏底、卡片圆角 / 发丝线 / 阴影）；
 *   - 没有装饰性渐变、发光、文字阴影；
 *   - 阅读顺序与锚点可达；正文与次要文字的对比度 ≥ 4.5:1。
 *
 * 前置：真实栈在跑（后端 + 前端）。跑法（在 app/ 目录）：
 *   node scripts/verify_layout.mjs
 * 可选：SCREENSHOT_BASE_URL 覆盖地址、SCREENSHOT_BROWSER=chrome|msedge|chromium。
 *
 * 默认用 `localhost` 而不是 `127.0.0.1`：Vite 开发服务器默认只监听 `::1`
 * （README 里的服务地址也是 `http://localhost:5173`），写死 IPv4 会连不上。
 *
 * 只读：不改任何文件。任何一条不满足就以非零码退出并逐条打印。
 */
import { chromium } from 'playwright'

const BASE_URL = process.env.SCREENSHOT_BASE_URL || 'http://localhost:5173'
const BROWSER = process.env.SCREENSHOT_BROWSER || 'chrome'

const VIEWPORTS = [
  { name: '1440x900', width: 1440, height: 900 },
  { name: '390x844', width: 390, height: 844 },
]

const SECTION_ORDER = [
  'conclusion',
  'market',
  'drivers',
  'quant',
  'strategy',
  'data-methods',
]

const problems = []

function check(condition, message) {
  if (!condition) problems.push(message)
}

async function checkPage(page, url, label) {
  await page.goto(new URL(url, BASE_URL).toString(), { waitUntil: 'networkidle', timeout: 60000 })
  await page.waitForTimeout(1500)

  // 1. 横向溢出：文档宽度不得超过视口
  const overflow = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth,
  }))
  check(
    overflow.scrollWidth <= overflow.clientWidth + 1,
    `${label}: 横向溢出 ${overflow.scrollWidth} > ${overflow.clientWidth}`,
  )

  // 2. 溢出元素点名（排除刻意横向滚动的表格容器）
  const offenders = await page.evaluate(() => {
    const bad = []
    for (const el of document.querySelectorAll('body *')) {
      const rect = el.getBoundingClientRect()
      if (rect.width === 0) continue
      if (rect.right > document.documentElement.clientWidth + 1) {
        if (el.closest('.table-scroll')) continue
        bad.push(`${el.tagName.toLowerCase()}.${el.className?.toString().slice(0, 40)}`)
      }
    }
    return [...new Set(bad)].slice(0, 6)
  })
  check(offenders.length === 0, `${label}: 越界元素 ${offenders.join(' | ')}`)

  // 3. 设计令牌生效：左栏是 macOS 侧边栏（浅一档的底 + 右侧发丝线），
  //    卡片有圆角与发丝线，整页是两栏铺满
  const tokens = await page.evaluate(() => {
    const root = getComputedStyle(document.documentElement)
    const shell = document.querySelector('.app-shell')
    const sidebar = document.querySelector('.toolbar')
    const main = document.querySelector('.app-main')
    const panel = document.querySelector('.panel')
    const sidebarStyle = sidebar ? getComputedStyle(sidebar) : null
    return {
      bg: root.getPropertyValue('--bg').trim(),
      separator: root.getPropertyValue('--separator').trim(),
      sidebarBg: sidebarStyle?.backgroundColor ?? null,
      sidebarFilter: sidebarStyle?.backdropFilter ?? null,
      sidebarBorderRight: sidebarStyle?.borderRightWidth ?? null,
      sidebarPosition: sidebarStyle?.position ?? null,
      shellColumns: shell ? getComputedStyle(shell).gridTemplateColumns : null,
      shellWidth: shell ? Math.round(shell.getBoundingClientRect().width) : null,
      mainWidth: main ? Math.round(main.getBoundingClientRect().width) : null,
      viewport: window.innerWidth,
      panelRadius: panel ? getComputedStyle(panel).borderRadius : null,
      panelBorder: panel ? getComputedStyle(panel).borderTopWidth : null,
      panelShadow: panel ? getComputedStyle(panel).boxShadow : null,
    }
  })
  check(tokens.bg === '#f2f2f7', `${label}: --bg 不是 macOS 窗口底（读到 ${tokens.bg}）`)
  check(tokens.separator === '#d8d8de', `${label}: --separator 不对（读到 ${tokens.separator}）`)
  check(
    /^rgb\(247, 247, 249\)|^rgba\(247, 247, 249|^rgba\(251, 251, 253/.test(tokens.sidebarBg ?? ''),
    `${label}: 左栏底色不是侧边栏色（读到 ${tokens.sidebarBg}）`,
  )
  check(
    /blur/.test(tokens.sidebarFilter ?? ''),
    `${label}: 左栏没有背景模糊（读到 ${tokens.sidebarFilter}）`,
  )
  check(tokens.sidebarPosition === 'sticky', `${label}: 左栏不是吸顶（读到 ${tokens.sidebarPosition}）`)
  check(tokens.panelRadius === '8px', `${label}: 卡片圆角不是 8px（读到 ${tokens.panelRadius}）`)
  // 两栏时左栏右侧有发丝线；窄屏落成单栏后是底边线（见 base.css）
  if (tokens.viewport > 960) {
    check(
      Number.parseFloat(tokens.sidebarBorderRight ?? '0') > 0,
      `${label}: 左栏没有右侧发丝线`,
    )
  }
  // 发丝线是 1px CSS 像素；在 2x 设备像素比下计算值是 0.666667px，按区间判
  const borderWidth = Number.parseFloat(tokens.panelBorder ?? '0')
  check(
    borderWidth >= 0.5 && borderWidth <= 2,
    `${label}: 卡片发丝线宽度异常（读到 ${tokens.panelBorder}）`,
  )
  check(tokens.panelShadow !== 'none', `${label}: 卡片没有阴影（读到 ${tokens.panelShadow}）`)
  // 铺满：内容区吃掉左栏之外的全部宽度（宽屏下两栏）
  if (tokens.viewport > 960) {
    check(
      tokens.shellWidth === tokens.viewport,
      `${label}: 两栏壳没有铺满视口（壳 ${tokens.shellWidth} / 视口 ${tokens.viewport}）`,
    )
    check(
      tokens.mainWidth > 700,
      `${label}: 内容区太窄（${tokens.mainWidth}px），两栏没生效`,
    )
  } else {
    check(
      tokens.shellColumns?.split(' ').length === 1,
      `${label}: 窄屏没有落成单栏（读到 ${tokens.shellColumns}）`,
    )
  }

  // 4. 没有装饰性渐变与发光（工具条的 backdrop-filter 是唯一允许的模糊）
  const decorative = await page.evaluate(() => {
    const bad = []
    for (const el of document.querySelectorAll('body *')) {
      const style = getComputedStyle(el)
      const bg = style.backgroundImage
      if (bg && bg !== 'none' && /gradient/.test(bg)) {
        bad.push(`gradient on ${el.tagName.toLowerCase()}.${el.className?.toString().slice(0, 30)}`)
      }
      if (style.filter && style.filter !== 'none' && /blur|drop-shadow/.test(style.filter)) {
        bad.push(`filter on ${el.tagName.toLowerCase()}.${el.className?.toString().slice(0, 30)}`)
      }
      if (style.textShadow && style.textShadow !== 'none') {
        bad.push(`text-shadow on ${el.tagName.toLowerCase()}`)
      }
    }
    return [...new Set(bad)].slice(0, 6)
  })
  check(decorative.length === 0, `${label}: 出现装饰性渐变/发光 ${decorative.join(' | ')}`)

  // 5. 阅读顺序与锚点
  const order = await page.evaluate(
    (ids) =>
      ids.map((id) => {
        const node = document.getElementById(id)
        if (!node) return -1
        return [...document.querySelectorAll('*')].indexOf(node)
      }),
    SECTION_ORDER,
  )
  if (url === '/') {
    check(!order.includes(-1), `${label}: 缺节 ${JSON.stringify(order)}`)
    check(
      JSON.stringify(order) === JSON.stringify([...order].sort((a, b) => a - b)),
      `${label}: 阅读顺序不对 ${JSON.stringify(order)}`,
    )
    const missingAnchors = await page.evaluate(() =>
      [...document.querySelectorAll('nav a[href^="#"]')]
        .map((a) => a.getAttribute('href').slice(1))
        .filter((id) => !document.getElementById(id)),
    )
    check(missingAnchors.length === 0, `${label}: 导航锚点不可达 ${missingAnchors.join(',')}`)
  }

  // 6. 文字对比度：抽查正文与次要文字（白底 4.5:1）
  const contrast = await page.evaluate(() => {
    const luminance = (rgb) => {
      const [r, g, b] = rgb.map((v) => {
        const c = v / 255
        return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4
      })
      return 0.2126 * r + 0.7152 * g + 0.0722 * b
    }
    const parse = (value) => (value.match(/\d+(\.\d+)?/g) ?? []).slice(0, 3).map(Number)
    const ratio = (fg, bg) => {
      const l1 = luminance(fg)
      const l2 = luminance(bg)
      const [hi, lo] = l1 > l2 ? [l1, l2] : [l2, l1]
      return (hi + 0.05) / (lo + 0.05)
    }
    const out = []
    for (const sel of ['.brief__line', '.section__intro', '.panel__meta', '.provenance']) {
      const el = document.querySelector(sel)
      if (!el) continue
      const style = getComputedStyle(el)
      // 底色向上找到第一个不透明的背景
      let bg = 'rgb(255, 255, 255)'
      let node = el
      while (node) {
        const value = getComputedStyle(node).backgroundColor
        if (value && !/rgba\(0, 0, 0, 0\)|transparent/.test(value)) {
          bg = value
          break
        }
        node = node.parentElement
      }
      out.push({ sel, ratio: Number(ratio(parse(style.color), parse(bg)).toFixed(2)) })
    }
    return out
  })
  for (const item of contrast) {
    check(item.ratio >= 4.5, `${label}: ${item.sel} 对比度 ${item.ratio} < 4.5`)
  }

  return { overflow, tokens, contrast, offenders }
}

async function main() {
  const browser = await chromium.launch({ channel: BROWSER })
  const report = {}

  for (const viewport of VIEWPORTS) {
    const context = await browser.newContext({
      viewport: { width: viewport.width, height: viewport.height },
      locale: 'zh-CN',
    })
    const page = await context.newPage()
    const errors = []
    page.on('pageerror', (error) => errors.push(error.message))

    report[`dashboard@${viewport.name}`] = await checkPage(page, '/', `dashboard@${viewport.name}`)
    report[`research@${viewport.name}`] = await checkPage(
      page,
      '/research.html',
      `research@${viewport.name}`,
    )
    check(errors.length === 0, `${viewport.name}: 未捕获异常 ${errors.join(' | ')}`)
    await context.close()
  }

  await browser.close()

  console.log(JSON.stringify(report, null, 2))
  if (problems.length > 0) {
    console.error('\n页面自检未通过：')
    for (const problem of problems) console.error(`  - ${problem}`)
    process.exit(1)
  }
  console.log('\n页面自检通过：两档视口无横向溢出、无装饰性渐变/发光、令牌生效、对比度达标、锚点可达。')
}

main().catch((error) => {
  console.error(error)
  process.exit(1)
})
