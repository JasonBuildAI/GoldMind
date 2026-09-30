import type { ReactNode } from 'react'

/**
 * 研究简报的一节：锚点、标题、一句话说明、操作区。
 * 层级由细线、字号与留白建立 —— 不用卡片、不用编号装饰。
 */
export default function Section({
  id,
  title,
  intro,
  actions,
  children,
}: {
  id: string
  title: string
  intro?: string
  actions?: ReactNode
  children: ReactNode
}) {
  return (
    <section id={id} className="section" aria-labelledby={`${id}-title`}>
      <div className="section__head">
        <div>
          <h2 id={`${id}-title`} className="section__title">
            {title}
          </h2>
          {intro ? <p className="section__intro">{intro}</p> : null}
        </div>
        {actions ? <div className="section__actions">{actions}</div> : null}
      </div>
      {children}
    </section>
  )
}
