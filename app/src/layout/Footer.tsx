import { modelLabel, useAiConfig } from '@/hooks/useAiConfig'

// 只列真实存在的数据来源。机构名称不是数据源 —— 机构观点由模型基于公开新闻整理，
// 这一句必须在页脚说清楚（见 docs/20-前端设计规范.md 第六节）。
const DATA_SOURCES = [
  '实时金价：腾讯财经（纽约黄金期货 GC）',
  '实时美元指数：新浪财经（ICE 美元指数 DXY）',
  '新闻：RSS 源（默认 FXStreet / MarketWatch / CNBC / WSJ，可用 NEWS_RSS_SOURCES 配置）',
]

export default function Footer() {
  const aiConfig = useAiConfig()

  return (
    <footer className="footer">
      <div className="wrap grid gap-8 sm:grid-cols-3">
        <section aria-labelledby="footer-sources">
          <h2 id="footer-sources">数据来源</h2>
          <ul>
            {DATA_SOURCES.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </section>

        <section aria-labelledby="footer-model">
          <h2 id="footer-model">分析模型</h2>
          <p style={{ margin: '0 0 8px' }}>模型：{modelLabel(aiConfig)}</p>
          <p style={{ margin: 0 }}>
            分析结果由大模型基于最近 24 小时的公开新闻与行情数据生成；机构观点为模型整理，
            可能滞后或不准确。联网搜索不可用时回退数据库与 RSS 新闻，不编造数据。
          </p>
        </section>

        <section aria-labelledby="footer-disclaimer">
          <h2 id="footer-disclaimer">免责声明</h2>
          <p style={{ margin: 0 }}>
            本页面内容仅供参考，不构成投资建议。投资有风险，入市需谨慎。过往表现不代表未来收益。
          </p>
        </section>
      </div>

      <div className="wrap footer__bottom">GoldMind · MIT License</div>
    </footer>
  )
}
