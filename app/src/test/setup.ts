// vitest 全局初始化
import '@testing-library/jest-dom/vitest'

// happy-dom 没有实现 IntersectionObserver，而多个 section 用它做入场动画。
// 提供一个最小可用的替身：观察即视为已进入视口（立刻回调一次），
// 这样组件的渲染逻辑能被完整执行。
class StubIntersectionObserver implements IntersectionObserver {
  readonly root: Element | Document | null = null
  readonly rootMargin: string = ''
  readonly thresholds: ReadonlyArray<number> = []

  private readonly callback: IntersectionObserverCallback

  constructor(callback: IntersectionObserverCallback) {
    this.callback = callback
  }

  observe(target: Element): void {
    this.callback(
      [
        {
          isIntersecting: true,
          target,
          intersectionRatio: 1,
          time: 0,
          boundingClientRect: target.getBoundingClientRect(),
          intersectionRect: target.getBoundingClientRect(),
          rootBounds: null,
        } as IntersectionObserverEntry,
      ],
      this,
    )
  }

  unobserve(): void {}
  disconnect(): void {}
  takeRecords(): IntersectionObserverEntry[] {
    return []
  }
}

globalThis.IntersectionObserver =
  StubIntersectionObserver as unknown as typeof IntersectionObserver
