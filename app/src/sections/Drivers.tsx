import Section from '@/components/Section'
import { TESTIDS } from '@/testids'
import Factors from './Factors'
import Institutions from './Institutions'
import Messages from './Messages'

/**
 * 驱动：看涨 / 看跌因素、消息与机构观点 —— 四路证据集中在同一节里，
 * 各自的取数与刷新互相独立，谁取不到只影响自己。
 */
export default function Drivers() {
  return (
    <Section
      id="drivers"
      title="驱动"
      intro="看涨与看跌因素的逐条论据、高权威消息与机构目标价 —— 每条证据都带来源与数据截至；取不到的一路只影响自己。"
      actions={null}
    >
      <div className="space-y-8" data-testid={TESTIDS.sectionDrivers}>
        <Factors />
        <Messages />
        <Institutions />
      </div>
    </Section>
  )
}