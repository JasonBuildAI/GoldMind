import { displayStamp } from '@/lib/format'
import type { ApiMetadata } from '@/lib/placeholder'
import { fieldTestId } from '@/testids'

/** 分析元信息：每个字段都有槽位；缺失显示「—」，不补默认值。 */
export default function MetadataBlock({
  metadata,
  testId,
}: {
  metadata?: ApiMetadata | null
  testId?: string
}) {
  if (!metadata) return null
  return (
    <dl className="metrics" data-testid={testId}>
      <div>
        <dt>状态</dt>
        <dd data-testid={fieldTestId('metadata.status')}>{metadata.status ?? '—'}</dd>
      </div>
      <div>
        <dt>缓存</dt>
        <dd data-testid={fieldTestId('metadata.cached')}>
          {metadata.cached === undefined ? '—' : metadata.cached ? '缓存' : '本次现算'}
        </dd>
      </div>
      <div>
        <dt>缓存来源</dt>
        <dd data-testid={fieldTestId('metadata.cache_source')}>{metadata.cache_source ?? '—'}</dd>
      </div>
      <div>
        <dt>提示</dt>
        <dd data-testid={fieldTestId('metadata.message')}>{metadata.message ?? '—'}</dd>
      </div>
      <div>
        <dt>生成时间</dt>
        <dd data-testid={fieldTestId('metadata.generated_at')}>
          {displayStamp(metadata.generated_at) ?? '—'}
        </dd>
      </div>
      <div>
        <dt>数据来源</dt>
        <dd data-testid={fieldTestId('metadata.data_sources')}>
          {metadata.data_sources?.join('、') || '—'}
        </dd>
      </div>
      <div>
        <dt>分析方法</dt>
        <dd data-testid={fieldTestId('metadata.analysis_method')}>
          {metadata.analysis_method ?? '—'}
        </dd>
      </div>
    </dl>
  )
}