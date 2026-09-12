<script setup lang="ts">
/**
 * PageHeader —— 页面顶部标题栏（返回 / 标题 / 副标题 / 右侧插槽）。
 */
import { ArrowLeft } from 'lucide-vue-next'
import { useRouter } from 'vue-router'

const props = withDefaults(
  defineProps<{
    title: string
    subtitle?: string
    back?: boolean
    sticky?: boolean
    bordered?: boolean
  }>(),
  { subtitle: '', back: false, sticky: true, bordered: false },
)

const router = useRouter()

function goBack(): void {
  if (window.history.length > 1) router.back()
  else void router.push({ name: 'Home' })
}
</script>

<template>
  <div
    class="z-30 bg-paper/90 backdrop-blur-xl"
    :class="[sticky ? 'sticky top-14' : '', bordered ? 'border-b border-line' : '']"
  >
    <div class="mx-auto flex max-w-[1600px] items-end gap-4 px-4 pb-5 pt-8 sm:px-6 lg:px-8">
      <button
        v-if="back"
        type="button"
        class="mb-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-ink-soft transition-colors duration-150 ease-yy hover:bg-paper-mute hover:text-ink"
        aria-label="返回"
        @click="goBack"
      >
        <ArrowLeft :size="18" :stroke-width="1.5" />
      </button>

      <div class="min-w-0 flex-1">
        <h1 class="font-serif text-2xl leading-tight text-ink">{{ title }}</h1>
        <p v-if="subtitle" class="mt-1.5 truncate text-sm text-ink-faint">
          {{ subtitle }}
        </p>
      </div>

      <div class="mb-0.5 flex shrink-0 items-center gap-2">
        <slot name="actions" />
      </div>
    </div>
  </div>
</template>
