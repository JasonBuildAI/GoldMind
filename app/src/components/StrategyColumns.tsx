import type { InvestmentStrategy } from '@/services/api'

const RISK_LABEL: Record<string, string> = {
  low: '低风险',
  medium: '中风险',
  high: '高风险',
}

/** 一行「标签 + 值」，用于入场与离场的若干条目。 */
function Row({ label, value }: { label: string; value: string }) {
  if (!value) return null
  return (
    <div>
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  )
}

/**
 * 三档策略（保守 / 均衡 / 机会）横向对照。
 *
 * 每档的字段完全同名同序 —— 读的时候可以横向比，而不是在三种卡片设计里找。
 * 窄屏按网格堆叠为单栏（lg 断点以上才并排）。
 */
export default function StrategyColumns({
  strategies,
  testId,
}: {
  strategies: InvestmentStrategy[]
  testId?: string
}) {
  return (
    <div className="grid gap-8 lg:grid-cols-3" data-testid={testId}>
      {strategies.map((strategy) => (
        <article key={strategy.type} className="panel">
          <h3 className="strategy__title">{strategy.title}</h3>
          <p className="strategy__lead">{strategy.description}</p>

          <dl className="strategy__facts">
            <div>
              <dt>仓位</dt>
              <dd>{strategy.allocation || '—'}</dd>
            </div>
            <div>
              <dt>时间框架</dt>
              <dd>{strategy.timeframe || '—'}</dd>
            </div>
            <div>
              <dt>风险</dt>
              <dd>{RISK_LABEL[strategy.risk_level] ?? '未知'}</dd>
            </div>
          </dl>

          <div className="strategy__block">
            <h4>入场</h4>
            <dl className="strategy__rows">
              <Row label="当前评估" value={strategy.entry_strategy?.current_price_assessment ?? ''} />
              <Row label="建议区间" value={strategy.entry_strategy?.recommended_entry_range ?? ''} />
              <Row label="时机" value={strategy.entry_strategy?.entry_timing ?? ''} />
              <Row label="建仓方式" value={strategy.entry_strategy?.position_building ?? ''} />
            </dl>
          </div>

          <div className="strategy__block">
            <h4>离场</h4>
            <dl className="strategy__rows">
              <Row label="止盈目标" value={strategy.exit_strategy?.profit_target ?? ''} />
              <Row label="止损" value={strategy.exit_strategy?.stop_loss ?? ''} />
              <Row label="再平衡" value={strategy.exit_strategy?.rebalancing_trigger ?? ''} />
            </dl>
          </div>

          {strategy.pros.length > 0 || strategy.cons.length > 0 ? (
            <div className="strategy__block">
              <h4>优缺点</h4>
              {strategy.pros.length > 0 ? (
                <>
                  <p className="strategy__label">优点</p>
                  <ul className="strategy__list">
                    {strategy.pros.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                </>
              ) : null}
              {strategy.cons.length > 0 ? (
                <>
                  <p className="strategy__label">缺点</p>
                  <ul className="strategy__list">
                    {strategy.cons.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                </>
              ) : null}
            </div>
          ) : null}

          {strategy.suitable_for.length > 0 ? (
            <div className="strategy__block">
              <h4>适合</h4>
              <ul className="strategy__list">
                {strategy.suitable_for.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
          ) : null}

          {strategy.execution_steps.length > 0 ? (
            <div className="strategy__block">
              <h4>执行步骤</h4>
              <ol className="strategy__list">
                {strategy.execution_steps.map((step, index) => (
                  <li key={`${index}-${step}`}>{step}</li>
                ))}
              </ol>
            </div>
          ) : null}
        </article>
      ))}
    </div>
  )
}
