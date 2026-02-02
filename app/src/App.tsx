import Hero from './sections/Hero';
import PriceChart from './sections/PriceChart';
import BullishFactors from './sections/BullishFactors';
import BearishFactors from './sections/BearishFactors';
import InstitutionalViews from './sections/InstitutionalViews';
import InvestmentAdvice from './sections/InvestmentAdvice';
import Summary from './sections/Summary';
import Footer from './sections/Footer';
import { GoldDataProvider } from './contexts/GoldDataContext';
import './App.css';

function App() {
  return (
    <GoldDataProvider>
      <div className="min-h-screen bg-[#0D0B08]">
      {/* Navigation */}
      <nav className="fixed top-0 left-0 right-0 z-50 bg-[#0D0B08]/80 backdrop-blur-md border-b border-gray-800/50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-amber-500/20 to-amber-600/10 flex items-center justify-center">
                <span className="text-lg font-bold gold-text">G</span>
              </div>
              <span className="text-white font-semibold hidden sm:block">黄金市场分析</span>
            </div>
            <div className="flex items-center gap-6">
              <a href="#analysis" className="text-gray-400 hover:text-amber-400 text-sm transition-colors">分析</a>
              <a href="#factors" className="text-gray-400 hover:text-amber-400 text-sm transition-colors">因素</a>
              <a href="#advice" className="text-gray-400 hover:text-amber-400 text-sm transition-colors">建议</a>
              <a href="#summary" className="text-gray-400 hover:text-amber-400 text-sm transition-colors">总结</a>
            </div>
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <main>
        <div className="pt-16">
          <Hero />
        </div>
        
        <div id="analysis">
          <PriceChart />
        </div>
        
        <div id="factors">
          <BullishFactors />
          <BearishFactors />
        </div>
        
        <InstitutionalViews />
        
        <div id="advice">
          <InvestmentAdvice />
        </div>
        
        <div id="summary">
          <Summary />
        </div>
      </main>

      <Footer />
    </div>
    </GoldDataProvider>
  );
}

export default App;
