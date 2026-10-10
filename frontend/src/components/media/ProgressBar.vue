<script setup lang="ts">
/**
 * ProgressBar —— 观看进度条（卡片底部细彩条）。
 */
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    value?: number
    color?: string
    track?: string
    height?: string
  }>(),
  {
    value: 0,
    color: 'bg-accent',
    track: 'bg-black/15',
    height: 'h-[3px]',
  },
)

const width = computed(() => `${Math.min(100, Math.max(0, props.value * 100))}%`)
</script>

<template>
  <div class="w-full overflow-hidden rounded-full" :class="[track, height]">
    <div
      class="h-full rounded-full transition-[width] duration-300 ease-yy"
      :class="color"
      :style="{ width }"
    />
  </div>
</template>
