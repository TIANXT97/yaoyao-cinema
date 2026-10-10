<script setup lang="ts">
/**
 * TagPill —— 标签药丸。
 */
withDefaults(
  defineProps<{
    label: string
    count?: number
    active?: boolean
    interactive?: boolean
  }>(),
  { count: undefined, active: false, interactive: true },
)

const emit = defineEmits<{ (e: 'click'): void }>()
</script>

<template>
  <component
    :is="interactive ? 'button' : 'span'"
    :type="interactive ? 'button' : undefined"
    class="inline-flex shrink-0 items-center gap-1.5 rounded-full border px-3 py-1 text-xs transition-colors duration-150 ease-yy"
    :class="
      active
        ? 'border-accent/50 bg-accent/10 text-ink'
        : 'border-line bg-paper text-ink-soft hover:border-line hover:text-ink'
    "
    @click="interactive && emit('click')"
  >
    <span>{{ label }}</span>
    <span v-if="count !== undefined" class="text-[10px] text-ink-mute">{{ count }}</span>
  </component>
</template>
