/**
 * useApi —— 轻量异步请求状态封装（loading / data / error）。
 */

import { ref, shallowRef, type Ref } from 'vue'

import { ApiError } from '@/api/client'

export interface UseApiOptions {
  /** 首次调用是否立即执行。 */
  immediate?: boolean
}

export interface UseApiReturn<T, A extends unknown[]> {
  data: Ref<T | null>
  error: Ref<string | null>
  loading: Ref<boolean>
  execute: (...args: A) => Promise<T | null>
  reset: () => void
}

/** 将任意异步任务包装为响应式状态。 */
export function useApi<T, A extends unknown[] = []>(
  task: (...args: A) => Promise<T>,
  options: UseApiOptions = {},
): UseApiReturn<T, A> {
  const data = shallowRef<T | null>(null)
  const error = ref<string | null>(null)
  const loading = ref(false)

  async function execute(...args: A): Promise<T | null> {
    loading.value = true
    error.value = null
    try {
      const result = await task(...args)
      data.value = result
      return result
    } catch (err) {
      error.value =
        err instanceof ApiError ? err.message : '操作失败，请稍后重试'
      return null
    } finally {
      loading.value = false
    }
  }

  function reset(): void {
    data.value = null
    error.value = null
    loading.value = false
  }

  if (options.immediate) {
    void execute(...([] as unknown as A))
  }

  return { data, error, loading, execute, reset }
}
