<script setup lang="ts">
/**
 * FilterBar —— 排序 / 筛选工具栏（排序字段、升降序、快捷筛选、标签）。
 */
import { ArrowUpDown, Check, ChevronDown } from 'lucide-vue-next'
import { computed } from 'vue'

import TagPill from '@/components/media/TagPill.vue'
import type { Tag } from '@/types/actor'
import type { VideoFilters } from '@/types/video'
import { QUICK_FILTERS } from '@/types/video'
import { SORT_OPTIONS } from '@/utils/constants'

const props = withDefaults(
  defineProps<{
    modelValue: VideoFilters
    tags?: Tag[]
    activeQuick?: string
    showQuick?: boolean
    showTags?: boolean
  }>(),
  {
    tags: () => [],
    activeQuick: 'all',
    showQuick: true,
    showTags: false,
  },
)

const emit = defineEmits<{
  (e: 'update:modelValue', value: VideoFilters): void
  (e: 'change', value: VideoFilters): void
  (e: 'quick', key: string): void
  (e: 'tag', tagId?: string): void
}>()

function patch(partial: Partial<VideoFilters>): void {
  const next = { ...props.modelValue, ...partial }
  emit('update:modelValue', next)
  emit('change', next)
}

function toggleOrder(): void {
  patch({ order: props.modelValue.order === 'desc' ? 'asc' : 'desc' })
}

const visibleTags = computed(() => props.tags.slice(0, 16))
</script>

<template>
  <div class="flex flex-col gap-3">
    <div class="flex flex-wrap items-center gap-3">
      <!-- 排序字段 -->
      <div class="relative inline-flex items-center">
        <select
          class="yy-select cursor-pointer rounded-full border border-line bg-paper py-1.5 pl-3.5 pr-8 text-xs text-ink-soft transition-colors duration-150 ease-yy hover:text-ink focus:outline-none"
          :value="modelValue.sort"
          @change="patch({ sort: ($event.target as HTMLSelectElement).value as VideoFilters['sort'] })"
        >
          <option v-for="option in SORT_OPTIONS" :key="option.value" :value="option.value">
            {{ option.label }}
          </option>
        </select>
        <ChevronDown
          :size="13"
          :stroke-width="1.5"
          class="pointer-events-none absolute right-2.5 text-ink-faint"
        />
      </div>

      <!-- 升降序 -->
      <button
        type="button"
        class="inline-flex items-center gap-1.5 rounded-full border border-line bg-paper px-3 py-1.5 text-xs text-ink-soft transition-colors duration-150 ease-yy hover:text-ink"
        @click="toggleOrder"
      >
        <ArrowUpDown :size="13" :stroke-width="1.5" />
        {{ modelValue.order === 'desc' ? '降序' : '升序' }}
      </button>

      <!-- 快捷筛选 -->
      <div v-if="showQuick" class="flex items-center gap-2 overflow-x-auto no-scrollbar">
        <TagPill
          v-for="quick in QUICK_FILTERS"
          :key="quick.key"
          :label="quick.label"
          :active="activeQuick === quick.key"
          @click="emit('quick', quick.key)"
        />
      </div>

      <span class="ml-auto hidden shrink-0 text-[11px] tracking-bangou text-ink-mute sm:block">
        {{ modelValue.search ? `“${modelValue.search}”` : '' }}
      </span>
    </div>

    <!-- 标签筛选 -->
    <div
      v-if="showTags && visibleTags.length > 0"
      class="flex items-center gap-2 overflow-x-auto pb-1 no-scrollbar"
    >
      <button
        type="button"
        class="inline-flex shrink-0 items-center gap-1 rounded-full border px-3 py-1 text-xs transition-colors duration-150 ease-yy"
        :class="
          !modelValue.tagId
            ? 'border-accent/50 bg-accent/10 text-ink'
            : 'border-line bg-paper text-ink-soft hover:text-ink'
        "
        @click="emit('tag', undefined)"
      >
        <Check v-if="!modelValue.tagId" :size="12" :stroke-width="1.5" />
        全部标签
      </button>
      <TagPill
        v-for="tag in visibleTags"
        :key="tag.id"
        :label="tag.name"
        :count="tag.video_count"
        :active="modelValue.tagId === tag.id"
        @click="emit('tag', modelValue.tagId === tag.id ? undefined : tag.id)"
      />
    </div>
  </div>
</template>
