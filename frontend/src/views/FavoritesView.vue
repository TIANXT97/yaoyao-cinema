<script setup lang="ts">
/**
 * FavoritesView —— 主人私房收藏。
 */
import { Heart } from 'lucide-vue-next'
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import PageHeader from '@/components/layout/PageHeader.vue'
import VideoGrid from '@/components/media/VideoGrid.vue'
import { useVideoStore } from '@/stores/video'
import type { Video } from '@/types/video'

const router = useRouter()
const videoStore = useVideoStore()

const workingId = ref<string | null>(null)

function openVideo(video: Video): void {
  void router.push({ name: 'VideoDetail', params: { id: video.id } })
}

async function unfavorite(video: Video): Promise<void> {
  if (workingId.value) return
  workingId.value = video.id
  try {
    await videoStore.toggleFavorite(video.id)
    // 收藏页移除已取消收藏项
    videoStore.videos = videoStore.videos.filter((item) => item.id !== video.id)
    videoStore.pagination.total = Math.max(0, videoStore.pagination.total - 1)
  } finally {
    workingId.value = null
  }
}

onMounted(async () => {
  videoStore.resetFilters()
  videoStore.setFilters({ favorite: true, sort: 'date_added', order: 'desc' })
  await videoStore.fetchVideos(true)
})
</script>

<template>
  <div>
    <PageHeader
      title="私房收藏"
      :subtitle="`共 ${videoStore.total} 部珍藏`"
      bordered
    />

    <section class="mx-auto max-w-[1600px] px-4 pt-8 pb-10 sm:px-6 lg:px-8">
      <VideoGrid
        :videos="videoStore.videos"
        :loading="videoStore.loading"
        :has-more="videoStore.hasMore"
        empty-title="收藏夹还是空的"
        empty-description="在影片详情页点击心形，即可将心仪之作收进私房。"
        @card-click="openVideo"
        @favorite="unfavorite"
        @load-more="videoStore.loadMore()"
      />

      <div
        v-if="videoStore.videos.length > 0"
        class="mt-2 flex items-center justify-center gap-1.5 text-[11px] tracking-bangou text-ink-mute"
      >
        <Heart :size="11" :stroke-width="1.5" class="text-accent" />
        已为你妥善保管
      </div>
    </section>
  </div>
</template>
