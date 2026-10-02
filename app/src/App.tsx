import Footer from './layout/Footer'
import Masthead from './layout/Masthead'
import { FreshnessProvider } from './contexts/FreshnessContext'
import { GoldDataProvider } from './contexts/GoldDataContext'
import Conclusion from './sections/Conclusion'
import DataMethods from './sections/DataMethods'
import Drivers from './sections/Drivers'
import Market from './sections/Market'
import Quant from './sections/Quant'
import Strategy from './sections/Strategy'
import { TESTIDS } from './testids'

/**
 * 看板阅读顺序（自上而下，唯一入口）：
 *   报头（字标 + 锚点导航 + 今日速览 + 数据新鲜度条）
 *   → 今日结论 → 行情 → 驱动（看涨 / 看跌 / 消息 / 机构）
 *   → 量化预测 → 投资策略 → 数据与方法 → 页脚
 */
function App() {
  return (
    <GoldDataProvider>
      <FreshnessProvider>
        <a className="skip-link no-print" href="#main">
          跳到主要内容
        </a>

        <Masthead />

        <main id="main">
          <div className="wrap" data-testid={TESTIDS.app}>
            <Conclusion />
            <Market />
            <Drivers />
            <Quant />
            <Strategy />
            <DataMethods />
          </div>
        </main>

        <Footer />
      </FreshnessProvider>
    </GoldDataProvider>
  )
}

export default App