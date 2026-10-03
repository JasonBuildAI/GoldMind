/**
 * 测试选择器契约：所有测试（vitest / Playwright / 截图脚本）使用的选择器
 * 只在 TESTIDS 里定义一次。改这里就等于改契约 —— 组件、测试与截图脚本
 * 用的是同一批字符串（截图脚本是 .mjs，不能 import TS，用同名字面量并在
 * 改动时同步，规范见 docs/20-前端设计规范.md 第八节）。
 */

export const fieldTestId = (path: string): string => `field-${path}`

const field = (path: string) => fieldTestId(path)
const build = (paths: readonly string[]) =>
  Object.freeze(Object.fromEntries(paths.map((path) => [path, field(path)])))

/** 量化预测的五个决策尺度。 */
export const PREDICTION_FIELDS = [
  'horizon_days',
  'scale_label',
  'scale',
  'scale_description',
  'headline',
  'status',
  'reason',
  'direction',
  'direction_label',
  'direction_status',
  'direction_reason',
  'as_of',
  'base_price',
  'base_basis',
  'base_basis_label',
  'target_price',
  'expected_return',
  'uncertainty',
  'probability_up',
  'distribution_mode',
  'interval_alpha',
  'interval_nominal',
  'expected_capped',
  'range_low',
  'range_high',
  'scenario_reason',
  'score',
  'model_version',
  'available_factors',
  'total_factors',
] as const

export const SCENARIO_FIELDS = [
  'key',
  'label',
  'probability',
  'price_low',
  'price_high',
  'trigger',
  'invalidation',
] as const

export const FACTOR_SNAPSHOT_FIELDS = [
  'key',
  'name',
  'category',
  'category_name',
  'unit',
  'source',
  'description',
  'sign',
  'weight',
  'value',
  'obs_date',
  'age_days',
  'max_age_days',
  'publication_lag_days',
  'coverage',
  'z',
  'signed_z',
  'contribution',
  'status',
  'reason',
] as const

export const FACTOR_CONTRIBUTION_FIELDS = [
  'key',
  'name',
  'category',
  'category_name',
  'weight',
  'sign',
  'value',
  'obs_date',
  'z',
  'signed_z',
  'contribution',
  'status',
  'reason',
] as const

export const FACTOR_ITEM_FIELDS = [
  'id',
  'title',
  'subtitle',
  'description',
  'details',
  'impact',
] as const

export const DIGEST_WINDOW_FIELDS = ['key', 'label', 'hours', 'total_clusters'] as const

export const DIGEST_RESPONSE_FIELDS = [
  'generated_at',
  'has_data',
  'unavailable_reason',
  'last_fetch',
] as const

/** 翻译状态（`digest.translation.*`，2026-10-03 起）。 */
export const DIGEST_TRANSLATION_FIELDS = ['enabled', 'model', 'pending', 'reason'] as const

export const ADVICE_PRINCIPLE_FIELDS = ['title', 'description'] as const

export const FACTOR_PERFORMANCE_FIELDS = [
  'key',
  'name',
  'category',
  'category_name',
  'weight',
  'sign',
  'samples',
  'hit_rate',
  'ic',
  'rank_ic',
] as const

export const REGIME_BLOCK_FIELDS = [
  'label',
  'window_start',
  'window_end',
  'sample_size',
  'accuracy',
  'baseline_up_accuracy',
  'baseline_momentum_accuracy',
  'reason',
] as const

export const MONITOR_FIELDS = [
  'key',
  'name',
  'frequency',
  'source',
  'value',
  'unit',
  'change',
  'obs_date',
  'signal',
  'signal_label',
  'note',
  'status',
  'reason',
] as const

export const RESEARCH_PERIODS = ['development', 'holdout', 'forward', 'full'] as const
export const RESEARCH_PERIOD_FIELDS = [
  'label',
  'window_start',
  'window_end',
  'sample_size',
  'accuracy',
  'baseline_up_accuracy',
  'baseline_momentum_accuracy',
  'brier_score',
  'brier_skill_score',
  'brier_skill_p_value',
  'mean_crps',
  'crps_skill_vs_flat',
  'accuracy_diff_vs_up',
  'direction_edge_vs_up_ci95',
  'down_calls',
  'down_call_accuracy',
  'down_call_edge_vs_up',
  'accuracy_ci95',
  'p_value_vs_up',
  'interval_coverage_80',
  'interval_coverage_ci95',
  'effective_sample_size',
  'independent_bets',
  'independent_bet_stride',
  'accuracy_independent_bets',
  'interval_coverage_80_independent_bets',
  'expected_cap_rate',
  'reason',
] as const

