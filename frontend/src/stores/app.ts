/**
 * 全局 App Store（设备信息、网络状态、UI 偏好）。
 */

import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { deviceKind, isStandalonePWA, type DeviceKind } from '@/utils/platform'

export const useAppStore = defineStore('app', () => {
  const device = ref<DeviceKind>(deviceKind())
  const standalone = ref(isStandalonePWA())
  const online = ref(typeof navigator !== 'undefined' ? navigator.onLine : true)
  const initialized = ref(false)

  const isMobile = computed(() => device.value === 'mobile')

  function refresh(): void {
    device.value = deviceKind()
    standalone.value = isStandalonePWA()
    online.value = typeof navigator !== 'undefined' ? navigator.onLine : true
  }

  function init(): void {
    if (initialized.value || typeof window === 'undefined') return
    initialized.value = true
    refresh()
    window.addEventListener('resize', refresh, { passive: true })
    window.addEventListener('online', refresh)
    window.addEventListener('offline', refresh)
  }

  return { device, standalone, online, initialized, isMobile, refresh, init }
})
