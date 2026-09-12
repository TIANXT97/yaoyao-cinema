<script setup lang="ts">
/**
 * LazyImage —— 图片懒加载 + 骨架屏 + 失败占位。
 */
import { ImageOff } from 'lucide-vue-next'
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'

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

const container = ref<HTMLElement | null>(null)
const visible = ref(false)
const loaded = ref(false)
const failed = ref(false)
let observer: IntersectionObserver | null = null

function cleanup(): void {
  observer?.disconnect()
  observer = null
}

function observe(): void {
  if (props.eager) {
    visible.value = true
    return
  }
  const el = container.value
  if (!el || typeof IntersectionObserver === 'undefined') {
    visible.value = true
    return
  }
  observer = new IntersectionObserver(
    (entries) => {
      if (entries.some((entry) => entry.isIntersecting)) {
        visible.value = true
        cleanup()
      }
    },
    { rootMargin: '480px 0px' },
  )
  observer.observe(el)
}

onMounted(observe)
onBeforeUnmount(cleanup)

watch(
  () => props.src,
  () => {
    loaded.value = false
    failed.value = false
    if (!visible.value) observe()
  },
)
</script>

<template>
  <div
    ref="container"
    class="relative overflow-hidden bg-paper-mute"
    :class="rounded"
    :style="{ aspectRatio: aspect }"
  >
    <div v-if="!loaded" class="yy-skeleton absolute inset-0" aria-hidden="true" />

    <img
      v-if="visible && src && !failed"
      :src="src"
      :alt="alt"
      loading="lazy"
      decoding="async"
      class="h-full w-full transition-opacity duration-500 ease-yy"
      :class="[objectFit, loaded ? 'opacity-100' : 'opacity-0']"
      @load="loaded = true"
      @error="failed = true"
    />

    <div
      v-if="visible && (failed || !src)"
      class="absolute inset-0 flex items-center justify-center text-ink-mute"
    >
      <slot name="fallback">
        <ImageOff :size="20" :stroke-width="1.5" />
      </slot>
    </div>
  </div>
</template>
