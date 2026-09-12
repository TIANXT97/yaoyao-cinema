<script setup lang="ts">
/**
 * LazyImage —— 极简纯净图片组件，拒绝过度封装。
 */
withDefaults(
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
</script>

<template>
  <div
    class="relative overflow-hidden bg-paper-mute"
    :class="rounded"
    :style="{ aspectRatio: aspect }"
  >
    <img
      v-if="src"
      :src="src"
      :alt="alt"
      :loading="eager ? 'eager' : 'lazy'"
      decoding="async"
      class="h-full w-full"
      :class="objectFit"
    />
    <div
      v-else
      class="absolute inset-0 flex items-center justify-center text-ink-mute"
    >
      <slot name="fallback" />
    </div>
  </div>
</template>
