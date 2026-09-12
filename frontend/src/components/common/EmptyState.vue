<script setup lang="ts">
/**
 * EmptyState —— 空状态：中心一行浅灰文字，不使用插画。
 */
withDefaults(
  defineProps<{
    title?: string
    description?: string
    compact?: boolean
  }>(),
  { title: '这里空空如也', description: '', compact: false },
)
</script>

<template>
  <div
    class="flex flex-col items-center justify-center text-center"
    :class="compact ? 'py-10' : 'py-24'"
  >
    <slot name="icon" />
    <p class="text-sm text-ink-faint">{{ title }}</p>
    <p v-if="description" class="mt-2 max-w-xs text-xs leading-relaxed text-ink-mute">
      {{ description }}
    </p>
    <div class="mt-4 empty:hidden">
      <slot />
    </div>
  </div>
</template>
