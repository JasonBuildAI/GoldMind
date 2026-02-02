import { TrendingUp } from 'lucide-react';

export default function Footer() {
  const currentYear = new Date().getFullYear();

  const dataSources = [
    '实时金价数据 - 腾讯财经API（纽约黄金期货GC）',
    '实时美元指数 - 新浪财经API（ICE美元指数DXY）',
    '智谱AI (Zhipu AI) - 实时新闻搜索与分析',
    'DeepSeek LLM - 市场综合分析与投资建议',
    '高盛 (Goldman Sachs) - 机构预测',
    '瑞银 (UBS) - 机构预测',
    '摩根士丹利 (Morgan Stanley) - 机构预测',
    '花旗 (Citi) - 机构预测'
  ];

  return (
    <footer className="py-12 px-4 sm:px-6 lg:px-8 border-t border-gray-800">
      <div className="max-w-7xl mx-auto">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8 mb-8">
          {/* Brand */}
          <div>
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-amber-500/20 to-amber-600/10 flex items-center justify-center">
                <TrendingUp className="w-5 h-5 text-amber-400" />
              </div>
              <div>
                <h3 className="text-lg font-bold text-white">黄金市场分析</h3>
                <p className="text-xs text-gray-500">Gold Market Analysis</p>
              </div>
            </div>
            <p className="text-gray-400 text-sm leading-relaxed">
              AI驱动的智能黄金市场分析平台，
              整合实时数据、AI新闻抓取与深度学习分析，
              为投资者提供专业的市场洞察与个性化投资建议。
            </p>
          </div>

          {/* Data Sources */}
          <div>
            <h4 className="text-white font-semibold mb-4">数据来源</h4>
            <ul className="space-y-2">
              {dataSources.map((source) => (
                <li key={source} className="text-gray-400 text-sm flex items-center gap-2">
                  <div className="w-1.5 h-1.5 rounded-full bg-amber-400" />
                  {source}
                </li>
              ))}
            </ul>
          </div>

          {/* Disclaimer */}
          <div>
            <h4 className="text-white font-semibold mb-4">免责声明</h4>
            <p className="text-gray-400 text-sm leading-relaxed">
              本网站内容仅供参考，不构成投资建议。
              投资有风险，入市需谨慎。
              过往表现不代表未来收益。
            </p>
          </div>
        </div>

        {/* Bottom Bar */}
        <div className="pt-8 border-t border-gray-800 flex flex-col sm:flex-row items-center justify-between gap-4">
          <p className="text-gray-500 text-sm">
            © {currentYear} 黄金市场深度分析. All rights reserved.
          </p>
          <p className="text-gray-600 text-xs">
            数据更新时间: {new Date().toLocaleDateString('zh-CN', { year: 'numeric', month: 'long', day: 'numeric' })}
          </p>
        </div>
      </div>
    </footer>
  );
}
