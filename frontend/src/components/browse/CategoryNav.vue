<script setup lang="ts">
/**
 * CategoryNav —— 纯白极简微浮雕二级分类导航胶囊条（全部 / 电影 / 国产剧 / 韩剧 / 欧美剧 / 动漫 / 纪录片 / 私房）
 */
import { onMounted, ref } from 'vue'
import { http } from '@/api/client'

withDefaults(
  defineProps<{
    modelValue?: string
  }>(),
  {
    modelValue: 'all',
  },
)

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void
  (e: 'change', value: string): void
}>()

interface CategoryItem {
  key: string
  label: string
}

const CATEGORIES: CategoryItem[] = [
  { key: 'all', label: '全部' },
  { key: 'movie', label: '电影' },
  { key: 'c_drama', label: '国产剧' },
  { key: 'k_drama', label: '韩剧' },
  { key: 'w_drama', label: '欧美剧' },
  { key: 'anime', label: '动漫' },
  { key: 'doc', label: '纪录片' },
  { key: 'local', label: '私房' },
]

const counts = ref<Record<string, number>>({})

async function fetchCounts() {
  try {
    const res = await http.get<Record<string, number>>('/videos/categories/summary')
    if (res && typeof res === 'object') {
      counts.value = res
    }
  } catch {
    // 忽略异常，降级显示
  }
}

function selectCategory(key: string) {
  emit('update:modelValue', key)
  emit('change', key)
}

onMounted(() => {
  void fetchCounts()
})
</script>

<template>
  <div class="no-scrollbar flex items-center gap-2 overflow-x-auto py-2">
    <button
      v-for="cat in CATEGORIES"
      :key="cat.key"
      type="button"
      class="group relative inline-flex shrink-0 items-center gap-1.5 rounded-full px-4 py-1.5 text-xs font-medium transition-all duration-200 ease-yy"
      :class="
        modelValue === cat.key
          ? 'bg-ink text-white shadow-soft ring-1 ring-ink'
          : 'bg-paper-mute text-ink-soft hover:bg-paper-mute/80 hover:text-ink'
      "
      @click="selectCategory(cat.key)"
    >
      <span>{{ cat.label }}</span>
      <span
        v-if="counts[cat.key] !== undefined && counts[cat.key] > 0"
        class="inline-flex items-center justify-center rounded-full px-1.5 py-0.2 text-[10px] font-mono leading-none"
        :class="
          modelValue === cat.key
            ? 'bg-white/20 text-white'
            : 'bg-black/5 text-ink-faint group-hover:text-ink-soft'
        "
      >
        {{ counts[cat.key] }}
      </span>
    </button>
  </div>
</template>
