/**
 * usePlatform —— 平台 / 设备检测（响应式）。
 */

import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

import {
  deviceKind,
  isAndroid,
  isIOS,
  isStandalonePWA,
  isTouchDevice,
  type DeviceKind,
} from '@/utils/platform'

export function usePlatform() {
  const width = ref(typeof window !== 'undefined' ? window.innerWidth : 1280)
  const kind = ref<DeviceKind>(deviceKind())

  const onResize = (): void => {
    width.value = window.innerWidth
    kind.value = deviceKind()
  }

  onMounted(() => {
    window.addEventListener('resize', onResize, { passive: true })
    onResize()
  })

  onBeforeUnmount(() => {
    window.removeEventListener('resize', onResize)
  })

  return {
    width,
    kind,
    isIOS: computed(() => isIOS()),
    isAndroid: computed(() => isAndroid()),
    isStandalone: computed(() => isStandalonePWA()),
    isTouch: computed(() => isTouchDevice()),
    isMobile: computed(() => kind.value === 'mobile'),
    isTablet: computed(() => kind.value === 'tablet'),
    isDesktop: computed(() => kind.value === 'desktop'),
  }
}
