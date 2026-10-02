import DataTable, { type Column } from '@/components/DataTable'
import StateBlock from '@/components/StateBlock'
import type { QuantMonitorResponse, QuantMonitorRow } from '@/services/api'
import { fieldTestId, TESTIDS } from '@/testids'
import {
  MONITOR_INFO_KEYS,
  SIGNAL_TEXT,
  formatChange,
  formatMonitorValue,
  statusLabel,
} from './shared'

const field = fieldTestId

function MonitorSignal({ row }: { row: QuantMonitorRow }) {
  if (row.status !== 'ok') {
    return (
      <span className="tag" data-testid={field('monitor.status')}>
        {statusLabel(row.status)}
      </span>
    )
  }
  const text = row.signal === null ? null : SIGNAL_TEXT[row.signal]
  if (text === null) {
    return (
      <span className="note" data-testid={field('monitor.signal_label')}>
        {row.signal_label}
      </span>
    )
  }
  return (
    <span
      className={row.signal === 'bull' ? 'is-up' : row.signal === 'bear' ? 'is-down' : ''}
      data-testid={field('monitor.signal')}
    >
      {text}
    </span>
  )
}

function columns(): ReadonlyArray<Column<QuantMonitorRow>> {
  return [
    {
      key: 'name',
      header: '指标',
      render: (row) => (
        <>
          <span data-testid={field('monitor.name')}>{row.name}</span>
          <span className="note" data-testid={field('monitor.key')}>
            {row.key}
          </span>
        </>
      ),
    },
    {
      key: 'frequency',
      header: '频率',
      render: (row) => <span data-testid={field('monitor.frequency')}>{row.frequency}</span>,
    },
    {
      key: 'source',
      header: '来源',
      render: (row) => <span data-testid={field('monitor.source')}>{row.source}</span>,
    },
    {
      key: 'value',
      header: '最新值',
      numeric: true,
      render: (row) => (
        <span data-testid={field('monitor.value')}>
          {row.value === null ? '—' : formatMonitorValue(row.value)}
          <span className="note" data-testid={field('monitor.unit')}>
            {row.unit}
          </span>
        </span>
      ),
    },
    {
      key: 'change',
      header: '变化',
      numeric: true,
      render: (row) => (
        <span data-testid={field('monitor.change')}>
          {row.change === null ? '—' : formatChange(row.change)}
        </span>
      ),
    },
    {
      key: 'obs_date',
      header: '数据截至',
      render: (row) => <span data-testid={field('monitor.obs_date')}>{row.obs_date ?? '—'}</span>,
    },
    {
      key: 'signal',
      header: '信号',
      render: (row) => <MonitorSignal row={row} />,
    },
    {
      key: 'note',
      header: '说明',
      render: (row) => (
        <>
          <span className="note" data-testid={field('monitor.note')}>
            {row.note}
          </span>
          {row.reason ? (
            <span className="note" data-testid={`quant-monitor-reason-${row.key}`}>
              （<span data-testid={field('monitor.reason')}>{row.reason}</span>）
            </span>
          ) : null}
        </>
      ),
    },
  ]
}

function MonitorTable({
  rows,
  testId,
  empty,
}: {
  rows: QuantMonitorRow[]
  testId: string
  empty: string
}) {
  return (
    <DataTable
      rows={rows}
      columns={columns()}
      rowKey={(row) => row.key}
      testId={testId}
      empty={empty}
    />
  )
}

/**
 * 监测仪表盘：方法论第七节的周更表。
 *
 * 按后端口径拆成两张表：参与信号（有确定性多空规则）与只看不评（信息型指标，
 * 只给数值不给方向）。每行给频率、来源、最新值与数据截至，取不到就说原因。
 */
export default function Monitor({ monitor }: { monitor: QuantMonitorResponse }) {
  if (monitor.rows.length === 0) {
    return (
      <StateBlock
        kind="unavailable"
        testId="quant-monitor-unavailable"
        title="监测仪表盘不可用"
        detail="接口没有返回任何监测行。"
      />
    )
  }

  const participating = monitor.rows.filter((row) => !MONITOR_INFO_KEYS.has(row.key))
  const infoOnly = monitor.rows.filter((row) => MONITOR_INFO_KEYS.has(row.key))
  const bullish = participating.filter((row) => row.signal === 'bull').length
  const bearish = participating.filter((row) => row.signal === 'bear').length
  const neutral = participating.length - bullish - bearish

  return (
    <div className="space-y-6" data-testid={TESTIDS.quantMonitorTable}>
      <p className="section__conclusion">
        参与信号 {participating.length} 项（看涨 {bullish} · 看跌 {bearish} · 中性 / 样本不足 {neutral}）；
        只看不评 {infoOnly.length} 项（信息型指标不给方向）。
        <span className="note" data-testid={field('monitor.as_of')}>
          全部指标中最新观测日：{monitor.as_of ?? '—'}。
        </span>
      </p>

      <div>
        <h4 data-testid={TESTIDS.quantMonitorParticipating}>参与信号（有确定性多空规则）</h4>
        <p className="note">
          信号只来自后端 monitor.py 的确定性规则；数据截至一列是每个指标的观测日 ——
          值越旧，越要打折看。看涨 / 看跌同时给 ▲▼ 与文字，颜色只是加强。
        </p>
        <MonitorTable
          rows={participating}
          testId={`${TESTIDS.quantMonitorParticipating}-table`}
          empty="没有参与信号的指标。"
        />
      </div>

      <div>
        <h4 data-testid={TESTIDS.quantMonitorInfoOnly}>只看不评（信息型指标）</h4>
        <p className="note">
          这些指标只给数值与观测日，不给多空判断 —— 它们在历史样本上没有通过筛选闸门，
          给方向就是编造。
        </p>
        <MonitorTable
          rows={infoOnly}
          testId={`${TESTIDS.quantMonitorInfoOnly}-table`}
          empty="没有信息型指标。"
        />
      </div>

      {monitor.rows
        .filter((row) => row.status !== 'ok' && row.reason)
        .map((row) => (
          <p className="note" key={`${row.key}-unavailable`}>
            {row.name}：{row.reason}
          </p>
        ))}
    </div>
  )
}