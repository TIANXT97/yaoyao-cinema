<script setup lang="ts">
/**
 * SearchInput —— 极简搜索输入框（带清除）。
 */
import { Search, X } from 'lucide-vue-next'
import { onMounted, ref } from 'vue'

const props = withDefaults(
  defineProps<{
    modelValue: string
    placeholder?: string
    autofocus?: boolean
  }>(),
  { placeholder: '搜索番号 / 标题 / 演员', autofocus: false },
)

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void
  (e: 'submit', value: string): void
  (e: 'clear'): void
}>()

const input = ref<HTMLInputElement | null>(null)

function onInput(event: Event): void {
  emit('update:modelValue', (event.target as HTMLInputElement).value)
}

function clear(): void {
  emit('update:modelValue', '')
  emit('clear')
  input.value?.focus()
}

onMounted(() => {
  if (props.autofocus) input.value?.focus()
})
</script>

<template>
  <form
    class="flex w-full items-center gap-2 rounded-full border border-line bg-paper-soft px-4 py-2 transition-colors duration-150 ease-yy focus-within:border-accent/60"
    @submit.prevent="emit('submit', modelValue)"
  >
    <Search :size="15" :stroke-width="1.5" class="shrink-0 text-ink-faint" />
    <input
      ref="input"
      :value="modelValue"
      type="search"
      :placeholder="placeholder"
      class="w-full bg-transparent text-sm text-ink placeholder:text-ink-mute focus:outline-none"
      @input="onInput"
    />
    <button
      v-if="modelValue"
      type="button"
      class="flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-ink-faint transition-colors duration-150 ease-yy hover:text-ink"
      aria-label="清除"
      @click="clear"
    >
      <X :size="14" :stroke-width="1.5" />
    </button>
  </form>
</template>