export const RESEARCH_HORIZON_FIELDS = ['horizon_days', 'label', 'headline'] as const

export const FORWARD_READINESS_FIELDS = [
  'window_start',
  'observations',
  'independent_bets',
  'required_bets',
  'decidable',
  'shortfall_bets',
  'approx_trading_days_needed',
] as const

export const FORWARD_POSTERIOR_FIELDS = [
  'prior',
  'alpha',
  'beta',
  'successes',
  'independent_bets',
  'mean',
  'ci95',
  'threshold',
  'probability_above_threshold',
  'mean_crps',
  'crps_skill_vs_flat',
] as const

export const RESEARCH_FACTOR_FIELDS = [
  'key',
  'name',
  'category',
  'category_name',
  'weight',
  'sign',
  'samples',
  'hit_rate',
  'ic',
  'rank_ic',
  'alignment',
  'alignment_t',
  'alignment_p_value',
  'alignment_naive_t',
] as const

export const DIGEST_ITEM_FIELDS = [
  'rank',
  'id',
  'title',
  'summary',
  // 中文译文：与英文原文并存（`title` / `summary` 照旧下发，可逐条核对）
  'title_zh',
  'brief_zh',
  'translated',
  'translation_model',
  'translated_at',
  'source',
  'tier',
  'tier_label',
  'url',
  'published_at',
  'age_hours',
  'importance',
  'confidence',
  'signals',
  'event_tags',
  'event_labels',
  'via_aggregator',
  'coverage_count',
] as const

export const DIGEST_RELATED_FIELDS = ['title', 'source', 'url', 'published_at'] as const

export const DIGEST_FETCH_FIELDS = [
  'fetched_at',
  'total_sources',
  'ok_sources',
  'failed_sources',
  'entries',
  'kept',
  'new_items',
  'duplicates',
  'skipped_no_title',
  'skipped_no_url',
  'skipped_no_time',
  'skipped_filtered',
  'skipped_unstorable',
  // 中文翻译：与抓取计数分开（翻译失败不是抓取失败）
  'translated',
  'translation_reason',
] as const

export const DIGEST_FETCH_SOURCE_FIELDS = ['name', 'status', 'entries', 'kept', 'new', 'error'] as const
export const INSTITUTION_FIELDS = [
  'name',
  'logo',
  'rating',
  'target_price',
  'timeframe',
  'reasoning',
  'key_points',
  'as_of_date',
  'stale_days',
  'source',
] as const

export const STRATEGY_FIELDS = [
  'type',
  'title',
  'description',
  'allocation',
  'timeframe',
  'risk_level',
  'pros',
  'cons',
  'suitable_for',
  'execution_steps',
] as const

export const ENTRY_FIELDS = [
  'current_price_assessment',
  'recommended_entry_range',
  'entry_timing',
  'position_building',
] as const

export const EXIT_FIELDS = ['profit_target', 'stop_loss', 'rebalancing_trigger'] as const

export const PRICE_SNAPSHOT_FIELDS = [
  'label',
  'window_start',
  'window_end',
  'latest_price',
  'change_pct',
  'high',
  'low',
  'amplitude_pct',
  'full_window',
  // 快照价自己的时间 / 口径 / 来源（2026-10-03）：只给数字读者不知道「这是哪天的」
  'as_of',
  'basis_label',
  'source',
] as const

export const MARKET_ASSESSMENT_FIELDS = [
  'current_position',
  'risk_level',
  'recommended_approach',
  'key_considerations',
] as const

export const METADATA_FIELDS = [
  'cached',
  'status',
  'cache_source',
  'message',
  'generated_at',
  'data_sources',
  'analysis_method',
] as const

