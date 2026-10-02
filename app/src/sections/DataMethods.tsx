import { useEffect, useState } from 'react'

import Section from '@/components/Section'
import StateBlock from '@/components/StateBlock'
import { describeApiError } from '@/lib/apiError'
import { displayStamp } from '@/lib/format'
import {
  healthApi,
  quantApi,
  sourcesApi,
  type HealthResponse,
  type QuantFactorsResponse,
  type SourcesStatusResponse,
} from '@/services/api'
import { fieldTestId, TESTIDS } from '@/testids'

const field = fieldTestId

function text(value: unknown): string {
  if (value === null || value === undefined || value === '') return '—'
  if (typeof value === 'boolean') return value ? '是' : '否'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

function serviceValue(health: HealthResponse | null, service: string, key: string): unknown {
  const services = (health?.services ?? {}) as Record<string, Record<string, unknown> | undefined>
  return services[service]?.[key]
}

const BOOTSTRAP_STATUS_NOTE: Record<string, string> = {
  pending: '等待启动',
  running: '正在运行',
  done: '已完成',
  failed: '失败',
  disabled: '未启用（后端关闭了启动引导）',
  skipped: '本轮跳过（后端未启用自动引导，例如测试环境）',
}

/** 引导进度：阶段表 + 数据空档；status 的每种取值都有对应的说法。 */
function BootstrapBlock({ health }: { health: HealthResponse | null }) {
  const bootstrap = health?.bootstrap
  if (!bootstrap) {
    return (
      <p className="note" data-testid={TESTIDS.dataBootstrap}>
        /health 未返回 bootstrap 字段（后端版本较旧或接口被裁剪）。
      </p>
    )
  }
  const running = bootstrap.status === 'running' || bootstrap.status === 'pending'
  return (
    <div className="space-y-4" data-testid={TESTIDS.dataBootstrap}>
      <p className="section__conclusion">
        <span data-testid={field('health.bootstrap.status')}>{bootstrap.status}</span>
        {'（'}
        <span data-testid={field('health.bootstrap.enabled')}>
          {bootstrap.enabled ? '已启用' : '未启用'}
        </span>
        {' · '}
        <span data-testid={field('health.bootstrap.ready')}>
          {bootstrap.ready ? '数据就绪' : '尚未就绪'}
        </span>
        {'）· '}
        {BOOTSTRAP_STATUS_NOTE[bootstrap.status] ?? '状态未知'}
        {' · 步骤 '}
        <span data-testid={field('health.bootstrap.step.index')}>{bootstrap.step.index}</span>
        {'/'}
        <span data-testid={field('health.bootstrap.step.total')}>{bootstrap.step.total}</span>
      </p>

      <p className="panel__meta">
        <span data-testid={field('health.bootstrap.started_at')}>
          开始 {displayStamp(bootstrap.started_at) ?? '—'}
        </span>
        <span data-testid={field('health.bootstrap.finished_at')}>
          完成 {displayStamp(bootstrap.finished_at) ?? '—'}
        </span>
        <span data-testid={field('health.bootstrap.error')}>错误：{bootstrap.error ?? '无'}</span>
        <span data-testid={field('health.bootstrap.migrations')}>
          迁移注册表：{text(bootstrap.migrations)}
        </span>
      </p>

      {running ? (
        <p className="note">
          引导仍在进行 —— 页面上的数据可能陆续补齐，完成后本行会变成「已完成」。
        </p>
      ) : null}

      {bootstrap.phases.length > 0 ? (
        <div className="table-scroll">
          <table className="data-table">
            <caption className="note">
              启动阶段：每一步的状态与说明都由后端给出；失败步骤会在这里留下原因。
            </caption>
            <thead>
              <tr>
                <th scope="col">阶段</th>
                <th scope="col">代号</th>
                <th scope="col">状态</th>
                <th scope="col">说明</th>
                <th scope="col">时间</th>
              </tr>
            </thead>
            <tbody>
              {bootstrap.phases.map((phase) => (
                <tr key={phase.key}>
                  <th scope="row" data-testid={field('health.bootstrap.phases.label')}>
                    {phase.label}
                  </th>
                  <td className="note" data-testid={field('health.bootstrap.phases.key')}>
                    {phase.key}
                  </td>
                  <td data-testid={field('health.bootstrap.phases.status')}>{phase.status}</td>
                  <td className="note" data-testid={field('health.bootstrap.phases.note')}>
                    {phase.note ?? '—'}
                  </td>
                  <td data-testid={field('health.bootstrap.phases.at')}>
                    {displayStamp(phase.at) ?? '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      <div className="table-scroll">
        <table className="data-table">
          <caption className="note">
            数据空档：每个通道的最后一期与是否需要补数；缺键显示「—」，不猜数字。
          </caption>
          <thead>
            <tr>
              <th scope="col">通道</th>
              <th scope="col" className="num">
                行数
              </th>
              <th scope="col">最后一期</th>
              <th scope="col">缺口明细</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <th scope="row">金价日线</th>
              <td className="num" data-testid={field('health.bootstrap.gaps.gold_prices.rows')}>
                {text(bootstrap.gaps.gold_prices?.rows)}
              </td>
              <td data-testid={field('health.bootstrap.gaps.gold_prices.last_date')}>
                {text(bootstrap.gaps.gold_prices?.last_date)}
              </td>
              <td className="note">—</td>
            </tr>
            <tr>
              <th scope="row">美元指数</th>
              <td className="num" data-testid={field('health.bootstrap.gaps.dollar_index.rows')}>
                {text(bootstrap.gaps.dollar_index?.rows)}
              </td>
              <td data-testid={field('health.bootstrap.gaps.dollar_index.last_date')}>
                {text(bootstrap.gaps.dollar_index?.last_date)}
              </td>
              <td className="note">—</td>
            </tr>
            <tr>
              <th scope="row">黄金新闻</th>
              <td className="num" data-testid={field('health.bootstrap.gaps.gold_news.rows')}>
                {text(bootstrap.gaps.gold_news?.rows)}
              </td>
              <td data-testid={field('health.bootstrap.gaps.gold_news.last_published_at')}>
                {text(bootstrap.gaps.gold_news?.last_published_at)}
              </td>
              <td className="note">—</td>
            </tr>
            <tr>
              <th scope="row">消息摘要</th>
              <td className="num" data-testid={field('health.bootstrap.gaps.news_digest.rows')}>
                {text(bootstrap.gaps.news_digest?.rows)}
              </td>
              <td data-testid={field('health.bootstrap.gaps.news_digest.last_published_at')}>
                {text(bootstrap.gaps.news_digest?.last_published_at)}
              </td>
              <td className="note">—</td>
            </tr>
            <tr>
              <th scope="row">量化因子</th>
              <td className="num" data-testid={field('health.bootstrap.gaps.quant.sparse_year_count')}>
                稀疏年份 {text(bootstrap.gaps.quant?.sparse_year_count)} 个
              </td>
              <td data-testid={field('health.bootstrap.gaps.quant.window_years')}>
                覆盖窗口 {text(bootstrap.gaps.quant?.window_years)} 年
              </td>
              <td className="note" data-testid={field('health.bootstrap.gaps.quant.series_without_data')}>
                无数据序列：{text(bootstrap.gaps.quant?.series_without_data)}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  )
}

/** 数据源可用性：每个渠道最近一次尝试的状态、时间与条目数。 */
function SourcesBlock({
  sources,
  error,
}: {
  sources: SourcesStatusResponse | null
  error: string | null
}) {
  if (!sources) {
    return (
      <StateBlock
        kind="unavailable"
        title="数据源状态不可用"
        testId="data-sources-unavailable"
        detail={error ?? '接口没有返回数据源状态。'}
      />
    )
  }
  return (
    <div className="space-y-4">
      <p className="section__conclusion">
        共 {sources.summary.total} 个渠道：可用 {sources.summary.ok} · 无数据 {sources.summary.empty} ·
        不可用 {sources.summary.error} · 本轮跳过 {sources.summary.skipped} · 陈旧 {sources.summary.stale}
        ；状态生成于{' '}
        <span data-testid={field('sources.generated_at')}>
          {displayStamp(sources.generated_at) ?? '—'}
        </span>
        。
      </p>
      <p className="panel__meta">
        <span data-testid={field('sources.summary.total')}>总数 {sources.summary.total}</span>
        <span data-testid={field('sources.summary.ok')}>可用 {sources.summary.ok}</span>
        <span data-testid={field('sources.summary.empty')}>无数据 {sources.summary.empty}</span>
        <span data-testid={field('sources.summary.error')}>不可用 {sources.summary.error}</span>
        <span data-testid={field('sources.summary.skipped')}>跳过 {sources.summary.skipped}</span>
        <span data-testid={field('sources.summary.stale')}>陈旧 {sources.summary.stale}</span>
      </p>
      <div className="table-scroll">
        <table className="data-table">
          <caption className="note">
            每行是一个渠道最近一次抓取尝试：来源代号、状态、是否陈旧、数据年龄与条目数；
            failed 行给出错误原文，不吞掉。
          </caption>
          <thead>
            <tr>
              <th scope="col">渠道</th>
              <th scope="col">来源代号</th>
              <th scope="col">状态</th>
              <th scope="col" className="num">
                陈旧
              </th>
              <th scope="col" className="num">
                数据年龄（小时）
              </th>
              <th scope="col">开始</th>
              <th scope="col">完成</th>
              <th scope="col" className="num">
                条目
              </th>
              <th scope="col">错误</th>
            </tr>
          </thead>
          <tbody>
            {sources.sources.map((source) => (
              <tr key={`${source.channel}-${source.source_key}`}>
                <th scope="row">
                  <span data-testid={field('sources.rows.channel_label')}>{source.channel_label}</span>
                  <span className="note" data-testid={field('sources.rows.channel')}>
                    {source.channel}
                  </span>
                </th>
                <td className="note" data-testid={field('sources.rows.source_key')}>
                  {source.source_key}
                </td>
                <td>
                  <span data-testid={field('sources.rows.status_label')}>{source.status_label}</span>
                  <span className="note" data-testid={field('sources.rows.status')}>
                    {source.status}
                  </span>
                </td>
                <td className="num" data-testid={field('sources.rows.stale')}>
                  {source.stale ? '是' : '否'}
                </td>
                <td className="num" data-testid={field('sources.rows.age_hours')}>
                  {text(source.age_hours)}
                </td>
                <td data-testid={field('sources.rows.started_at')}>
                  {displayStamp(source.started_at) ?? '—'}
                </td>
                <td data-testid={field('sources.rows.finished_at')}>
                  {displayStamp(source.finished_at) ?? '—'}
                </td>
                <td className="num" data-testid={field('sources.rows.items')}>
                  {text(source.items)}
                </td>
                <td className="note" data-testid={field('sources.rows.error')}>
                  {source.error ?? '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

/** .env 热加载（config_watch）：只展示状态与文件名，不展示任何值。 */
function ConfigWatchBlock({ health }: { health: HealthResponse | null }) {
  const watch = health?.config_watch
  if (!watch) {
    return (
      <p className="note" data-testid={TESTIDS.dataConfigWatch}>
        /health 未返回 config_watch 字段。
      </p>
    )
  }
  return (
    <div className="space-y-4" data-testid={TESTIDS.dataConfigWatch}>
      <p className="section__conclusion">
        配置热加载 <span data-testid={field('health.config_watch.status')}>{watch.status}</span>
        {'（'}
        <span data-testid={field('health.config_watch.enabled')}>
          {watch.enabled ? '已启用' : '未启用'}
        </span>
        {'）· 监测文件 '}
        <span data-testid={field('health.config_watch.env_file')}>{watch.env_file}</span>
        {' · 间隔 '}
        <span data-testid={field('health.config_watch.interval_seconds')}>
          {watch.interval_seconds}
        </span>
        {' 秒'}
      </p>
      <p className="panel__meta">
        <span data-testid={field('health.config_watch.last_check_at')}>
          上次检查 {displayStamp(watch.last_check_at) ?? '—'}
        </span>
        <span data-testid={field('health.config_watch.last_reload_at')}>
          上次重载 {displayStamp(watch.last_reload_at) ?? '—'}
        </span>
        <span data-testid={field('health.config_watch.reloaded_keys')}>
          重载过的键：{watch.reloaded_keys.length > 0 ? watch.reloaded_keys.join('、') : '无'}
        </span>
        <span data-testid={field('health.config_watch.note')}>{watch.note ?? '—'}</span>
      </p>
    </div>
  )
}

/**
 * 数据与方法：数据源可用性、启动引导进度、量化同步报告、服务状态与口径说明。
 *
 * 这一节只陈述事实与口径，不产生任何新数字；密钥只以「是否配置」出现，不展示值。
 */
export default function DataMethods() {
  const [sources, setSources] = useState<SourcesStatusResponse | null>(null)
  const [factors, setFactors] = useState<QuantFactorsResponse | null>(null)
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [sourcesError, setSourcesError] = useState<string | null>(null)
  const [healthError, setHealthError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    const load = async () => {
      setLoading(true)
      const [sourcesResult, factorsResult, healthResult] = await Promise.allSettled([
        sourcesApi.getStatus(),
        quantApi.getFactors(),
        healthApi.getHealth(),
      ])
      if (cancelled) return
      if (sourcesResult.status === 'fulfilled') {
        setSources(sourcesResult.value)
        setSourcesError(null)
      } else {
        setSourcesError(describeApiError(sourcesResult.reason, { fallback: '获取数据源状态失败。' }))
      }
      setFactors(factorsResult.status === 'fulfilled' ? factorsResult.value : null)
      if (healthResult.status === 'fulfilled') {
        setHealth(healthResult.value)
        setHealthError(null)
      } else {
        setHealthError(describeApiError(healthResult.reason, { fallback: '获取 /health 失败。' }))
      }
      setLoading(false)
    }
    void load()
    return () => {
      cancelled = true
    }
  }, [])

  if (loading) {
    return (
      <Section id="data-methods" title="数据与方法" intro="数据源可用性、初始化进度、同步报告与口径说明。">
        <StateBlock title="正在读取数据源与方法说明…" testId="data-methods-loading" />
      </Section>
    )
  }

  return (
    <Section
      id="data-methods"
      title="数据与方法"
      intro="这一节陈述数据从哪里来、什么时候更新、哪些渠道不可用，以及页面上各种口径标签的含义；它不产生新数字。"
    >
      <div className="space-y-8">
        <div className="panel" data-testid={TESTIDS.dataSync}>
          <h3 className="panel__title">同步报告</h3>
          {factors ? (
            <p className="section__conclusion">
              同步完成{' '}
              <span data-testid={field('quant.sync.finished_at')}>
                {displayStamp(factors.sync.finished_at) ?? '—'}
              </span>
              {'；本轮开始 '}
              <span data-testid={field('quant.sync.started_at')}>
                {displayStamp(factors.sync.started_at) ?? '—'}
              </span>
              {'；正常源 '}
              <span data-testid={field('quant.sync.sources_ok')}>{factors.sync.sources_ok ?? '—'}</span>
              {'/'}
              <span data-testid={field('quant.sync.sources_total')}>{factors.sync.sources_total ?? '—'}</span>
              ；因子数据截至 {factors.as_of ?? '—'}，可用 {factors.available_factors}/{factors.total_factors}。
              逐源明细在「量化预测 → 数据源状态」。
            </p>
          ) : (
            <p className="note">量化同步报告不可用（因子接口没有返回）。</p>
          )}
        </div>

        <div className="panel" data-testid={TESTIDS.dataSourcesStatus}>
          <h3 className="panel__title">数据源可用性</h3>
          <SourcesBlock sources={sources} error={sourcesError} />
        </div>

        <div className="panel">
          <h3 className="panel__title">初始化进度</h3>
          <BootstrapBlock health={health} />
          {healthError ? <p className="panel__error">/health 读取失败：{healthError}</p> : null}
        </div>

        <div className="panel">
          <h3 className="panel__title">配置与热加载</h3>
          <ConfigWatchBlock health={health} />
        </div>

        <div className="panel">
          <h3 className="panel__title">服务状态</h3>
          <p className="panel__meta">
            <span data-testid={field('health.status')}>整体 {health?.status ?? '—'}</span>
            <span data-testid={field('health.version')}>版本 {health?.version ?? '—'}</span>
            <span data-testid={field('health.timestamp')}>
              时间 {displayStamp(health?.timestamp) ?? '—'}
            </span>
          </p>
          <div className="table-scroll">
            <table className="data-table">
              <caption className="note">服务自检：密钥类配置只显示是否已配置与端点信息，不展示密钥本身。</caption>
              <thead>
                <tr>
                  <th scope="col">服务</th>
                  <th scope="col">状态</th>
                  <th scope="col">说明</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <th scope="row">模型服务</th>
                  <td data-testid={field('health.services.ai_config.status')}>
                    {text(serviceValue(health, 'ai_config', 'status'))}
                  </td>
                  <td className="note">
                    <span data-testid={field('health.services.ai_config.provider')}>
                      供应商 {text(serviceValue(health, 'ai_config', 'provider'))}
                    </span>
                    <span data-testid={field('health.services.ai_config.model')}>
                      模型 {text(serviceValue(health, 'ai_config', 'model'))}
                    </span>
                    <span data-testid={field('health.services.ai_config.base_url')}>
                      端点 {text(serviceValue(health, 'ai_config', 'base_url'))}
                    </span>
                    <span data-testid={field('health.services.ai_config.search_model')}>
                      联网搜索模型 {text(serviceValue(health, 'ai_config', 'search_model'))}
                    </span>
                    <span data-testid={field('health.services.ai_config.configured')}>
                      密钥已配置：{text(serviceValue(health, 'ai_config', 'configured'))}
                    </span>
                  </td>
                </tr>
                <tr>
                  <th scope="row">数据库</th>
                  <td data-testid={field('health.services.database.status')}>
                    {text(serviceValue(health, 'database', 'status'))}
                  </td>
                  <td className="note">—</td>
                </tr>
                <tr>
                  <th scope="row">行情接口</th>
                  <td data-testid={field('health.services.tencent_api.status')}>
                    {text(serviceValue(health, 'tencent_api', 'status'))}
                  </td>
                  <td className="note">—</td>
                </tr>
                <tr>
                  <th scope="row">缓存</th>
                  <td data-testid={field('health.services.cache.status')}>
                    {text(serviceValue(health, 'cache', 'status'))}
                  </td>
                  <td className="note">—</td>
                </tr>
                <tr>
                  <th scope="row">定时任务</th>
                  <td data-testid={field('health.services.scheduler.status')}>
                    {text(serviceValue(health, 'scheduler', 'status'))}
                  </td>
                  <td className="note">—</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <div className="panel" data-testid={TESTIDS.dataLegend}>
          <h3 className="panel__title">口径说明与图例</h3>
          <dl className="principles">
            <dt>价格口径标签</dt>
            <dd>
              实时报价 = 数据源当前报价，带报价时间；日收盘 = 数据源当日收盘后的日线值；
              量化基准 = 量化模型使用的日收盘序列最后一点（目标价与区间的基准口径）。
              每处价格都在旁边或表内注明口径与数据截至时间。
            </dd>
            <dt>涨跌符号</dt>
            <dd>
              ▲ 表示上涨 / 看涨，▼ 表示下跌 / 看跌，＝ 表示持平，— 表示后端未给值；
              颜色只是加强，文字与符号始终同时出现。
            </dd>
            <dt>数据截至与来源列</dt>
            <dd>
              凡是带来源的数据，表内固定给出「来源 / 数据截至」两列；观测日越旧，越要打折看。
              发布时间滞后（统计期末 → 公开发布）单独一列说明，不与数据延迟混为一谈。
            </dd>
            <dt>不可用的处理</dt>
            <dd>
              数据源不可用时页面显示「不可用」与原因，不用内置数字或模型印象补位；
              金额缺失显示「—」，不显示 $0.00。
            </dd>
          </dl>
        </div>
      </div>
    </Section>
  )
}