<script setup lang="ts">
/**
 * Skeleton —— 海报骨架屏（浅灰脉冲，不用旋转菊花）。
 */
withDefaults(
  defineProps<{
    rounded?: string
  }>(),
  { rounded: 'rounded-md' },
)
</script>

<template>
  <div class="yy-skeleton" :class="rounded" aria-hidden="true" />
</template>