export const RESEARCH_RELIABILITY_FIELDS = ['lo', 'hi', 'count', 'mean_predicted', 'frequency'] as const

/** 因子覆盖画像（2.0.2 第 11 条）的字段级选择器。 */
export const QUANT_FACTOR_COVERAGE_FIELDS = [
  'observations',
  'years',
  'year_counts',
  'sparse_years',
  'first_date',
  'last_date',
  'accumulating',
] as const

export const SOURCES_STATUS_FIELDS = [
  'channel',
  'channel_label',
  'source_key',
  'status',
  'status_label',
  'stale',
  'age_hours',
  'started_at',
  'finished_at',
  'items',
  'error',
] as const

export const SOURCES_SUMMARY_FIELDS = ['total', 'ok', 'empty', 'error', 'skipped', 'stale'] as const

export const BOOTSTRAP_PHASE_FIELDS = ['key', 'label', 'status', 'note', 'at'] as const

export const CONFIG_WATCH_FIELDS = [
  'enabled',
  'status',
  'env_file',
  'interval_seconds',
  'last_check_at',
  'last_reload_at',
  'reloaded_keys',
  'note',
] as const
const prediction = build(PREDICTION_FIELDS.map((name) => `predictions.${name}`))
const scenarios = build(SCENARIO_FIELDS.map((name) => `predictions.scenarios.${name}`))
const factorSnapshots = build(FACTOR_SNAPSHOT_FIELDS.map((name) => `quant.factors.${name}`))
const factorCoverage = build(
  QUANT_FACTOR_COVERAGE_FIELDS.map((name) => `quant.factors.coverage.${name}`),
)
const factorContributions = build(
  FACTOR_CONTRIBUTION_FIELDS.map((name) => `predictions.factors.${name}`),
)
const monitor = build(MONITOR_FIELDS.map((name) => `monitor.${name}`))
const researchPeriods = Object.freeze(
  Object.fromEntries(
    RESEARCH_PERIODS.map((period) => [
      period,
      build(RESEARCH_PERIOD_FIELDS.map((name) => `research.periods.${period}.${name}`)),
    ]),
  ),
)
const researchHorizons = build(RESEARCH_HORIZON_FIELDS.map((name) => `research.horizons.${name}`))
const forwardReadiness = build(
  FORWARD_READINESS_FIELDS.map((name) => `research.horizons.forward_readiness.${name}`),
)
const forwardPosterior = build(
  FORWARD_POSTERIOR_FIELDS.map((name) => `research.horizons.forward_posterior.${name}`),
)
const researchFactors = build(RESEARCH_FACTOR_FIELDS.map((name) => `research.factors.${name}`))
const researchReliability = build(
  RESEARCH_RELIABILITY_FIELDS.map((name) => `research.reliability.${name}`),
)
const digestItems = build(DIGEST_ITEM_FIELDS.map((name) => `digest.items.${name}`))
const digestRelated = build(DIGEST_RELATED_FIELDS.map((name) => `digest.related.${name}`))
const digestFetch = build(DIGEST_FETCH_FIELDS.map((name) => `digest.fetch.${name}`))
const digestFetchSources = build(
  DIGEST_FETCH_SOURCE_FIELDS.map((name) => `digest.fetch.sources.${name}`),
)
const institutions = build(INSTITUTION_FIELDS.map((name) => `institutions.${name}`))
const strategy = build(STRATEGY_FIELDS.map((name) => `advice.strategy.${name}`))
const entry = build(ENTRY_FIELDS.map((name) => `advice.entry.${name}`))
const exit = build(EXIT_FIELDS.map((name) => `advice.exit.${name}`))
const snapshot = build(PRICE_SNAPSHOT_FIELDS.map((name) => `advice.snapshot.${name}`))
const assessment = build(MARKET_ASSESSMENT_FIELDS.map((name) => `advice.assessment.${name}`))
const metadata = build(METADATA_FIELDS.map((name) => `metadata.${name}`))
const sourcesStatus = build(SOURCES_STATUS_FIELDS.map((name) => `sources.rows.${name}`))
const sourcesSummary = build(SOURCES_SUMMARY_FIELDS.map((name) => `sources.summary.${name}`))
const bootstrapPhases = build(BOOTSTRAP_PHASE_FIELDS.map((name) => `health.bootstrap.phases.${name}`))
const configWatch = build(CONFIG_WATCH_FIELDS.map((name) => `health.config_watch.${name}`))
const bullishItems = build(FACTOR_ITEM_FIELDS.map((name) => `bullish.items.${name}`))
const bearishItems = build(FACTOR_ITEM_FIELDS.map((name) => `bearish.items.${name}`))
const digestWindows = build(DIGEST_WINDOW_FIELDS.map((name) => `digest.windows.${name}`))
const digestResponse = build(DIGEST_RESPONSE_FIELDS.map((name) => `digest.${name}`))
const digestTranslation = build(
  DIGEST_TRANSLATION_FIELDS.map((name) => `digest.translation.${name}`),
)
const principles = build(ADVICE_PRINCIPLE_FIELDS.map((name) => `advice.principles.${name}`))
const accuracyFactors = build(FACTOR_PERFORMANCE_FIELDS.map((name) => `accuracy.factors.${name}`))
const accuracyRegimePre = build(REGIME_BLOCK_FIELDS.map((name) => `accuracy.regimes.pre.${name}`))
const accuracyRegimePost = build(REGIME_BLOCK_FIELDS.map((name) => `accuracy.regimes.post.${name}`))
const extras = Object.freeze({
  'bullish.analysis_summary': field('bullish.analysis_summary'),
  'bullish.last_updated': field('bullish.last_updated'),
  'bearish.analysis_summary': field('bearish.analysis_summary'),
  'bearish.last_updated': field('bearish.last_updated'),
  'advice.risk_warning': field('advice.risk_warning'),
  'advice.disclaimer': field('advice.disclaimer'),
  'advice.analysis_status': field('advice.analysis_status'),
  'monitor.as_of': field('monitor.as_of'),
  'predictions.model_version': field('predictions.model_version'),
  'predictions.as_of': field('predictions.as_of'),
  // 金价出现在哪儿，它的刷新时间槽位就跟到哪儿（2026-10-03）
  'predictions.base_price_as_of': field('predictions.base_price_as_of'),
  'fair_value.market_price_as_of': field('fair_value.market_price_as_of'),
  'quant.refresh.success': field('quant.refresh.success'),
  'quant.refresh.message': field('quant.refresh.message'),
  'digest.refresh.success': field('digest.refresh.success'),
  'health.services.ai_config.status': field('health.services.ai_config.status'),
  'health.services.ai_config.provider': field('health.services.ai_config.provider'),
  'health.services.ai_config.model': field('health.services.ai_config.model'),
  'health.services.ai_config.base_url': field('health.services.ai_config.base_url'),
  'health.services.ai_config.search_model': field('health.services.ai_config.search_model'),
  'health.services.ai_config.configured': field('health.services.ai_config.configured'),
  'health.services.database.status': field('health.services.database.status'),
  'health.services.tencent_api.status': field('health.services.tencent_api.status'),
  'health.services.cache.status': field('health.services.cache.status'),
  'health.services.scheduler.status': field('health.services.scheduler.status'),
  'accuracy.metrics.mean_crps': field('accuracy.metrics.mean_crps'),
  'accuracy.metrics.mean_crps_flat': field('accuracy.metrics.mean_crps_flat'),
  'accuracy.metrics.crps_skill_vs_flat': field('accuracy.metrics.crps_skill_vs_flat'),
  'accuracy.metrics.crps_samples': field('accuracy.metrics.crps_samples'),
  'accuracy.metrics.nonoverlapping_samples': field('accuracy.metrics.nonoverlapping_samples'),
  'accuracy.metrics.accuracy_nonoverlapping': field('accuracy.metrics.accuracy_nonoverlapping'),
  'accuracy.metrics.coverage_nonoverlapping': field('accuracy.metrics.coverage_nonoverlapping'),
  'accuracy.metrics.magnitude_mape': field('accuracy.metrics.magnitude_mape'),
  'accuracy.metrics.magnitude_skill_vs_flat': field('accuracy.metrics.magnitude_skill_vs_flat'),
  'accuracy.metrics.interval_sharpness_80': field('accuracy.metrics.interval_sharpness_80'),
  'accuracy.metrics.effective_sample_size': field('accuracy.metrics.effective_sample_size'),
  'accuracy.metrics.expected_cap_rate': field('accuracy.metrics.expected_cap_rate'),
  'accuracy.metrics.down_calls': field('accuracy.metrics.down_calls'),
  'accuracy.metrics.down_call_accuracy': field('accuracy.metrics.down_call_accuracy'),
  'accuracy.metrics.down_call_edge_vs_up': field('accuracy.metrics.down_call_edge_vs_up'),
  'accuracy.metrics.accuracy_ci95': field('accuracy.metrics.accuracy_ci95'),
  'accuracy.metrics.p_value_vs_up': field('accuracy.metrics.p_value_vs_up'),
  'accuracy.metrics.accuracy_diff_vs_up': field('accuracy.metrics.accuracy_diff_vs_up'),
  'accuracy.metrics.direction_edge_vs_up_ci95': field('accuracy.metrics.direction_edge_vs_up_ci95'),
  'accuracy.history.mean_crps': field('accuracy.history.mean_crps'),
  'accuracy.history.brier_score': field('accuracy.history.brier_score'),
})

