<script setup lang="ts">
/**
 * PlayerControls —— 播放控件层（顶栏标题 + 底栏控制）。
 */
import {
  Airplay,
  ArrowLeft,
  Maximize,
  Minimize,
  Pause,
  Play,
  SkipBack,
  SkipForward,
} from 'lucide-vue-next'

import ProgressSlider from '@/components/player/ProgressSlider.vue'
import { SEEK_STEP } from '@/utils/constants'
import { formatClock } from '@/utils/format'

withDefaults(
  defineProps<{
    visible: boolean
    playing: boolean
    currentTime: number
    duration: number
    buffered?: number
    speed?: number
    fullscreen?: boolean
    title?: string
    hasAirplay?: boolean
  }>(),
  { buffered: 0, speed: 1, fullscreen: false, title: '', hasAirplay: false },
)

const emit = defineEmits<{
  (e: 'toggle'): void
  (e: 'seek', time: number): void
  (e: 'seeking', active: boolean): void
  (e: 'back'): void
  (e: 'speed'): void
  (e: 'fullscreen'): void
  (e: 'airplay'): void
}>()
</script>

<template>
  <Transition name="yy-fade">
    <div
      v-show="visible"
      class="pointer-events-none absolute inset-0 z-30 flex flex-col justify-between"
    >
      <!-- 顶栏 -->
      <div
        class="pointer-events-auto flex items-center gap-3 bg-gradient-to-b from-black/60 to-transparent px-3 pb-10 pt-safe sm:px-5"
      >
        <button
          type="button"
          class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-white/85 transition-colors duration-150 ease-yy hover:text-white"
          aria-label="返回"
          @click="emit('back')"
        >
          <ArrowLeft :size="19" :stroke-width="1.6" />
        </button>
        <h1 class="truncate text-sm font-normal text-white/90">{{ title }}</h1>
        <button
          v-if="hasAirplay"
          type="button"
          class="ml-auto flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-white/85 transition-colors duration-150 ease-yy hover:text-white"
          aria-label="无线投屏"
          @click="emit('airplay')"
        >
          <Airplay :size="19" :stroke-width="1.6" />
        </button>
      </div>

      <!-- 底栏 -->
      <div
        class="pointer-events-auto bg-gradient-to-t from-black/70 to-transparent px-3 pb-5 pt-12 sm:px-5"
      >
        <ProgressSlider
          :current-time="currentTime"
          :duration="duration"
          :buffered="buffered"
          @seek="emit('seek', $event)"
          @seeking="emit('seeking', $event)"
        />

        <div class="mt-3 flex items-center gap-3 text-white/85 sm:gap-4">
          <button
            type="button"
            class="flex h-9 w-9 items-center justify-center rounded-full transition-colors duration-150 ease-yy hover:text-white"
            aria-label="播放/暂停"
            @click="emit('toggle')"
          >
            <Play v-if="!playing" :size="22" :stroke-width="1.5" class="ml-0.5" />
            <Pause v-else :size="22" :stroke-width="1.5" />
          </button>

          <button
            type="button"
            class="flex items-center gap-0.5 transition-colors duration-150 ease-yy hover:text-white"
            aria-label="后退 10 秒"
            @click="emit('seek', currentTime - SEEK_STEP)"
          >
            <SkipBack :size="19" :stroke-width="1.5" />
            <span class="text-[10px]">10</span>
          </button>

          <button
            type="button"
            class="flex items-center gap-0.5 transition-colors duration-150 ease-yy hover:text-white"
            aria-label="前进 10 秒"
            @click="emit('seek', currentTime + SEEK_STEP)"
          >
            <SkipForward :size="19" :stroke-width="1.5" />
            <span class="text-[10px]">10</span>
          </button>

          <span class="ml-1 font-mono text-xs tracking-wide text-white/80">
            {{ formatClock(currentTime) }} / {{ formatClock(duration) }}
          </span>

          <div class="ml-auto flex items-center gap-1.5 sm:gap-3">
            <button
              type="button"
              class="rounded-full px-2 py-1 font-mono text-xs tracking-wide text-white/80 transition-colors duration-150 ease-yy hover:text-white"
              aria-label="播放速度"
              @click="emit('speed')"
            >
              {{ speed }}x
            </button>
            <button
              type="button"
              class="flex h-9 w-9 items-center justify-center rounded-full transition-colors duration-150 ease-yy hover:text-white"
              :aria-label="fullscreen ? '退出全屏' : '全屏'"
              @click="emit('fullscreen')"
            >
              <Minimize v-if="fullscreen" :size="18" :stroke-width="1.5" />
              <Maximize v-else :size="18" :stroke-width="1.5" />
            </button>
          </div>
        </div>
      </div>
    </div>
  </Transition>
</template>
