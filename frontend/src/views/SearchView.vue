<script setup lang="ts">
/**
 * SearchView —— 即时搜索（防抖 300ms，无限滚动）。
 */
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { listVideos } from '@/api/videos'
import SearchInput from '@/components/browse/SearchInput.vue'
import PageHeader from '@/components/layout/PageHeader.vue'
import VideoGrid from '@/components/media/VideoGrid.vue'
import { useDebounceFn } from '@/composables/useDebounce'
import type { Video } from '@/types/video'

const route = useRoute()
const router = useRouter()

const keyword = ref(String(route.query.q ?? ''))
const results = ref<Video[]>([])
const loading = ref(false)
const page = ref(0)
const totalPages = ref(0)
const total = ref(0)
const perPage = 30

const hasMore = computed(() => page.value > 0 && page.value < totalPages.value)

async function search(reset = true): Promise<void> {
  const query = keyword.value.trim()
  if (!query) {
    results.value = []
    total.value = 0
    page.value = 0
    totalPages.value = 0
    return
  }
  if (loading.value) return

  const nextPage = reset ? 1 : page.value + 1
  loading.value = true
  try {
    const data = await listVideos({
      search: query,
      page: nextPage,
      per_page: perPage,
      sort: 'date_added',
      order: 'desc',
    })
    results.value = reset ? data.items : [...results.value, ...data.items]
    page.value = data.pagination.page
    totalPages.value = data.pagination.total_pages
    total.value = data.pagination.total
  } finally {
    loading.value = false
  }
}

function commitSearch(): void {
  const query = keyword.value.trim()
  void router.replace({ name: 'Search', query: query ? { q: query } : {} })
  void search(true)
}

const debouncedSearch = useDebounceFn(commitSearch, 300)

watch(keyword, () => debouncedSearch())

function loadMore(): void {
  if (hasMore.value) void search(false)
}

function openVideo(video: Video): void {
  void router.push({ name: 'VideoDetail', params: { id: video.id } })
}

onMounted(() => {
  if (keyword.value) void search(true)
})
</script>

<template>
  <div>
    <PageHeader title="搜索" subtitle="番号 · 标题 · 演员" bordered />

    <section class="mx-auto max-w-[1600px] px-4 pt-6 pb-12 sm:px-6 lg:px-8">
      <SearchInput v-model="keyword" autofocus @submit="commitSearch" />

      <div class="mt-4 flex items-center justify-between text-[11px] text-ink-faint">
        <span v-if="keyword.trim()">共找到 {{ total }} 条结果</span>
        <span v-else>输入关键词，即刻检索私家馆藏</span>
      </div>

      <div v-if="keyword.trim()" class="mt-6">
        <VideoGrid
          :videos="results"
          :loading="loading"
          :has-more="hasMore"
          empty-title="没有找到相关影片"
          empty-description="换个番号或关键词试试，或确认媒体库已完成刮削。"
          @card-click="openVideo"
          @load-more="loadMore"
        />
      </div>

      <div
        v-else
        class="flex flex-col items-center justify-center py-24 text-center"
      >
        <p class="font-serif text-lg text-ink-mute">搜索你的私家馆藏</p>
        <p class="mt-2 text-xs text-ink-mute">
          支持番号、原始标题、中文标题与演员名
        </p>
      </div>
    </section>
  </div>
</template>
