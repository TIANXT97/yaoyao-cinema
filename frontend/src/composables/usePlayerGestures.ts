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

const DOUBLE_TAP_MS = 280
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

  let startX = 0
  let startY = 0
  let startVolume = 1
  let startBrightness = 1
  let zone: 'left' | 'right' = 'right'
  let mode: 'none' | 'horizontal' | 'vertical' = 'none'
  let moved = false
  let lastTapAt = 0
  let singleTapTimer: ReturnType<typeof setTimeout> | null = null
  let feedbackTimer: ReturnType<typeof setTimeout> | null = null
  let flashTimer: ReturnType<typeof setTimeout> | null = null
  let pendingSeek = 0

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
    showFeedback(
      'seek',
      delta,
      delta > 0 ? `前进 ${SEEK_STEP} 秒` : `后退 ${SEEK_STEP} 秒`,
    )
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

    // 单击 / 双击判定
    const touch = event.changedTouches[0]
    const clientX = touch ? touch.clientX : startX
    const now = Date.now()

    if (now - lastTapAt < DOUBLE_TAP_MS) {
      lastTapAt = 0
      if (singleTapTimer) {
        clearTimeout(singleTapTimer)
        singleTapTimer = null
      }
      handleDoubleTap(clientX)
      return
    }

    lastTapAt = now
    if (singleTapTimer) clearTimeout(singleTapTimer)
    singleTapTimer = setTimeout(() => {
      singleTapTimer = null
      options.toggleControls()
    }, DOUBLE_TAP_MS)
  }

  onBeforeUnmount(() => {
    if (singleTapTimer) clearTimeout(singleTapTimer)
    if (feedbackTimer) clearTimeout(feedbackTimer)
    if (flashTimer) clearTimeout(flashTimer)
  })

  return {
    feedback: feedback as Ref<GestureFeedback>,
    seekFlash: seekFlash as Ref<SeekFlash>,
    onTouchStart,
    onTouchMove,
    onTouchEnd,
    clearFeedback,
  }
}