export const TESTIDS = Object.freeze({
  // 结构性选择器（e2e / 截图脚本使用）
  app: 'gm-app',
  header: 'gm-header',
  headerNav: 'gm-nav',
  freshnessBar: 'freshness-bar',
  freshnessState: 'freshness-state',
  freshnessItemPrefix: 'freshness-item-',
  todaySummary: 'today-summary',
  sectionConclusion: 'conclusion',
  sectionMarket: 'market',
  sectionDrivers: 'drivers',
  sectionMessages: 'messages',
  sectionQuant: 'quant',
  sectionStrategy: 'strategy',
  sectionData: 'data-methods',
  driversBullish: 'drivers-bullish',
  driversBearish: 'drivers-bearish',
  driversMessages: 'drivers-messages',
  driversInstitutions: 'drivers-institutions',
  bullishFactors: 'bullish-factors',
  bearishFactors: 'bearish-factors',
  messagesWindows: 'messages-windows',
  messageReport: 'messages-report',
  institutionsSummary: 'institutions-summary',
  institutionsTable: 'institutions-table',
  marketUnavailable: 'market-unavailable',
  marketStats: 'market-stats',
  marketChart: 'market-chart',
  correlationTable: 'correlation-table',
  dailyTable: 'daily-table',
  dollarQuote: 'dollar-quote',
  goldQuote: 'gold-quote',
  conclusionSummary: 'conclusion-summary',
  conclusionDetails: 'conclusion-details',
  conclusionTargets: 'conclusion-targets',
  quantFairValue: 'quant-fair-value',
  quantScaleTable: 'quant-scale-table',
  quantMonitorTable: 'quant-monitor-table',
  quantMonitorParticipating: 'quant-monitor-participating',
  quantMonitorInfoOnly: 'quant-monitor-info-only',
  quantAccuracy: 'quant-accuracy',
  quantAccuracyHistory: 'quant-accuracy-history',
  quantFactorTable: 'quant-factor-table',
  quantUnavailable: 'quant-unavailable',
  strategyColumns: 'strategy-columns',
  dataSourcesStatus: 'data-sources-status',
  dataBootstrap: 'data-bootstrap',
  dataConfigWatch: 'data-config-watch',
  dataSync: 'data-sync',
  dataLegend: 'data-legend',
  researchVerdict: 'research-verdict',
  researchForwardWindow: 'research-forward-window',
  researchOverview: 'research-overview',
  researchCoverage: 'research-coverage',
  researchDiagnostics: 'research-diagnostics',
  researchRegimes: 'research-regimes',
  researchBenchmarks: 'research-benchmarks',
  researchFactors: 'research-factors',
  researchSync: 'research-sync',
  researchDataWindow: 'research-data-window',
  // 字段级选择器（字段覆盖测试按 data-testid 逐个断言）
  field: Object.freeze({
    'stats.current_price': field('stats.current_price'),
    'stats.start_price': field('stats.start_price'),
    'stats.window_label': field('stats.window_label'),
    'stats.window_start': field('stats.window_start'),
    'stats.window_end': field('stats.window_end'),
    'stats.window_return': field('stats.window_return'),
    'stats.max_price': field('stats.max_price'),
    'stats.min_price': field('stats.min_price'),
    'stats.max_date': field('stats.max_date'),
    'stats.min_date': field('stats.min_date'),
    'stats.amplitude': field('stats.amplitude'),
    'stats.market_status': field('stats.market_status'),
    'stats.market_status_desc': field('stats.market_status_desc'),
    'stats.updated_at': field('stats.updated_at'),
    'stats.data_source': field('stats.data_source'),
    'stats.is_realtime': field('stats.is_realtime'),
    'stats.price_basis': field('stats.price_basis'),
    'stats.price_basis_label': field('stats.price_basis_label'),
    'stats.price_as_of': field('stats.price_as_of'),
    'daily.date': field('daily.date'),
    'daily.price': field('daily.price'),
    'daily.volume': field('daily.volume'),
    'daily.basis': field('daily.basis'),
    'daily.basis_label': field('daily.basis_label'),
    'daily.source': field('daily.source'),
    'daily.as_of': field('daily.as_of'),
    'correlation.date': field('correlation.date'),
    'correlation.gold_price': field('correlation.gold_price'),
    'correlation.dollar_index': field('correlation.dollar_index'),
    'correlation.gold_basis': field('correlation.gold_basis'),
    'correlation.gold_basis_label': field('correlation.gold_basis_label'),
    'correlation.gold_source': field('correlation.gold_source'),
    'correlation.dollar_basis': field('correlation.dollar_basis'),
    'correlation.dollar_basis_label': field('correlation.dollar_basis_label'),
    'correlation.dollar_source': field('correlation.dollar_source'),
    'correlation.as_of': field('correlation.as_of'),
    'dollar.price': field('dollar.price'),
    'dollar.previous_close': field('dollar.previous_close'),
    'dollar.change': field('dollar.change'),
    'dollar.change_percent': field('dollar.change_percent'),
    'dollar.open': field('dollar.open'),
    'dollar.high': field('dollar.high'),
    'dollar.low': field('dollar.low'),
    'dollar.updated_at': field('dollar.updated_at'),
    'dollar.date': field('dollar.date'),
    'dollar.source': field('dollar.source'),
    'summary.core_view': field('summary.core_view'),
    'summary.current_price': field('summary.current_price'),
    // 当前价的时间 / 口径 / 来源：金价出现在哪儿，时间就跟到哪儿
    'summary.price_as_of': field('summary.price_as_of'),
    'summary.price_basis_label': field('summary.price_basis_label'),
    'summary.price_source': field('summary.price_source'),
    'summary.confidence_level': field('summary.confidence_level'),
    'summary.time_horizon': field('summary.time_horizon'),
    'summary.investment_recommendation': field('summary.investment_recommendation'),
    'summary.core_bullish_logic': field('summary.core_bullish_logic'),
    'summary.main_risks': field('summary.main_risks'),
    'summary.market_consensus': field('summary.market_consensus'),
    'summary.comprehensive_judgment.bullish_summary': field('summary.comprehensive_judgment.bullish_summary'),
    'summary.comprehensive_judgment.bearish_summary': field('summary.comprehensive_judgment.bearish_summary'),
    'summary.comprehensive_judgment.neutral_summary': field('summary.comprehensive_judgment.neutral_summary'),
    'summary.institution_targets.institution': field('summary.institution_targets.institution'),
    'summary.institution_targets.target': field('summary.institution_targets.target'),
    'summary.institution_targets.probability': field('summary.institution_targets.probability'),
    'summary.institution_targets.timeframe': field('summary.institution_targets.timeframe'),    ...prediction,
    ...scenarios,
    ...factorSnapshots,
    ...factorCoverage,
    ...factorContributions,
    ...monitor,
    ...researchHorizons,
    ...forwardReadiness,
    ...forwardPosterior,
    ...researchFactors,
    ...researchReliability,
    ...digestItems,
    ...digestRelated,
    ...digestFetch,
    ...digestFetchSources,
    ...institutions,
    ...bullishItems,
    ...bearishItems,
    ...digestWindows,
    ...digestResponse,
    ...digestTranslation,
    ...principles,
    ...accuracyFactors,
    ...accuracyRegimePre,
    ...accuracyRegimePost,
    ...extras,
    ...strategy,
    ...entry,
    ...exit,
    ...snapshot,
    ...assessment,
    ...metadata,
    ...sourcesStatus,
    ...sourcesSummary,
    ...bootstrapPhases,
    ...configWatch,
    research: Object.freeze({
      model_version: field('research.model_version'),
      status: field('research.status'),
      reason: field('research.reason'),
      as_of: field('research.as_of'),
      data_window_start: field('research.data_window.start'),
      data_window_end: field('research.data_window.end'),
      data_window_trading_days: field('research.data_window.trading_days'),
      data_window_years: field('research.data_window.years'),
      holdout_start: field('research.holdout_start'),
      active_holdout_start: field('research.active_holdout_start'),
      generated_at: field('research.generated_at'),
      cached: field('research.cached'),
      verdict_status: field('research.verdict.status'),
      verdict_label: field('research.verdict.label'),
      verdict_detail: field('research.verdict.detail'),
      benchmark_key: field('research.benchmark.key'),
      benchmark_name: field('research.benchmark.name'),
      benchmark_note: field('research.benchmark.note'),
      benchmark_alternative_key: field('research.benchmark.alternatives.key'),
      benchmark_alternative_name: field('research.benchmark.alternatives.name'),
      benchmark_alternative_note: field('research.benchmark.alternatives.note'),
      benchmark_alternative_available: field('research.benchmark.alternatives.available'),
      benchmark_alternative_reason: field('research.benchmark.alternatives.reason'),
      regime_key: field('research.regimes.key'),
      regime_name: field('research.regimes.name'),
      regime_series_key: field('research.regimes.series_key'),
      regime_description: field('research.regimes.description'),
      regime_status: field('research.regimes.status'),
      regime_note: field('research.regimes.note'),
      periods: researchPeriods,
    }),
    health: Object.freeze({
      status: field('health.status'),
      timestamp: field('health.timestamp'),
      version: field('health.version'),
      bootstrap_enabled: field('health.bootstrap.enabled'),
      bootstrap_status: field('health.bootstrap.status'),
      bootstrap_ready: field('health.bootstrap.ready'),
      bootstrap_step_index: field('health.bootstrap.step.index'),
      bootstrap_step_total: field('health.bootstrap.step.total'),
      bootstrap_error: field('health.bootstrap.error'),
      bootstrap_started_at: field('health.bootstrap.started_at'),
      bootstrap_finished_at: field('health.bootstrap.finished_at'),
      bootstrap_migrations: field('health.bootstrap.migrations'),
      phases: bootstrapPhases,
      gaps: build([
        'health.bootstrap.gaps.gold_prices.rows',
        'health.bootstrap.gaps.gold_prices.last_date',
        'health.bootstrap.gaps.dollar_index.rows',
        'health.bootstrap.gaps.dollar_index.last_date',
        'health.bootstrap.gaps.gold_news.rows',
        'health.bootstrap.gaps.gold_news.last_published_at',
        'health.bootstrap.gaps.news_digest.rows',
        'health.bootstrap.gaps.news_digest.last_published_at',
        'health.bootstrap.gaps.quant.series_without_data',
        'health.bootstrap.gaps.quant.sparse_year_count',
        'health.bootstrap.gaps.quant.window_years',
      ]),
      config_watch: configWatch,
    }),    'sources.generated_at': field('sources.generated_at'),
    'quant.model_version': field('quant.model_version'),
    'quant.as_of': field('quant.as_of'),
    'quant.available_factors': field('quant.available_factors'),
    'quant.total_factors': field('quant.total_factors'),
    'quant.unavailable_reason': field('quant.unavailable_reason'),
    'quant.sync.started_at': field('quant.sync.started_at'),
    'quant.sync.finished_at': field('quant.sync.finished_at'),
    'quant.sync.sources_ok': field('quant.sync.sources_ok'),
    'quant.sync.sources_total': field('quant.sync.sources_total'),
    'quant.source.name': field('quant.source.name'),
    'quant.source.label': field('quant.source.label'),
    'quant.source.status': field('quant.source.status'),
    'quant.source.error': field('quant.source.error'),
    'quant.source.reason': field('quant.source.reason'),
    'quant.category.key': field('quant.category.key'),
    'quant.category.name': field('quant.category.name'),
    'quant.category.total': field('quant.category.total'),
    'quant.category.available': field('quant.category.available'),
    'fair_value.status': field('fair_value.status'),
    'fair_value.reason': field('fair_value.reason'),
    'fair_value.as_of': field('fair_value.as_of'),
    'fair_value.basis': field('fair_value.basis'),
    'fair_value.basis_label': field('fair_value.basis_label'),
    'fair_value.market_price': field('fair_value.market_price'),
    'fair_value.fair_value': field('fair_value.fair_value'),
    'fair_value.deviation_pct': field('fair_value.deviation_pct'),
    'fair_value.r2': field('fair_value.r2'),
    'fair_value.samples': field('fair_value.samples'),
    'fair_value.blocks.key': field('fair_value.blocks.key'),
    'fair_value.blocks.name': field('fair_value.blocks.name'),
    'fair_value.blocks.usd': field('fair_value.blocks.usd'),
    'fair_value.blocks.share_pct': field('fair_value.blocks.share_pct'),
    'fair_value.blocks.drivers.key': field('fair_value.blocks.drivers.key'),
    'fair_value.blocks.drivers.name': field('fair_value.blocks.drivers.name'),
    'fair_value.blocks.drivers.log_contribution': field('fair_value.blocks.drivers.log_contribution'),
    'predictions.price_basis.basis': field('predictions.price_basis.basis'),
    'predictions.price_basis.label': field('predictions.price_basis.label'),
    'predictions.price_basis.source': field('predictions.price_basis.source'),
    'predictions.price_basis.as_of': field('predictions.price_basis.as_of'),
    'accuracy.model_version': field('accuracy.model_version'),
    'accuracy.latest.horizon_days': field('accuracy.latest.horizon_days'),
    'accuracy.latest.evaluated_at': field('accuracy.latest.evaluated_at'),
    'accuracy.latest.window_start': field('accuracy.latest.window_start'),
    'accuracy.latest.window_end': field('accuracy.latest.window_end'),
    'accuracy.latest.sample_size': field('accuracy.latest.sample_size'),
    'accuracy.latest.accuracy': field('accuracy.latest.accuracy'),
    'accuracy.latest.baseline_up_accuracy': field('accuracy.latest.baseline_up_accuracy'),
    'accuracy.latest.baseline_momentum_accuracy': field('accuracy.latest.baseline_momentum_accuracy'),
    'accuracy.latest.brier_score': field('accuracy.latest.brier_score'),
    'accuracy.latest.metrics.interval_nominal_80': field('accuracy.latest.metrics.interval_nominal_80'),
    'accuracy.latest.metrics.interval_coverage_80': field('accuracy.latest.metrics.interval_coverage_80'),
    'accuracy.latest.metrics.score_direction_accuracy': field('accuracy.latest.metrics.score_direction_accuracy'),
    'accuracy.latest.metrics.regimes.split_date': field('accuracy.latest.metrics.regimes.split_date'),
    'accuracy.latest.metrics.regimes.note': field('accuracy.latest.metrics.regimes.note'),
    'accuracy.latest.metrics.reason': field('accuracy.latest.metrics.reason'),
    'accuracy.latest.reason': field('accuracy.latest.reason'),
    'accuracy.history.evaluated_at': field('accuracy.history.evaluated_at'),
    'accuracy.history.horizon_days': field('accuracy.history.horizon_days'),
    'accuracy.history.window_start': field('accuracy.history.window_start'),
    'accuracy.history.window_end': field('accuracy.history.window_end'),
    'accuracy.history.sample_size': field('accuracy.history.sample_size'),
    'accuracy.history.accuracy': field('accuracy.history.accuracy'),
    'accuracy.history.reason': field('accuracy.history.reason'),
  }),
})

export type TestIds = typeof TESTIDS