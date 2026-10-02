import StateBlock from '@/components/StateBlock'
import DataTable, { type Column } from '@/components/DataTable'
import { displayStamp, formatPercent, formatShare, formatUsd } from '@/lib/format'
import type { QuantDecomposition, QuantDecompositionBlock } from '@/services/api'
import { fieldTestId, TESTIDS } from '@/testids'
import { num } from './shared'

const field = fieldTestId

/**
 * 公允价分解：把市场价拆成宏观锚、需求溢价、风险溢价与情绪残差。
 *
 * 一行结论 + 关键数字在最上；四块构成与驱动因子进表格，数字都由后端给出。
 */
export default function FairValue({ decomposition }: { decomposition: QuantDecomposition }) {
  if (decomposition.status !== 'ok') {
    return (
      <StateBlock
        kind="unavailable"
        testId="quant-fair-value-unavailable"
        title="公允价值分解不可用"
        detail={
          decomposition.reason ??
          '回归样本或回归量不足。这里不显示编出来的公允价 —— 宁可只给市场价。'
        }
      />
    )
  }

  const columns: ReadonlyArray<Column<QuantDecompositionBlock>> = [
    {
      key: 'name',
      header: '分块',
      render: (block) => (
        <>
          <span data-testid={field('fair_value.blocks.name')}>{block.name}</span>
          <span className="note" data-testid={field('fair_value.blocks.key')}>
            {block.key}
          </span>
        </>
      ),
    },
    {
      key: 'usd',
      header: '美元',
      numeric: true,
      render: (block) => <span data-testid={field('fair_value.blocks.usd')}>{formatUsd(block.usd)}</span>,
    },
    {
      key: 'share',
      header: '占比',
      numeric: true,
      render: (block) => (
        <span data-testid={field('fair_value.blocks.share_pct')}>
          {block.share_pct === null ? '—' : formatShare(block.share_pct, 1)}
        </span>
      ),
    },
    {
      key: 'drivers',
      header: '驱动',
      render: (block) =>
        block.drivers.length === 0 ? (
          '—'
        ) : (
          <ul className="point-list">
            {block.drivers.map((driver) => (
              <li key={driver.key}>
                <span data-testid={field('fair_value.blocks.drivers.name')}>{driver.name}</span>
                <span className="note" data-testid={field('fair_value.blocks.drivers.key')}>
                  {driver.key}
                </span>
                <span className="num" data-testid={field('fair_value.blocks.drivers.log_contribution')}>
                  {num(driver.log_contribution)}
                </span>
              </li>
            ))}
          </ul>
        ),
    },
  ]

  return (
    <div className="space-y-6" data-testid={TESTIDS.quantFairValue}>
      <p className="section__conclusion">
        市场价 <span className="num">{formatUsd(decomposition.market_price)}</span>，公允价{' '}
        <span className="num">{formatUsd(decomposition.fair_value)}</span>，偏离{' '}
        <span data-testid={field('fair_value.deviation_pct')}>
          {decomposition.deviation_pct === null
            ? '—'
            : formatPercent(decomposition.deviation_pct * 100)}
        </span>
        ；回归样本 <span data-testid={field('fair_value.samples')}>{decomposition.samples}</span> 个，
        拟合 R² <span data-testid={field('fair_value.r2')}>{num(decomposition.r2)}</span>。
      </p>

      <dl className="metrics">
        <div>
          <dt>市场价</dt>
          <dd className="num" data-testid={field('fair_value.market_price')}>
            {formatUsd(decomposition.market_price)}
          </dd>
        </div>
        <div>
          <dt>公允价</dt>
          <dd className="num" data-testid={field('fair_value.fair_value')}>
            {formatUsd(decomposition.fair_value)}
          </dd>
        </div>
        <div>
          <dt>偏离度</dt>
          <dd data-testid={field('fair_value.deviation_pct')}>
            {decomposition.deviation_pct === null
              ? '—'
              : formatPercent(decomposition.deviation_pct * 100)}
          </dd>
        </div>
        <div>
          <dt>拟合 R²</dt>
          <dd data-testid={field('fair_value.r2')}>{num(decomposition.r2)}</dd>
        </div>
        <div>
          <dt>口径</dt>
          <dd>
            <span data-testid={field('fair_value.basis_label')}>{decomposition.basis_label}</span>
            <span className="note" data-testid={field('fair_value.basis')}>
              {decomposition.basis}
            </span>
          </dd>
        </div>
        <div>
          <dt>数据截至</dt>
          <dd data-testid={field('fair_value.as_of')}>
            {displayStamp(decomposition.as_of) ?? '—'}
          </dd>
        </div>
        <div>
          <dt>状态</dt>
          <dd data-testid={field('fair_value.status')}>{decomposition.status}</dd>
        </div>
        <div>
          <dt>回归样本</dt>
          <dd data-testid={field('fair_value.samples')}>{decomposition.samples}</dd>
        </div>
        <div>
          <dt>不可用原因</dt>
          <dd data-testid={field('fair_value.reason')}>{decomposition.reason ?? '—'}</dd>
        </div>
      </dl>

      <DataTable
        rows={decomposition.blocks}
        columns={columns}
        rowKey={(block) => block.key}
        caption="四块之和恒等于市场价：中枢 + 需求溢价 + 风险溢价 + 情绪残差（残差走阔 = 模型外因素在定价）。驱动列给出该块的回归量及其对数贡献。"
      />
    </div>
  )
}