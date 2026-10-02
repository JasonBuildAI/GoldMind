import Footer from './layout/Footer'
import Masthead from './layout/Masthead'
import { GoldDataProvider } from './contexts/GoldDataContext'
import Market from './sections/Market'
import Factors from './sections/Factors'
import Institutions from './sections/Institutions'
import Messages from './sections/Messages'
import Strategy from './sections/Strategy'
import Quant from './sections/Quant'
import Conclusion from './sections/Conclusion'

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
          <Messages />
          <Strategy />
          <Quant />
          <Conclusion />
        </div>
      </main>

      <Footer />
    </GoldDataProvider>
  )
}

export default App
