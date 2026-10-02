import DataTable, { type Column } from '@/components/DataTable'
import { displayStamp, formatPercent } from '@/lib/format'
import type {
  QuantCategoryStatus,
  QuantFactorCoverage,
  QuantFactorSnapshot,
  QuantFactorsResponse,
} from '@/services/api'
import { fieldTestId, TESTIDS } from '@/testids'
import { statusLabel, statusTag } from './shared'

const field = fieldTestId

/**
 * 覆盖画像：窗口 + 条数 + 年数走一行；缺口年与「积累期」分开报告 ——
 * 新序列允许先入库积累，不能被当成缺口。逐年观测数收进一层折叠。
 */
function CoverageLine({ coverage }: { coverage: QuantFactorCoverage }) {
  const yearEntries = coverage.years.map(
    (year) => `${year}: ${coverage.year_counts[String(year)] ?? 0}`,
  )
  return (
    <div className="note" data-testid={field('quant.factors.coverage')}>
      <span>
        覆盖 <span data-testid={field('quant.factors.coverage.first_date')}>{coverage.first_date ?? '—'}</span>
        {' — '}
        <span data-testid={field('quant.factors.coverage.last_date')}>{coverage.last_date ?? '—'}</span>
        {' · '}
        <span data-testid={field('quant.factors.coverage.observations')}>
          {coverage.observations}
        </span>{' '}
        条 ·{' '}
        <span data-testid={field('quant.factors.coverage.years')}>{coverage.years.length}</span> 年
      </span>
      {coverage.accumulating ? (
        <span className="tag" data-testid={field('quant.factors.coverage.accumulating')}>
          积累期（序列尚短，非缺口）
        </span>
      ) : null}
      {coverage.sparse_years.length > 0 ? (
        <span className="panel__error" data-testid={field('quant.factors.coverage.sparse_years')}>
          缺口年：{coverage.sparse_years.join('、')}
        </span>
      ) : null}
      <details className="row-details">
        <summary>逐年观测数（{coverage.years.length} 年）</summary>
        <span data-testid={field('quant.factors.coverage.year_counts')}>
          {yearEntries.join('、')}
        </span>
      </details>
    </div>
  )
}

