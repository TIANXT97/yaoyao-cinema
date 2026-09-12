<script setup lang="ts">
/**
 * GestureOverlay —— 手势反馈 HUD（亮度 / 音量 / 快进 + 双击居中动画提示）。
 */
import { FastForward, Rewind, Sun, Volume2 } from 'lucide-vue-next'
import { computed } from 'vue'

import type {
  DoubleTapHint,
  GestureFeedback,
  SeekFlash,
} from '@/composables/usePlayerGestures'

const props = defineProps<{
  feedback: GestureFeedback
  seekFlash: SeekFlash
  doubleTapHint: DoubleTapHint
}>()

const percent = computed(() =>
  props.feedback.value <= 1 ? Math.max(0, Math.min(100, props.feedback.value * 100)) : 0,
)
</script>

<template>
  <div class="pointer-events-none absolute inset-0 z-20">
    <!-- 中心 HUD（滑动手势反馈：亮度 / 音量 / 水平滑动快进快退） -->
    <Transition name="yy-fade">
      <div
        v-if="feedback.visible"
        class="absolute left-1/2 top-1/2 min-w-[7rem] -translate-x-1/2 -translate-y-1/2 rounded-xl bg-black/55 px-5 py-3 text-center text-white backdrop-blur-md"
      >
        <div class="flex items-center justify-center gap-2">
          <Sun
            v-if="feedback.kind === 'brightness'"
            :size="17"
            :stroke-width="1.5"
          />
          <Volume2
            v-else-if="feedback.kind === 'volume'"
            :size="17"
            :stroke-width="1.5"
          />
          <FastForward
            v-else-if="feedback.kind === 'seek' && feedback.value > 0"
            :size="17"
            :stroke-width="1.5"
          />
          <Rewind v-else :size="17" :stroke-width="1.5" />
        </div>

        <p class="mt-1.5 whitespace-nowrap text-xs tracking-wide">
          {{ feedback.label }}
        </p>

        <div
          v-if="feedback.kind === 'volume' || feedback.kind === 'brightness'"
          class="mt-2 h-[3px] w-28 overflow-hidden rounded-full bg-white/25"
        >
          <div
            class="h-full rounded-full bg-white transition-[width] duration-100 ease-yy"
            :style="{ width: `${percent}%` }"
          />
        </div>
      </div>
    </Transition>

    <!-- 双击快进/快退：精致居中动画提示 -->
    <Transition name="dt-hint">
      <div
        v-if="doubleTapHint.visible"
        :key="doubleTapHint.key"
        class="absolute left-1/2 top-1/2 flex -translate-x-1/2 -translate-y-1/2 items-center gap-2.5 rounded-2xl bg-black/50 px-6 py-3.5 text-white shadow-lg backdrop-blur-md"
      >
        <Rewind
          v-if="doubleTapHint.side === 'left'"
          :size="22"
          :stroke-width="1.5"
          class="shrink-0"
        />
        <FastForward
          v-else
          :size="22"
          :stroke-width="1.5"
          class="shrink-0"
        />
        <span class="text-base font-semibold tracking-wide">
          {{ doubleTapHint.label }}
        </span>
      </div>
    </Transition>

    <!-- 双击快进/后退波纹（左右侧小圆） -->
    <Transition name="yy-fade">
      <div
        v-if="seekFlash"
        class="absolute top-1/2 flex h-16 w-16 -translate-y-1/2 items-center justify-center rounded-full bg-black/35 text-white backdrop-blur-sm"
        :class="seekFlash === 'back' ? 'left-[12%]' : 'right-[12%]'"
      >
        <Rewind
          v-if="seekFlash === 'back'"
          :size="22"
          :stroke-width="1.5"
        />
        <FastForward v-else :size="22" :stroke-width="1.5" />
      </div>
    </Transition>
  </div>
</template>

<style scoped>
/* 双击居中提示：弹入 + 淡出动画 */
.dt-hint-enter-active {
  animation: dt-pop-in 0.28s cubic-bezier(0.34, 1.56, 0.64, 1) forwards;
}
.dt-hint-leave-active {
  animation: dt-fade-out 0.38s ease-out forwards;
}

@keyframes dt-pop-in {
  0% {
    opacity: 0;
    transform: translate(-50%, -50%) scale(0.5);
  }
  100% {
    opacity: 1;
    transform: translate(-50%, -50%) scale(1);
  }
}

@keyframes dt-fade-out {
  0% {
    opacity: 1;
    transform: translate(-50%, -50%) scale(1);
  }
  100% {
    opacity: 0;
    transform: translate(-50%, -50%) scale(1.15);
  }
}
</style>
