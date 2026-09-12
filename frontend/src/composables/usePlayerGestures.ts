/**
 * usePlayerGestures —— 全屏播放器手势识别（自研，无第三方依赖）。
 *
 * 手势映射（ARCHITECTURE.md 3.2.4）：
 * ┌────────────────────────────────────┐
 * │  左半区上下滑 = 亮度调节           │
 * │  右半区上下滑 = 音量调节           │
 * │  左右滑       = 快进 / 后退        │
 * │  单击         = 切换控件显隐       │
 * │  双击左       = 后退 10s           │
 * │  双击右       = 前进 10s           │
 * └────────────────────────────────────┘
 */

import { onBeforeUnmount, ref, type Ref } from 'vue'

import { SEEK_STEP } from '@/utils/constants'
import { clamp, formatClock } from '@/utils/format'

export type GestureKind = 'none' | 'seek' | 'volume' | 'brightness'
export type SeekFlash = 'back' | 'forward' | null

/** 双击快进/快退居中动画提示数据 */
export interface DoubleTapHint {
  visible: boolean
  label: string
  /** 'left' | 'right' 标识双击区域 */
  side: 'left' | 'right'
  /** 用于触发新动画的递增 key */
  key: number
}

export interface GestureFeedback {
  kind: GestureKind
  /** 归一化数值（音量 / 亮度为 0~1；快进为秒数，可正可负）。 */
  value: number
  label: string
  visible: boolean
}

export interface PlayerGestureOptions {
  /** 当前视频元素。 */
  video: () => HTMLVideoElement | null
  /** 相对快进（秒，正为前进）。 */
  seekBy: (deltaSeconds: number) => void
  /** 设置音量（0~1）。 */
  setVolume: (volume: number) => void
  /** 设置亮度（0.1~1）。 */
  setBrightness: (brightness: number) => void
  getVolume: () => number
  getBrightness: () => number
  /** 单击切换控件。 */
  toggleControls: () => void
  /** 任意手势活动（用于重置控件自动隐藏）。 */
  onActivity?: () => void
}

/** 单击/双击判定窗口（毫秒）。 */
const DOUBLE_TAP_MS = 300
const MOVE_THRESHOLD = 10
const SEEK_SECONDS_PER_PX = 0.5

