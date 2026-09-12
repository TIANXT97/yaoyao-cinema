<script setup lang="ts">
/**
 * GestureOverlay —— 手势反馈 HUD（亮度 / 音量 / 双击快进）。
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
  <div class="pointer-events-none absolute inset-0 z-20 overflow-hidden">
    <!-- 中心 HUD（滑动调节亮度 / 音量） -->
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

    <!-- 双击快进/快退：纯净居中，锁定屏幕正中绝不漂移 -->
    <Transition name="dt-hint">
      <div
        v-if="doubleTapHint.visible"
        class="dt-center-box flex items-center gap-2.5 rounded-2xl bg-black/60 px-6 py-3.5 text-white shadow-2xl backdrop-blur-md"
      >
        <Rewind
          v-if="doubleTapHint.side === 'left'"
          :size="24"
          :stroke-width="1.75"
          class="shrink-0 text-white"
        />
        <FastForward
          v-else
          :size="24"
          :stroke-width="1.75"
          class="shrink-0 text-white"
        />
        <span class="text-base font-semibold tracking-wider text-white">
          {{ doubleTapHint.label }}
        </span>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.dt-center-box {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
}

/* 居中提示：优雅微缩放显隐，锁定位置绝对不偏移 */
.dt-hint-enter-active {
  transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
}
.dt-hint-leave-active {
  transition: all 0.25s ease-out;
}

.dt-hint-enter-from {
  opacity: 0;
  transform: translate(-50%, -50%) scale(0.85);
}
.dt-hint-enter-to {
  opacity: 1;
  transform: translate(-50%, -50%) scale(1);
}
.dt-hint-leave-from {
  opacity: 1;
  transform: translate(-50%, -50%) scale(1);
}
.dt-hint-leave-to {
  opacity: 0;
  transform: translate(-50%, -50%) scale(1.05);
}
</style>
