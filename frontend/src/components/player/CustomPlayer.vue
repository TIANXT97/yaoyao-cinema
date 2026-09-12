<script setup lang="ts">
/**
 * CustomPlayer —— 自研 HTML5 原画手势播放器。
 *
 * 特性：
 * - HTTP 206 流直解（`/api/stream/{id}`）；
 * - 双击左/右快退/快进 10s；
 * - 垂直滑动（左亮度 / 右音量）、水平滑动快进快退；
 * - 单击切换控件，控件 4s 自动隐藏（拖动进度条时绝不隐藏）；
 * - 续播定位 + 每 10s 自动进度上报（暂停 / 离开强制上报）。
 */
import { computed, onBeforeUnmount, onMounted, provide, ref, watch } from 'vue'

import { streamUrl } from '@/api/client'
import GestureOverlay from '@/components/player/GestureOverlay.vue'
import PlayerControls from '@/components/player/PlayerControls.vue'
import { usePlayerGestures } from '@/composables/usePlayerGestures'
import { usePlayerStore } from '@/stores/player'
import { CONTROLS_HIDE_DELAY, PLAYBACK_RATES } from '@/utils/constants'
import { clamp } from '@/utils/format'
import { isIOS, isStandalonePWA } from '@/utils/platform'

const props = withDefaults(
  defineProps<{
    videoId: string
    title?: string
    poster?: string | null
    autoplay?: boolean
    /** 续播位置（毫秒）。 */
    resumeMs?: number
  }>(),
  { title: '', poster: null, autoplay: true, resumeMs: 0 },
)

const emit = defineEmits<{
  (e: 'back'): void
  (e: 'ended'): void
  (e: 'error', message: string): void
}>()

const store = usePlayerStore()

const container = ref<HTMLElement | null>(null)

const canAirplay = ref(true)

/** AirPlay 降级提示：PWA 模式下弹出原生全屏时的引导文字 */
const airplayHint = ref('')
let airplayHintTimer: ReturnType<typeof setTimeout> | null = null

function showAirplayHint(msg: string): void {
  airplayHint.value = msg
  if (airplayHintTimer) clearTimeout(airplayHintTimer)
  airplayHintTimer = setTimeout(() => {
    airplayHint.value = ''
  }, 4000)
}

function checkAirplay() {
  // 默认常驻显示投屏图标，绝不因为异步事件丢失而隐藏
  canAirplay.value = true
}

/**
 * triggerAirplay —— 唤起 AirPlay 投屏菜单。
 *
 * ★ iOS WebKit 铁律：webkitShowPlaybackTargetPicker() 必须在用户物理
 *   点击事件的「同步调用栈」中触发。因此此函数通过 provide/inject 直接
 *   注入 PlayerControls，由按钮 @click 同步调用，绝不经过 Vue emit 异步链。
 *
 * PWA Standalone 降级：
 *   iOS PWA 脱壳模式下 WebKit 可能拒绝弹出 Picker。
 *   此时降级到 webkitEnterFullscreen() —— iOS 原生全屏播放器顶栏自带
 *   系统级 AirPlay 投屏图标，无任何限制。
 */
function triggerAirplay(): void {
  const el = videoEl.value as HTMLVideoElement & {
    webkitShowPlaybackTargetPicker?: () => void
    webkitEnterFullscreen?: () => void
    remote?: { prompt: () => Promise<void> }
  }
  if (!el) return

  // 1️⃣ iOS PWA 独立模式：WebKit 经常拒绝 picker，直接走原生全屏降级
  if (isIOS() && isStandalonePWA()) {
    if (typeof el.webkitEnterFullscreen === 'function') {
      el.webkitEnterFullscreen()
      showAirplayHint('已进入原生播放器，请点击顶栏 AirPlay 图标投屏')
      return
    }
  }

  // 2️⃣ 优先尝试 WebKit 原生 Picker（Safari / 非 PWA iOS）
  if (typeof el.webkitShowPlaybackTargetPicker === 'function') {
    try {
      el.webkitShowPlaybackTargetPicker()
      return
    } catch {
      // 某些情况下可能抛异常，继续降级
    }
  }

  // 3️⃣ Remote Playback API（Chrome / Edge 等）
  if (el.remote && typeof el.remote.prompt === 'function') {
    el.remote.prompt().catch(() => {
      // 用户取消或不支持，静默忽略
    })
    return
  }

  // 4️⃣ 最终降级：iOS 原生全屏（系统播放器自带 AirPlay 图标）
  if (typeof el.webkitEnterFullscreen === 'function') {
    el.webkitEnterFullscreen()
    showAirplayHint('已进入原生播放器，请点击顶栏 AirPlay 图标投屏')
  }
}

// ★ 通过 provide 将 triggerAirplay 直接注入子组件，保持同步调用栈
provide('triggerAirplay', triggerAirplay)

const videoEl = ref<HTMLVideoElement | null>(null)

