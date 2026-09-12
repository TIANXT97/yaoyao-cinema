<script setup lang="ts">
/**
 * InfiniteScroll —— 无限滚动触发器（哨兵元素 + IntersectionObserver）。
 */
import { ref } from 'vue'

import { useInfiniteScroll } from '@/composables/useInfiniteScroll'

const props = withDefaults(
  defineProps<{
    disabled?: boolean
    rootMargin?: string
  }>(),
  { disabled: false, rootMargin: '320px 0px' },
)

const emit = defineEmits<{ (e: 'load'): void }>()

const sentinel = ref<HTMLElement | null>(null)

useInfiniteScroll({
  target: sentinel,
  onLoad: () => emit('load'),
  disabled: () => props.disabled,
  rootMargin: props.rootMargin,
})
</script>

<template>
  <div ref="sentinel" class="h-px w-full" aria-hidden="true" />
</template>
