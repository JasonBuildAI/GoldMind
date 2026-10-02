/**
 * 手动触发一次分析。按钮文案在「分析中…」与动作名之间切换，
 * 名称就是动作本身（重新分析 / 重新抓取），不用「提交」这类抽象词。
 */
export default function RefreshButton({
  onClick,
  busy,
  label,
  busyLabel = '分析中…',
}: {
  onClick: () => void
  busy: boolean
  label: string
  busyLabel?: string
}) {
  return (
    <button type="button" className="btn no-print" onClick={onClick} disabled={busy}>
      {busy ? busyLabel : label}
    </button>
  )
}