const scrubbing = ref(false)
const waiting = ref(false)
const failed = ref(false)
let resumeApplied = false
let lastTouchAt = 0
let hideTimer: ReturnType<typeof setTimeout> | null = null

const src = computed(() => streamUrl(props.videoId))
const videoStyle = computed(() => ({
  filter: `brightness(${store.brightness})`,
}))

// ---------------------------------------------------------------------------
// 手势
// ---------------------------------------------------------------------------
const {
  feedback,
  seekFlash,
  doubleTapHint,
  onTouchStart,
  onTouchMove,
  onTouchEnd,
  handleClick,
} = usePlayerGestures({
  video: () => videoEl.value,
  seekBy: (delta) => seekBy(delta),
  setVolume: (value) => applyVolume(value),
  setBrightness: (value) => store.setBrightness(value),
  getVolume: () => store.volume,
  getBrightness: () => store.brightness,
  toggleControls: () => store.toggleControls(),
  onActivity: () => activity(),
})

// ---------------------------------------------------------------------------
// 控件自动隐藏
// ---------------------------------------------------------------------------
function clearHideTimer(): void {
  if (hideTimer) {
    clearTimeout(hideTimer)
    hideTimer = null
  }
}

function scheduleHide(): void {
  clearHideTimer()
  // 正在拖动进度条或已暂停时，绝不自动隐藏
  if (!store.isPlaying || scrubbing.value) return
  hideTimer = setTimeout(() => store.setControlsVisible(false), CONTROLS_HIDE_DELAY)
}

function activity(): void {
  store.setControlsVisible(true)
  scheduleHide()
}

watch(
  () => store.showControls,
  (visible) => {
    if (visible) scheduleHide()
    else clearHideTimer()
  },
)

// ---------------------------------------------------------------------------
// 播放控制
// ---------------------------------------------------------------------------
async function play(): Promise<void> {
  const el = videoEl.value
  if (!el) return
  try {
    await el.play()
  } catch {
    // 浏览器自动播放策略拦截：保持暂停，等待用户操作
    store.setPlaying(false)
  }
}

function togglePlay(): void {
  const el = videoEl.value
  if (!el) return
  if (el.paused) void play()
  else el.pause()
  activity()
}

function seekTo(seconds: number): void {
  const el = videoEl.value
  if (!el || !Number.isFinite(el.duration)) return
  const target = clamp(seconds, 0, el.duration)
  el.currentTime = target
  store.setCurrentTime(target)
  activity()
}

function seekBy(delta: number): void {
  const el = videoEl.value
  if (!el) return
  seekTo(el.currentTime + delta)
}

function applyVolume(value: number): void {
  const next = clamp(value, 0, 1)
  store.setVolume(next)
  const el = videoEl.value
  if (el) {
    el.volume = next
    el.muted = next <= 0.001
  }
}

function cycleSpeed(): void {
  const rates = PLAYBACK_RATES
  const index = rates.indexOf(store.playbackRate as (typeof rates)[number])
  const next = rates[(index + 1) % rates.length] ?? 1
  store.setPlaybackRate(next)
  const el = videoEl.value
  if (el) el.playbackRate = next
  activity()
}

// ---------------------------------------------------------------------------
// 全屏
// ---------------------------------------------------------------------------
async function toggleFullscreen(): Promise<void> {
  const el = videoEl.value
  const box = container.value
  if (!box) return

  const iosVideo = el as
    | (HTMLVideoElement & {
        webkitEnterFullscreen?: () => void
        webkitDisplayingFullscreen?: boolean
      })
    | null

  try {
    if (!document.fullscreenElement) {
      if (box.requestFullscreen) await box.requestFullscreen()
      else if (iosVideo?.webkitDisplayingFullscreen === false)
        iosVideo?.webkitEnterFullscreen?.()
    } else {
      await document.exitFullscreen()
    }
  } catch {
    // iOS Safari 仅支持 video 元素原生全屏
    iosVideo?.webkitEnterFullscreen?.()
  }
}

function onFullscreenChange(): void {
  store.setFullscreen(Boolean(document.fullscreenElement))
}

// ---------------------------------------------------------------------------
// 视频事件
// ---------------------------------------------------------------------------
function onLoadedMetadata(): void {
  const el = videoEl.value
  if (!el) return
  store.setDuration(el.duration)
  el.volume = store.volume
  el.muted = store.volume <= 0.001
  el.playbackRate = store.playbackRate

  if (!resumeApplied) {
    resumeApplied = true
    const target = props.resumeMs / 1000
    if (target > 0 && target < el.duration - 3) {
      el.currentTime = target
      store.setCurrentTime(target)
    }
  }

  if (props.autoplay) void play()
}

function onTimeUpdate(): void {
  const el = videoEl.value
  if (!el) return
  if (!scrubbing.value) store.setCurrentTime(el.currentTime)
  void store.reportProgress()
}

