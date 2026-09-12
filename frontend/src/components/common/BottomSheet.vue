<script setup lang="ts">
/**
 * BottomSheet —— 通用底部上滑面板（iOS 风格 Sheet）。
 */
import { X } from 'lucide-vue-next'
import { onBeforeUnmount, watch } from 'vue'

const props = withDefaults(
  defineProps<{
    modelValue: boolean
    title?: string
  }>(),
  { title: '' },
)

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'close'): void
}>()

function close(): void {
  emit('update:modelValue', false)
  emit('close')
}

function onKeydown(event: KeyboardEvent): void {
  if (event.key === 'Escape') close()
}

watch(
  () => props.modelValue,
  (visible) => {
    if (typeof document === 'undefined') return
    document.body.style.overflow = visible ? 'hidden' : ''
    if (visible) window.addEventListener('keydown', onKeydown)
    else window.removeEventListener('keydown', onKeydown)
  },
)

onBeforeUnmount(() => {
  document.body.style.overflow = ''
  window.removeEventListener('keydown', onKeydown)
})
</script>

<template>
  <Teleport to="body">
    <Transition name="yy-fade">
      <div
        v-if="modelValue"
        class="fixed inset-0 z-50 bg-black/20 backdrop-blur-[2px]"
        @click="close"
      />
    </Transition>

    <Transition name="yy-sheet">
      <div
        v-if="modelValue"
        class="fixed inset-x-0 bottom-0 z-50 max-h-[88vh] overflow-y-auto rounded-t-2xl bg-paper pb-safe shadow-[0_-8px_40px_rgba(0,0,0,0.10)]"
        role="dialog"
        aria-modal="true"
      >
        <div
          class="sticky top-0 z-10 flex items-center justify-between border-b border-line bg-paper/95 px-5 py-4 backdrop-blur-xl"
        >
          <h2 class="text-sm font-medium text-ink">{{ title }}</h2>
          <button
            type="button"
            class="flex h-7 w-7 items-center justify-center rounded-full text-ink-faint transition-colors duration-150 ease-yy hover:text-ink"
            aria-label="关闭"
            @click="close"
          >
            <X :size="17" :stroke-width="1.5" />
          </button>
        </div>
        <div class="px-5 py-5">
          <slot />
        </div>
      </div>
    </Transition>
  </Teleport>
</template>
