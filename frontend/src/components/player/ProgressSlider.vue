<script setup lang="ts">
/**
 * ProgressSlider —— 播放进度滑块（自研视觉轨道 + 原生 range 交互）。
 */
import { computed, ref } from 'vue'

const props = withDefaults(
  defineProps<{
    currentTime: number
    duration: number
    buffered?: number
    disabled?: boolean
  }>(),
  { buffered: 0, disabled: false },
)

const emit = defineEmits<{
  (e: 'seek', time: number): void
  (e: 'seeking', active: boolean): void
}>()

const dragging = ref(false)
const dragValue = ref(0)

const max = computed(() => (props.duration > 0 ? props.duration : 0))
const value = computed(() => (dragging.value ? dragValue.value : props.currentTime))
const percent = computed(() =>
  max.value > 0 ? Math.min(100, Math.max(0, (value.value / max.value) * 100)) : 0,
)
const bufferedPercent = computed(() =>
  max.value > 0 ? Math.min(100, Math.max(0, (props.buffered / max.value) * 100)) : 0,
)

function beginDrag(): void {
  if (props.disabled) return
  dragging.value = true
  emit('seeking', true)
}

function onInput(event: Event): void {
  const next = Number((event.target as HTMLInputElement).value)
  if (!dragging.value) beginDrag()
  dragValue.value = next
  emit('seek', next)
}

function onEnd(event: Event): void {
  const next = Number((event.target as HTMLInputElement).value)
  dragValue.value = next
  emit('seek', next)
  dragging.value = false
  emit('seeking', false)
}
</script>

<template>
  <div class="group relative flex h-5 w-full items-center">
    <!-- 轨道 -->
    <div class="absolute inset-x-0 h-[3px] rounded-full bg-white/22" />
    <!-- 缓冲 -->
    <div
      class="absolute h-[3px] rounded-full bg-white/38"
      :style="{ width: `${bufferedPercent}%` }"
    />
    <!-- 已播放 -->
    <div
      class="absolute h-[3px] rounded-full bg-accent"
      :style="{ width: `${percent}%` }"
    />
    <!-- 拖拽点 -->
    <div
      class="absolute h-3 w-3 -translate-x-1/2 rounded-full bg-white shadow-[0_1px_4px_rgba(0,0,0,0.4)] transition-transform duration-150 ease-yy group-hover:scale-110"
      :style="{ left: `${percent}%` }"
    />
    <!-- 交互层 -->
    <input
      type="range"
      min="0"
      :max="max"
      step="0.1"
      :value="value"
      :disabled="disabled"
      class="absolute inset-0 h-full w-full cursor-pointer opacity-0 disabled:cursor-default"
      aria-label="播放进度"
      @input="onInput"
      @change="onEnd"
      @pointerdown="beginDrag"
    />
  </div>
</template>
