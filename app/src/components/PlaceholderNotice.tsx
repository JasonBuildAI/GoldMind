import { PLACEHOLDER_NOTICE } from '@/lib/placeholder';

/**
 * 占位内容提示条。
 *
 * 只在接口明确表示「还在分析、这是占位内容」时渲染。
 * 单独抽成组件，是为了让各 section 用同一句话、同一个样式说明这件事 ——
 * 否则很容易在某个区块漏掉，用户就会把内置常量当成分析结论。
 */
export default function PlaceholderNotice({
  show,
  testId,
}: {
  show: boolean;
  testId?: string;
}) {
  if (!show) return null;

  return (
    <span
      data-testid={testId}
      role="status"
      className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-amber-500/10 border border-amber-500/30 text-amber-400 text-xs"
    >
      {PLACEHOLDER_NOTICE}
    </span>
  );
}
