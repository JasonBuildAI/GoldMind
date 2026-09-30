import Footer from './layout/Footer'
import Masthead from './layout/Masthead'
import { GoldDataProvider } from './contexts/GoldDataContext'
import Market from './sections/Market'
import Factors from './sections/Factors'
import Institutions from './sections/Institutions'
import InvestmentAdvice from './sections/InvestmentAdvice'
import Summary from './sections/Summary'

function App() {
  return (
    <GoldDataProvider>
      <a className="skip-link no-print" href="#main">
        跳到主要内容
      </a>

      <Masthead />

      <main id="main">
        <div className="wrap">
          <Market />
          <Factors />
          <Institutions />
        </div>

        {/* 迁移期容器：下面两个区块还在旧版深色主题上，重建一个就移出一个；
            全部迁移完后删除 .legacy-dark（见 docs/specs/2026-09-30-前端表现层重构-plan.md）。 */}
        <div className="legacy-dark">
          <div className="wrap">
            <div id="strategy">
              <InvestmentAdvice />
            </div>

            <div id="conclusion">
              <Summary />
            </div>
          </div>
        </div>
      </main>

      <Footer />
    </GoldDataProvider>
  )
}

export default App
