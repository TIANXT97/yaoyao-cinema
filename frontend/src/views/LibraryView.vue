<script setup lang="ts">
/**
 * LibraryView —— 全部影片（海报墙 + 排序 + 筛选 + 无限滚动）。
 */
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { listTags } from '@/api/tags'
import CategoryNav from '@/components/browse/CategoryNav.vue'
import FilterBar from '@/components/browse/FilterBar.vue'
import PageHeader from '@/components/layout/PageHeader.vue'
import VideoGrid from '@/components/media/VideoGrid.vue'
import { useVideoStore } from '@/stores/video'
import type { Tag } from '@/types/actor'
import { QUICK_FILTERS, type Video, type VideoFilters } from '@/types/video'

const router = useRouter()
const videoStore = useVideoStore()

const tags = ref<Tag[]>([])
const activeQuick = ref('all')
const activeCategory = ref('all')

async function onCategoryChange(cat: string): Promise<void> {
  activeCategory.value = cat
  videoStore.setFilters({ category: cat === 'all' ? undefined : cat })
  await reload()
}


function openVideo(video: Video): void {
  void router.push({ name: 'VideoDetail', params: { id: video.id } })
}

async function reload(): Promise<void> {
  await videoStore.fetchVideos(true)
}

async function onFilterChange(filters: VideoFilters): Promise<void> {
  videoStore.setFilters(filters)
  await reload()
}

async function onQuick(key: string): Promise<void> {
  activeQuick.value = key
  const quick = QUICK_FILTERS.find((item) => item.key === key)
  videoStore.setFilters({
    favorite: quick?.favorite,
    status: quick?.status,
    sort: quick?.sort ?? 'date_added',
    order: quick?.order ?? 'desc',
  })
  await reload()
}

async function onTag(tagId?: string): Promise<void> {
  videoStore.setFilters({ tagId })
  await reload()
}

onMounted(async () => {
  videoStore.resetFilters()
  activeQuick.value = 'all'
  await reload()
  try {
    tags.value = await listTags()
  } catch {
    tags.value = []
  }
})
</script>

<template>
  <div>
    <PageHeader
      title="片库"
      :subtitle="`共 ${videoStore.total} 部影片 · 全链路原画直出`"
      bordered
    />

    <section class="mx-auto max-w-[1600px] px-4 pt-6 sm:px-6 lg:px-8">
      <div class="mb-4">
        <CategoryNav v-model="activeCategory" @change="onCategoryChange" />
      </div>
      <FilterBar
        :model-value="videoStore.filters"
        :tags="tags"
        :active-quick="activeQuick"
        show-tags
        @change="onFilterChange"
        @quick="onQuick"
        @tag="onTag"
      />

      <div class="mt-6 pb-10">
        <VideoGrid
          :videos="videoStore.videos"
          :loading="videoStore.loading"
          :has-more="videoStore.hasMore"
          empty-title="没有符合条件的影片"
          empty-description="尝试调整筛选条件，或前往设置触发媒体库扫描。"
          @card-click="openVideo"
          @favorite="(video) => videoStore.toggleFavorite(video.id)"
          @load-more="videoStore.loadMore()"
        />
      </div>
    </section>
  </div>
</template>
