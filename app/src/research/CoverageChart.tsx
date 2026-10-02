import type { HorizonResearch } from '@/services/api'

/**
 * 留出期 80% 区间覆盖率：内联 SVG，不用图表库。
 *
 * 名义覆盖率 80% 用金色虚线标出；每根柱子是一个尺度。没有数字的尺度画成
 * 空柱并显示「—」，不补 0 —— 0% 和「没算出来」是两回事。
 */
export default function CoverageChart({ horizons }: { horizons: HorizonResearch[] }) {
  const width = 640
  const height = 210
  const padX = 52
  const padTop = 26
  const padBottom = 38
  const plotWidth = width - padX * 2
  const plotHeight = height - padTop - padBottom
  const slot = horizons.length > 0 ? plotWidth / horizons.length : plotWidth
  const barWidth = Math.min(56, slot * 0.5)
  const target = 0.8
  const y = (value: number) => padTop + (1 - value) * plotHeight

  return (
    <figure className="panel" style={{ margin: 0 }}>
      <figcaption className="panel__title">留出期 80% 区间覆盖率</figcaption>
      <svg
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label="历史留出期各尺度 80% 区间覆盖率与 80% 名义线的对比"
        style={{ width: '100%', height: 'auto' }}
      >
        {[0, 0.4, 1].map((tick) => (
          <g key={tick}>
            <line
              x1={padX}
              x2={width - padX}
              y1={y(tick)}
              y2={y(tick)}
              stroke="var(--rule)"
              strokeWidth={1}
            />
            <text
              x={padX - 8}
              y={y(tick) + 4}
              textAnchor="end"
              fontSize={11}
              fill="var(--ink-muted)"
            >
              {Math.round(tick * 100)}%
            </text>
          </g>
        ))}

        <line
          x1={padX}
          x2={width - padX}
          y1={y(target)}
          y2={y(target)}
          stroke="var(--gold)"
          strokeWidth={1.5}
          strokeDasharray="6 4"
        />
        <text x={width - padX} y={y(target) - 6} textAnchor="end" fontSize={11} fill="var(--gold)">
          名义 80%
        </text>

        {horizons.map((horizon, index) => {
          const value = horizon.periods.holdout?.interval_coverage_80 ?? null
          const x = padX + slot * index + (slot - barWidth) / 2
          const barTop = value === null ? y(0) : y(Math.max(0, Math.min(1, value)))
          return (
            <g key={horizon.horizon_days}>
              <rect
                x={x}
                y={barTop}
                width={barWidth}
                height={value === null ? 2 : Math.max(1, y(0) - barTop)}
                fill={value === null ? 'none' : 'var(--ink)'}
                stroke={value === null ? 'var(--rule)' : 'none'}
              />
              <text
                x={x + barWidth / 2}
                y={barTop - 6}
                textAnchor="middle"
                fontSize={11}
                fill="var(--ink)"
              >
                {value === null ? '—' : `${(value * 100).toFixed(1)}%`}
              </text>
              <text
                x={x + barWidth / 2}
                y={height - padBottom + 18}
                textAnchor="middle"
                fontSize={12}
                fill="var(--ink-muted)"
              >
                {horizon.label}
              </text>
            </g>
          )
        })}
      </svg>
      <p className="note" style={{ marginTop: 10 }}>
        柱值 = **历史**留出期（已被前两轮裁决看过）的实际覆盖率，只作记录；
        样本不足时显示「—」，不补数字。裁决窗口的覆盖率见「前向留出期」一节。
      </p>
    </figure>
  )
}
