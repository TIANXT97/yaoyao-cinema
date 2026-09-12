/**
 * useInfiniteScroll —— 无限滚动触发器（基于 IntersectionObserver）。
 */

import { onBeforeUnmount, onMounted, ref, type Ref } from 'vue'

export interface UseInfiniteScrollOptions {
  /** 触发回调。 */
  onLoad: () => void
  /** 是否禁用（如已无更多数据）。 */
  disabled?: () => boolean
  /** 预加载边距。 */
  rootMargin?: string
  /** 观察目标元素。 */
  target: Ref<HTMLElement | null>
}

export function useInfiniteScroll(options: UseInfiniteScrollOptions): {
  active: Ref<boolean>
  check: () => void
} {
  const active = ref(false)
  let observer: IntersectionObserver | null = null

  const trigger = (): void => {
    if (options.disabled?.()) return
    options.onLoad()
  }

  onMounted(() => {
    const el = options.target.value
    if (!el || typeof IntersectionObserver === 'undefined') {
      active.value = true
      return
    }

    observer = new IntersectionObserver(
      (entries) => {
        const entry = entries[0]
        if (entry?.isIntersecting) trigger()
      },
      { root: null, rootMargin: options.rootMargin ?? '320px 0px', threshold: 0 },
    )
    observer.observe(el)
  })

  onBeforeUnmount(() => {
    observer?.disconnect()
    observer = null
  })

  /** 手动检查（当内容不足以撑出滚动条时）。 */
  function check(): void {
    trigger()
  }

  return { active, check }
}
