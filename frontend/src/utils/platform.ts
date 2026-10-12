/**
 * 平台判断辅助（浏览器端，无 Capacitor 依赖）。
 */

export function isBrowser(): boolean {
  return typeof window !== 'undefined'
}

export function isTouchDevice(): boolean {
  if (!isBrowser()) return false
  return 'ontouchstart' in window || navigator.maxTouchPoints > 0
}

export function isIOS(): boolean {
  if (!isBrowser()) return false
  const ua = navigator.userAgent
  return (
    /iPad|iPhone|iPod/.test(ua) ||
    (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1)
  )
}

export function isAndroid(): boolean {
  return isBrowser() && /Android/i.test(navigator.userAgent)
}

/** 是否处于 Capacitor 原生移动容器中。 */
export function isCapacitorNative(): boolean {
  if (!isBrowser()) return false
  const w = window as unknown as { Capacitor?: { isNativePlatform?: () => boolean } }
  if (w.Capacitor?.isNativePlatform) {
    try {
      return w.Capacitor.isNativePlatform()
    } catch {
      // 容错处理
    }
  }
  // Android / iOS Capacitor 容器环境下的经典协议或主机特征
  const loc = window.location
  return loc.protocol === 'capacitor:' || loc.hostname === 'localhost' && /Android/i.test(navigator.userAgent)
}

/** 是否已作为 PWA 独立窗口运行。 */
export function isStandalonePWA(): boolean {
  if (!isBrowser()) return false
  return (
    window.matchMedia('(display-mode: standalone)').matches ||
    // iOS Safari 专有属性
    (navigator as Navigator & { standalone?: boolean }).standalone === true
  )
}

/** 粗略设备类型。 */
export type DeviceKind = 'mobile' | 'tablet' | 'desktop'

export function deviceKind(): DeviceKind {
  if (!isBrowser()) return 'desktop'
  const width = window.innerWidth
  if (width < 768) return 'mobile'
  if (width < 1024) return 'tablet'
  return 'desktop'
}

/** 设备标识（用于观看历史上报）。 */
export function deviceLabel(): string {
  if (isStandalonePWA()) {
    if (isIOS()) return 'iOS PWA'
    if (isAndroid()) return 'Android PWA'
    return 'PWA'
  }
  if (isIOS()) return 'iOS Safari'
  if (isAndroid()) return 'Android Browser'
  return 'Web Browser'
}
