<script setup lang="ts">
/**
 * LazyImage —— 极简纯净图片组件,拒绝过度封装。
 *
 * 加载失败时自动重试(附加递增 query 绕过缓存),重试耗尽后展示占位图标。
 */
import { ImageOff } from 'lucide-vue-next'
import { computed, onBeforeUnmount, ref, watch } from 'vue'

const props = withDefaults(
  defineProps<{
    src?: string | null
    alt?: string
    aspect?: string
    eager?: boolean
    rounded?: string
    objectFit?: string
  }>(),
  {
    src: '',
    alt: '',
    aspect: '2 / 3',
    eager: false,
    rounded: '',
    objectFit: 'object-cover',
  },
)

const MAX_RETRIES = 2
const RETRY_DELAY_MS = 800

const attempt = ref(0)
const failed = ref(false)
let retryTimer: ReturnType<typeof setTimeout> | null = null

const currentSrc = computed(() => {
  const base = props.src ?? ''
  if (!base || attempt.value === 0) return base
  const sep = base.includes('?') ? '&' : '?'
  return `${base}${sep}retry=${attempt.value}`
})

function clearRetryTimer(): void {
  if (retryTimer) {
    clearTimeout(retryTimer)
    retryTimer = null
  }
}

function onError(): void {
  if (attempt.value >= MAX_RETRIES) {
    failed.value = true
    return
  }
  clearRetryTimer()
  retryTimer = setTimeout(() => {
    retryTimer = null
    attempt.value += 1
  }, RETRY_DELAY_MS)
}

watch(
  () => props.src,
  () => {
    clearRetryTimer()
    attempt.value = 0
    failed.value = false
  },
)

onBeforeUnmount(clearRetryTimer)
</script>

<template>
  <div
    class="relative overflow-hidden bg-paper-mute"
    :class="rounded"
    :style="{ aspectRatio: aspect }"
  >
    <img
      v-if="src && !failed"
      :key="attempt"
      :src="currentSrc"
      :alt="alt"
      :loading="eager ? 'eager' : 'lazy'"
      decoding="async"
      class="h-full w-full"
      :class="objectFit"
      @error="onError"
    />
    <div
      v-else
      class="absolute inset-0 flex items-center justify-center text-ink-mute"
    >
      <slot name="fallback">
        <ImageOff v-if="failed" :size="20" :stroke-width="1.5" />
      </slot>
    </div>
  </div>
</template>
