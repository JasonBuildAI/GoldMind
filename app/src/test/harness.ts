import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia, type Pinia } from 'pinia'

/**
 * 区块测试的统一入口。
 *
 * 三件事各写一遍容易漏：装 Pinia（组件读新鲜度 / 行情 store）、attach 到
 * `document.body`（区块用 `document` 查询）、以及给容器一个唯一标记
 * （测试里按根元素收窄查询范围，避免与上一个用例的残留 DOM 相互干扰）。
 *
 * 类型上刻意放宽到 `any`：`mount` 的泛型会随传入组件推出一整套
 * `ComponentProps<C>`，在「组件是变量」的场景（测试夹具、守卫循环挂载）里
 * 它只会把调用点淹没在类型体操里，而这里要的只是「挂上、拿到根元素、能查询」。
 */
export interface Mounted {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  wrapper: any
  /** 组件挂载的根元素；查询一律从它出发 */
  root: HTMLElement
  cleanup: () => void
}

let counter = 0

export function mountBlock(
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  component: any,
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  options: { pinia?: Pinia; props?: Record<string, any> } = {},
): Mounted {
  const pinia = options.pinia ?? createPinia()
  if (!options.pinia) setActivePinia(pinia)

  const host = document.createElement('div')
  host.className = `gm-test-${(counter += 1)}`
  document.body.appendChild(host)

  const wrapper = mount(component, {
    attachTo: host,
    props: options.props,
    global: { plugins: [pinia] },
  })

  return {
    wrapper,
    root: wrapper.element as HTMLElement,
    cleanup: () => {
      wrapper.unmount()
      host.remove()
    },
  }
}

/**
 * 收集一批挂载实例，返回统一的清理函数 —— 用例结束时调用，
 * 否则上一个用例的 DOM 会留在 document 里污染下一个。
 */
export function createBlockHarness() {
  const mounted: Mounted[] = []
  return {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    mount(component: any, options: { pinia?: Pinia; props?: Record<string, any> } = {}): Mounted {
      const instance = mountBlock(component, options)
      mounted.push(instance)
      return instance
    },
    cleanup(): void {
      for (const instance of mounted) instance.cleanup()
      mounted.length = 0
    },
  }
}

/** 区块内可见文本（收窄到组件根元素，不含别的用例残留）。 */
export function textOf(root: HTMLElement): string {
  return root.textContent ?? ''
}

/** 区块内是否有匹配文本的元素。 */
export function hasText(root: HTMLElement, needle: string | RegExp): boolean {
  return [...root.querySelectorAll('*')].some((node) => {
    const value = node.textContent ?? ''
    return typeof needle === 'string' ? value.includes(needle) : needle.test(value)
  })
}

/** 按 data-testid 取元素（区块内）。 */
export function byTestId(root: HTMLElement, id: string): HTMLElement | null {
  return root.querySelector<HTMLElement>(`[data-testid="${id}"]`)
}

/** 按可见文案取按钮。 */
export function buttonByText(root: HTMLElement, label: string): HTMLButtonElement | undefined {
  return [...root.querySelectorAll('button')].find((button) =>
    (button.textContent ?? '').includes(label),
  )
}