function onProgress(): void {
  const el = videoEl.value
  if (!el) return
  const ranges = el.buffered
  store.setBuffered(ranges.length ? ranges.end(ranges.length - 1) : 0)
}

function onPlay(): void {
  store.setPlaying(true)
  scheduleHide()
}

function onPause(): void {
  store.setPlaying(false)
  store.setControlsVisible(true)
  clearHideTimer()
  void store.reportProgress(true)
}

function onEnded(): void {
  store.setPlaying(false)
  store.setControlsVisible(true)
  void store.reportProgress(true)
  emit('ended')
}

function onSeekingState(active: boolean): void {
  scrubbing.value = active
  if (active) {
    // 正在拖动进度条：取消隐藏定时器，保持控制栏可见
    clearHideTimer()
    store.setControlsVisible(true)
  } else {
    // 拖动结束：重新开始 4s 倒计时
    scheduleHide()
  }
}

function onError(): void {
  failed.value = true
  emit('error', '视频加载失败，请确认文件存在且格式受支持。')
}

// ---------------------------------------------------------------------------
// 手势表面事件（兼容鼠标点击）
// ---------------------------------------------------------------------------
function handleTouchStart(event: TouchEvent): void {
  lastTouchAt = Date.now()
  onTouchStart(event)
}

function handleSurfaceClick(event: MouseEvent): void {
  // 刚触摸结束后的 ghost click 忽略
  if (Date.now() - lastTouchAt < 800) return
  handleClick(event)
}

// ---------------------------------------------------------------------------
// 生命周期
// ---------------------------------------------------------------------------
onMounted(() => {
  checkAirplay()

  document.addEventListener('fullscreenchange', onFullscreenChange)
  const el = videoEl.value
  if (el) {
    el.volume = store.volume
    el.muted = store.volume <= 0.001
  }
  scheduleHide()
})

onBeforeUnmount(() => {
  clearHideTimer()
  if (airplayHintTimer) clearTimeout(airplayHintTimer)
  document.removeEventListener('fullscreenchange', onFullscreenChange)
  videoEl.value?.pause()
  void store.reportProgress(true)
})

defineExpose({ play, togglePlay, seekTo })
</script>

<template>
  <div
    ref="container"
    class="relative h-full w-full overflow-hidden bg-player"
  >
    <video
      ref="videoEl"
      :src="src"
      :poster="poster ?? undefined"
      class="h-full w-full object-contain transition-[filter] duration-150 ease-yy"
      :style="videoStyle"
      playsinline
      webkit-playsinline
      x-webkit-airplay="allow"
      preload="metadata"
      @loadedmetadata="onLoadedMetadata"
      @timeupdate="onTimeUpdate"
      @progress="onProgress"
      @play="onPlay"
      @pause="onPause"
      @ended="onEnded"
      @waiting="waiting = true"
      @playing="waiting = false"
      @canplay="waiting = false"
      @error="onError"
    />

    <!-- 加载指示（极简脉冲，不用旋转菊花） -->
    <div
      v-if="waiting && !failed"
      class="pointer-events-none absolute inset-0 z-[15] flex items-center justify-center"
    >
      <span class="h-8 w-8 animate-pulse rounded-full bg-white/15" />
    </div>

    <!-- 失败提示 -->
    <div
      v-if="failed"
      class="pointer-events-none absolute inset-0 z-[15] flex items-center justify-center px-6 text-center"
    >
      <p class="text-sm text-white/70">视频加载失败，请稍后重试。</p>
    </div>

    <!-- 手势识别覆盖层 -->
    <div
      class="absolute inset-0 z-10 touch-none"
      @touchstart="handleTouchStart"
      @touchmove.prevent="onTouchMove"
      @touchend="onTouchEnd"
      @click="handleSurfaceClick"
    />

    <!-- 手势反馈 -->
    <GestureOverlay
      :feedback="feedback"
      :seek-flash="seekFlash"
      :double-tap-hint="doubleTapHint"
    />

    <!-- AirPlay 降级提示 Toast -->
    <Transition name="yy-fade">
      <div
        v-if="airplayHint"
        class="absolute left-1/2 top-[15%] z-40 -translate-x-1/2 rounded-xl bg-black/70 px-5 py-3 text-center text-sm text-white shadow-2xl backdrop-blur-md"
      >
        {{ airplayHint }}
      </div>
    </Transition>

    <!-- 控件 -->
    <PlayerControls
      :has-airplay="canAirplay"
      :visible="store.showControls"
      :playing="store.isPlaying"
      :current-time="store.currentTime"
      :duration="store.duration"
      :buffered="store.bufferedEnd"
      :speed="store.playbackRate"
      :fullscreen="store.isFullscreen"
      :title="title"
      @toggle="togglePlay"
      @seek="seekTo"
      @seeking="onSeekingState"
      @back="emit('back')"
      @speed="cycleSpeed"
      @fullscreen="toggleFullscreen"
    />
  </div>
</template>
