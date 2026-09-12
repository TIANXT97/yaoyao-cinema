/**
 * 播放器状态 Store（进度、音量、亮度、续播点、手势状态）。
 */

import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { getResumePoint, reportProgress as reportProgressApi } from '@/api/history'
import { PROGRESS_REPORT_INTERVAL } from '@/utils/constants'
import { clamp } from '@/utils/format'
import { deviceLabel } from '@/utils/platform'

export type GestureState = 'idle' | 'seeking' | 'volume' | 'brightness'

const VOLUME_KEY = 'yaoyao.player.volume'
const BRIGHTNESS_KEY = 'yaoyao.player.brightness'

function readStoredNumber(key: string, fallback: number): number {
  if (typeof window === 'undefined') return fallback
  const raw = window.localStorage.getItem(key)
  if (raw === null) return fallback
  const parsed = Number(raw)
  return Number.isFinite(parsed) ? parsed : fallback
}

export const usePlayerStore = defineStore('player', () => {
  // === 状态 ===
  const videoId = ref<string | null>(null)
  const title = ref('')
  const isPlaying = ref(false)
  const currentTime = ref(0) // 秒
  const duration = ref(0) // 秒
  const bufferedEnd = ref(0) // 秒
  const isFullscreen = ref(false)
  const showControls = ref(true)
  const resumePosition = ref(0) // 毫秒
  const gestureState = ref<GestureState>('idle')
  const playbackRate = ref(1)
  const volume = ref(clamp(readStoredNumber(VOLUME_KEY, 1), 0, 1))
  const brightness = ref(clamp(readStoredNumber(BRIGHTNESS_KEY, 1), 0.1, 1))
  const reporting = ref(false)

  let lastReportAt = 0
  let lastReportedPosition = -1

  // === 计算 ===
  const progress = computed(() =>
    duration.value > 0 ? clamp(currentTime.value / duration.value) : 0,
  )

  // === 动作 ===
  function setVideo(id: string, options: { title?: string; resumeMs?: number } = {}): void {
    videoId.value = id
    title.value = options.title ?? ''
    resumePosition.value = options.resumeMs ?? 0
    currentTime.value = 0
    duration.value = 0
    bufferedEnd.value = 0
    isPlaying.value = false
    lastReportAt = 0
    lastReportedPosition = -1
  }

  function setDuration(seconds: number): void {
    duration.value = Number.isFinite(seconds) ? Math.max(0, seconds) : 0
  }

  function setCurrentTime(seconds: number): void {
    currentTime.value = Number.isFinite(seconds) ? Math.max(0, seconds) : 0
  }

  function setBuffered(seconds: number): void {
    bufferedEnd.value = Number.isFinite(seconds) ? Math.max(0, seconds) : 0
  }

  function setPlaying(value: boolean): void {
    isPlaying.value = value
  }

  function setControlsVisible(value: boolean): void {
    showControls.value = value
  }

  function toggleControls(): void {
    showControls.value = !showControls.value
  }

  function setFullscreen(value: boolean): void {
    isFullscreen.value = value
  }

  function setGestureState(state: GestureState): void {
    gestureState.value = state
  }

  function setPlaybackRate(rate: number): void {
    playbackRate.value = rate
  }

  function setVolume(value: number): void {
    volume.value = clamp(value, 0, 1)
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(VOLUME_KEY, String(volume.value))
    }
  }

  function setBrightness(value: number): void {
    brightness.value = clamp(value, 0.1, 1)
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(BRIGHTNESS_KEY, String(brightness.value))
    }
  }

  /** 加载续播点（毫秒）。 */
  async function loadResumePoint(id: string): Promise<number> {
    try {
      const record = await getResumePoint(id)
      resumePosition.value = record.position ?? 0
      return resumePosition.value
    } catch {
      resumePosition.value = 0
      return 0
    }
  }

  /**
   * 上报播放进度。
   * @param force 忽略 10 秒节流（暂停 / 退出 / 手动 seek 时使用）
   */
  async function reportProgress(force = false): Promise<void> {
    if (!videoId.value || duration.value <= 0 || reporting.value) return

    const now = Date.now()
    if (!force && now - lastReportAt < PROGRESS_REPORT_INTERVAL) return

    const position = Math.round(currentTime.value * 1000)
    // 位置变化过小则跳过，避免无意义写入
    if (!force && Math.abs(position - lastReportedPosition) < 1000) return

    reporting.value = true
    try {
      await reportProgressApi({
        video_id: videoId.value,
        position,
        duration: Math.round(duration.value * 1000),
        device: deviceLabel(),
      })
      lastReportAt = now
      lastReportedPosition = position
    } catch {
      // 静默失败，不打断播放
    } finally {
      reporting.value = false
    }
  }

  function reset(): void {
    videoId.value = null
    title.value = ''
    isPlaying.value = false
    currentTime.value = 0
    duration.value = 0
    bufferedEnd.value = 0
    isFullscreen.value = false
    showControls.value = true
    resumePosition.value = 0
    gestureState.value = 'idle'
    playbackRate.value = 1
    lastReportAt = 0
    lastReportedPosition = -1
  }

  return {
    // state
    videoId,
    title,
    isPlaying,
    currentTime,
    duration,
    bufferedEnd,
    isFullscreen,
    showControls,
    resumePosition,
    gestureState,
    playbackRate,
    volume,
    brightness,
    // getters
    progress,
    // actions
    setVideo,
    setDuration,
    setCurrentTime,
    setBuffered,
    setPlaying,
    setControlsVisible,
    toggleControls,
    setFullscreen,
    setGestureState,
    setPlaybackRate,
    setVolume,
    setBrightness,
    loadResumePoint,
    reportProgress,
    reset,
  }
})
