/**
 * 判断接口返回的是「占位内容」还是真实分析。
 *
 * 背景：缓存未命中时，后端会立刻返回一份内置的默认内容（好让页面不至于空白），
 * 并在后台真正跑一次分析。问题是这份占位内容在结构上与真实分析**完全一样** ——
 * 前端如果不看 `metadata` 就分辨不出来，于是页面会把内置常量当成分析结论展示。
 *
 * 两种标记都实际出现过：
 *   - 看涨/看跌因子、机构预测、投资建议：`status === 'analyzing'`
 *   - 市场总结：`cache_source === 'default'`
 */
export interface ApiMetadata {
  cached?: boolean;
  status?: string;
  cache_source?: string;
  message?: string;
  generated_at?: string;
  data_sources?: string[];
  analysis_method?: string;
}

export function isPlaceholder(metadata?: ApiMetadata | null): boolean {
  if (!metadata) return false;
  return metadata.status === 'analyzing' || metadata.cache_source === 'default';
}

/** 占位内容旁边要显示的提示语。 */
export const PLACEHOLDER_NOTICE =
  '正在分析最新数据，以下为占位内容，不是本次分析结果，请稍后刷新';
