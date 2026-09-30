import { modelLabel, useAiConfig } from '@/hooks/useAiConfig'
import { displayStamp } from '@/lib/format'

/**
 * 分析区块的署名行：谁生成的、什么时候生成的。
 *
 * 模型名从 /health 读（见 useAiConfig），分析时间只用后端返回的字段 ——
 * 两者都不许猜。读不到模型名时如实写「模型未知」，不硬编码一个型号。
 */
export default function SignOff({ generatedAt }: { generatedAt?: string | null }) {
  const config = useAiConfig()
  const model = config?.model ? modelLabel(config) : '模型未知（/health 未返回）'
  const stamp = displayStamp(generatedAt)

  return (
    <p className="provenance">
      由 {model} 生成
      {stamp ? ` · 分析时间 ${stamp}` : ''}
      {' · 仅供参考'}
    </p>
  )
}
