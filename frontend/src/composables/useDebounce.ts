/**
 * useDebounce —— 防抖 / 节流工具（搜索即时过滤 300ms）。
 */

import { onBeforeUnmount } from 'vue'

/** 防抖函数：延迟 delay 毫秒后执行，重复调用会重置计时。 */
export function useDebounceFn<A extends unknown[]>(
  fn: (...args: A) => void,
  delay = 300,
): (...args: A) => void {
  let timer: ReturnType<typeof setTimeout> | null = null

  const wrapped = (...args: A): void => {
    if (timer) clearTimeout(timer)
    timer = setTimeout(() => {
      timer = null
      fn(...args)
    }, delay)
  }

  const cancel = (): void => {
    if (timer) {
      clearTimeout(timer)
      timer = null
    }
  }

  onBeforeUnmount(cancel)
  return wrapped
}

/** 节流函数：interval 毫秒内最多执行一次（尾部补执行）。 */
export function useThrottleFn<A extends unknown[]>(
  fn: (...args: A) => void,
  interval = 200,
): (...args: A) => void {
  let last = 0
  let timer: ReturnType<typeof setTimeout> | null = null

  const invoke = (args: A): void => {
    last = Date.now()
    fn(...args)
  }

  const wrapped = (...args: A): void => {
    const now = Date.now()
    const remaining = interval - (now - last)
    if (remaining <= 0) {
      if (timer) {
        clearTimeout(timer)
        timer = null
      }
      invoke(args)
    } else if (!timer) {
      timer = setTimeout(() => {
        timer = null
        invoke(args)
      }, remaining)
    }
  }

  const cancel = (): void => {
    if (timer) {
      clearTimeout(timer)
      timer = null
    }
  }

  onBeforeUnmount(cancel)
  return wrapped
}