export function usePlayerGestures(options: PlayerGestureOptions) {
  const feedback = ref<GestureFeedback>({
    kind: 'none',
    value: 0,
    label: '',
    visible: false,
  })
  const seekFlash = ref<SeekFlash>(null)

  /** 双击快进/快退的居中动画提示 */
  const doubleTapHint = ref<DoubleTapHint>({
    visible: false,
    label: '',
    side: 'right',
    key: 0,
  })

  let startX = 0
  let startY = 0
  let startVolume = 1
  let startBrightness = 1
  let zone: 'left' | 'right' = 'right'
  let mode: 'none' | 'horizontal' | 'vertical' = 'none'
  let moved = false
  let lastTapAt = 0
  let lastTapX = 0
  let singleTapTimer: ReturnType<typeof setTimeout> | null = null
  let feedbackTimer: ReturnType<typeof setTimeout> | null = null
  let flashTimer: ReturnType<typeof setTimeout> | null = null
  let hintTimer: ReturnType<typeof setTimeout> | null = null
  let pendingSeek = 0
  let hintKeyCounter = 0

  // Mouse click decoupling
  let lastMouseClickAt = 0
  let lastMouseClickX = 0
  let mouseClickTimer: ReturnType<typeof setTimeout> | null = null

  function clearFeedback(): void {
    feedback.value = { kind: 'none', value: 0, label: '', visible: false }
  }

  function showFeedback(
    kind: GestureKind,
    value: number,
    label: string,
    autoHide = true,
  ): void {
    feedback.value = { kind, value, label, visible: true }
    if (feedbackTimer) clearTimeout(feedbackTimer)
    if (autoHide) {
      feedbackTimer = setTimeout(clearFeedback, 900)
    }
  }

  function flashSeek(direction: Exclude<SeekFlash, null>): void {
    seekFlash.value = direction
    if (flashTimer) clearTimeout(flashTimer)
    flashTimer = setTimeout(() => {
      seekFlash.value = null
    }, 520)
  }

  /** 显示居中的 ±10s 动画提示 */
  function showDoubleTapHint(side: 'left' | 'right'): void {
    hintKeyCounter += 1
    doubleTapHint.value = {
      visible: true,
      label: side === 'right' ? `+${SEEK_STEP}s` : `-${SEEK_STEP}s`,
      side,
      key: hintKeyCounter,
    }
    if (hintTimer) clearTimeout(hintTimer)
    hintTimer = setTimeout(() => {
      doubleTapHint.value = { ...doubleTapHint.value, visible: false }
    }, 800)
  }

  function getZone(clientX: number): 'left' | 'right' {
    const el = options.video()
    if (!el) return 'right'
    const rect = el.getBoundingClientRect()
    if (!rect.width) return 'right'
    return clientX < rect.left + rect.width / 2 ? 'left' : 'right'
  }

  function handleDoubleTap(clientX: number): void {
    const tapZone = getZone(clientX)
    const delta = tapZone === 'left' ? -SEEK_STEP : SEEK_STEP
    options.seekBy(delta)
    showDoubleTapHint(tapZone)
    flashSeek(delta > 0 ? 'forward' : 'back')
  }

  function onTouchStart(event: TouchEvent): void {
    const touch = event.touches[0]
    if (!touch) return
    options.onActivity?.()
    startX = touch.clientX
    startY = touch.clientY
    zone = getZone(touch.clientX)
    mode = 'none'
    moved = false
    pendingSeek = 0
    startVolume = options.getVolume()
    startBrightness = options.getBrightness()
  }

  function onTouchMove(event: TouchEvent): void {
    const touch = event.touches[0]
    if (!touch) return
    const dx = touch.clientX - startX
    const dy = touch.clientY - startY

    if (mode === 'none') {
      if (Math.abs(dx) < MOVE_THRESHOLD && Math.abs(dy) < MOVE_THRESHOLD) return
      mode = Math.abs(dx) > Math.abs(dy) ? 'horizontal' : 'vertical'
      moved = true
      options.onActivity?.()
    }

    if (mode === 'horizontal') {
      pendingSeek = dx * SEEK_SECONDS_PER_PX
      const magnitude = Math.abs(pendingSeek)
      showFeedback(
        'seek',
        pendingSeek,
        pendingSeek >= 0
          ? `快进 ${formatClock(magnitude)}`
          : `后退 ${formatClock(magnitude)}`,
        false,
      )
      return
    }

    if (mode === 'vertical') {
      const el = options.video()
      const height = el ? el.getBoundingClientRect().height || 1 : 1
      const ratio = (startY - touch.clientY) / height

      if (zone === 'left') {
        const next = clamp(startBrightness + ratio, 0.1, 1)
        options.setBrightness(next)
        showFeedback(
          'brightness',
          next,
          `亮度 ${Math.round(next * 100)}%`,
          false,
        )
      } else {
        const next = clamp(startVolume + ratio, 0, 1)
        options.setVolume(next)
        showFeedback('volume', next, `音量 ${Math.round(next * 100)}%`, false)
      }
    }
  }

  function onTouchEnd(event: TouchEvent): void {
    if (mode === 'horizontal' && Math.abs(pendingSeek) >= 1) {
      options.seekBy(pendingSeek)
      flashSeek(pendingSeek >= 0 ? 'forward' : 'back')
    }
    const wasMoved = moved
    const wasMode = mode
    mode = 'none'
    moved = false
    pendingSeek = 0

    if (wasMoved || wasMode !== 'none') {
      if (feedbackTimer) clearTimeout(feedbackTimer)
      feedbackTimer = setTimeout(clearFeedback, 400)
      return
    }

    // 单击 / 双击判定（精准解耦，300ms 窗口）
    const touch = event.changedTouches[0]
    const clientX = touch ? touch.clientX : startX
    const now = Date.now()

    if (now - lastTapAt < DOUBLE_TAP_MS) {
      // 双击命中 —— 取消排队中的单击回调
      lastTapAt = 0
      if (singleTapTimer) {
        clearTimeout(singleTapTimer)
        singleTapTimer = null
      }
      handleDoubleTap(clientX)
      return
    }

    lastTapAt = now
    lastTapX = clientX
    if (singleTapTimer) clearTimeout(singleTapTimer)
    singleTapTimer = setTimeout(() => {
      singleTapTimer = null
      options.toggleControls()
    }, DOUBLE_TAP_MS)
  }

  /**
   * 鼠标 click 处理（桌面端）—— 同样做 300ms 单/双击解耦。
   * 由 CustomPlayer 的 @click 调用（已排除 ghost click）。
   */
  function handleClick(event: MouseEvent): void {
    const now = Date.now()
    const clientX = event.clientX

    if (now - lastMouseClickAt < DOUBLE_TAP_MS) {
      // 双击
      lastMouseClickAt = 0
      if (mouseClickTimer) {
        clearTimeout(mouseClickTimer)
        mouseClickTimer = null
      }
      handleDoubleTap(clientX)
      return
    }

    lastMouseClickAt = now
    lastMouseClickX = clientX
    if (mouseClickTimer) clearTimeout(mouseClickTimer)
    mouseClickTimer = setTimeout(() => {
      mouseClickTimer = null
      options.toggleControls()
    }, DOUBLE_TAP_MS)
  }

  onBeforeUnmount(() => {
    if (singleTapTimer) clearTimeout(singleTapTimer)
    if (feedbackTimer) clearTimeout(feedbackTimer)
    if (flashTimer) clearTimeout(flashTimer)
    if (hintTimer) clearTimeout(hintTimer)
    if (mouseClickTimer) clearTimeout(mouseClickTimer)
  })

  return {
    feedback: feedback as Ref<GestureFeedback>,
    seekFlash: seekFlash as Ref<SeekFlash>,
    doubleTapHint: doubleTapHint as Ref<DoubleTapHint>,
    onTouchStart,
    onTouchMove,
    onTouchEnd,
    handleClick,
    clearFeedback,
  }
}