/** 四类影响因素：每个因子一行，数值、来源、口径与滞后都进表格。 */
function CategoryTable({
  category,
  factors,
}: {
  category: QuantCategoryStatus
  factors: QuantFactorSnapshot[]
}) {
  const rows = factors.filter((factor) => factor.category === category.key)
  const columns: ReadonlyArray<Column<QuantFactorSnapshot>> = [
    {
      key: 'name',
      header: '因子',
      render: (factor) => (
        <>
          <span data-testid={field('quant.factors.name')}>{factor.name}</span>
          <span className="note" data-testid={field('quant.factors.key')}>
            {factor.key}
          </span>
          <span className="note" data-testid={field('quant.factors.description')}>
            {factor.description}
          </span>
          {factor.coverage ? (
            <CoverageLine coverage={factor.coverage} />
          ) : (
            <span className="note" data-testid={field('quant.factors.coverage')}>
              覆盖信息未提供（序列为空时后端不下发）
            </span>
          )}
        </>
      ),
    },
    {
      key: 'category',
      header: '类别',
      render: (factor) => (
        <>
          <span data-testid={field('quant.factors.category_name')}>{factor.category_name}</span>
          <span className="note" data-testid={field('quant.factors.category')}>
            {factor.category}
          </span>
        </>
      ),
    },
    {
      key: 'weight',
      header: '权重 / 方向',
      numeric: true,
      render: (factor) => (
        <>
          <span data-testid={field('quant.factors.weight')}>{factor.weight}</span>
          <span className="note" data-testid={field('quant.factors.sign')}>
            {factor.sign > 0 ? '上升利多' : '上升利空'}
          </span>
        </>
      ),
    },
    {
      key: 'value',
      header: '最新值',
      numeric: true,
      render: (factor) => (
        <>
          <span data-testid={field('quant.factors.value')}>
            {factor.value === null ? '—' : factor.value.toFixed(2)}
          </span>
          <span className="note" data-testid={field('quant.factors.unit')}>
            {factor.unit}
          </span>
        </>
      ),
    },
    {
      key: 'obs_date',
      header: '数据截至',
      render: (factor) => (
        <>
          <span data-testid={field('quant.factors.obs_date')}>{factor.obs_date ?? '—'}</span>
          <span className="note" data-testid={field('quant.factors.age_days')}>
            {factor.age_days === null ? '滞后未知' : `${factor.age_days} 天前`} / 上限{' '}
            <span data-testid={field('quant.factors.max_age_days')}>{factor.max_age_days}</span> 天
          </span>
        </>
      ),
    },
    {
      key: 'publication_lag',
      header: '发布滞后',
      numeric: true,
      source: '统计期末 → 公开发布',
      render: (factor) => (
        <span data-testid={field('quant.factors.publication_lag_days')}>
          {factor.publication_lag_days} 天
        </span>
      ),
    },
    {
      key: 'z',
      header: 'z',
      numeric: true,
      render: (factor) => (
        <>
          <span data-testid={field('quant.factors.z')}>
            {factor.z === null ? '—' : factor.z.toFixed(2)}
          </span>
          <span className="note" data-testid={field('quant.factors.signed_z')}>
            对齐后 {factor.signed_z === null ? '—' : factor.signed_z.toFixed(2)}
          </span>
        </>
      ),
    },
    {
      key: 'contribution',
      header: '贡献',
      numeric: true,
      render: (factor) => (
        <span data-testid={field('quant.factors.contribution')}>
          {factor.contribution === null ? '—' : formatPercent(factor.contribution * 100, 2)}
        </span>
      ),
    },
    {
      key: 'status',
      header: '状态',
      render: (factor) => (
        <>
          <span data-testid={field('quant.factors.status')}>{statusLabel(factor.status)}</span>
          {statusTag(factor.status)}
          <span className="note" data-testid={field('quant.factors.reason')}>
            {factor.reason ?? '—'}
          </span>
        </>
      ),
    },
    {
      key: 'source',
      header: '来源',
      render: (factor) => <span data-testid={field('quant.factors.source')}>{factor.source}</span>,
    },
  ]

  return (
    <div>
      <h4>
        {category.name}
        <span className="note" data-testid={field('quant.category.key')}>
          {category.key}
        </span>
      </h4>
      <p className="note">
        <span data-testid={field('quant.category.name')}>{category.name}</span>：
        <span data-testid={field('quant.category.available')}>{category.available}</span> /{' '}
        <span data-testid={field('quant.category.total')}>{category.total}</span> 个因子可用。
      </p>
      <DataTable
        rows={rows}
        columns={columns}
        rowKey={(factor) => factor.key}
        empty="这一类没有因子。"
      />
    </div>
  )
}

/**
 * 四类影响因素面板：面板头先给模型与因子总数，再逐类给出逐因子表。
 * 「发布滞后」是口径说明（统计期末到公开发布通常滞后几天），不是延迟。
 */
export default function FactorTables({ factors }: { factors: QuantFactorsResponse }) {
  return (
    <div className="space-y-6" data-testid={TESTIDS.quantFactorTable}>
      <p className="panel__meta">
        <span data-testid={field('quant.model_version')}>模型 {factors.model_version}</span>
        <span data-testid={field('quant.as_of')}>
          因子数据截至 {displayStamp(factors.as_of) ?? factors.as_of ?? '—'}
        </span>
        <span>
          可用 <span data-testid={field('quant.available_factors')}>{factors.available_factors}</span> /{' '}
          <span data-testid={field('quant.total_factors')}>{factors.total_factors}</span> 个因子
        </span>
        <span data-testid={field('quant.unavailable_reason')}>
          不可用原因：{factors.unavailable_reason ?? '无'}
        </span>
      </p>

      {factors.categories.map((category) => (
        <CategoryTable key={category.key} category={category} factors={factors.factors} />
      ))}
    </div>
  )
}