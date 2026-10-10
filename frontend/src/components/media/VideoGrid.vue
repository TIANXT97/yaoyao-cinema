<script setup lang="ts">
/**
 * VideoGrid —— 极致美学响应式海报网格。
 * 
 * 排版铁律：
 * - 手机竖屏（<640px）：精致 3 列紧凑卡片（单卡宽约 105px~115px），轻巧合手，绝不大膏药；
 * - 平板（640px~1024px）：4~5 列自适应；
 * - 桌面大宽屏（>=1024px）：原生 CSS 锁定 repeat(auto-fill, minmax(160px, 185px)) 黄金海报尺寸，
 *   哪怕只有 1 部或 3 部影片，卡片宽度死死锁在 180px 左右靠左整齐排列，绝对不会撑大横向爆开！
 */
import { computed } from 'vue'

import EmptyState from '@/components/common/EmptyState.vue'
import InfiniteScroll from '@/components/common/InfiniteScroll.vue'
import Skeleton from '@/components/common/Skeleton.vue'
import VideoCard from '@/components/media/VideoCard.vue'
import type { Video } from '@/types/video'

const props = withDefaults(
  defineProps<{
    videos: Video[]
    loading?: boolean
    progressMap?: Record<string, number>
    columns?: number
    emptyTitle?: string
    emptyDescription?: string
    infinite?: boolean
    hasMore?: boolean
    skeletonCount?: number
  }>(),
  {
    loading: false,
    progressMap: () => ({}),
    columns: 3,
    emptyTitle: '暂无影片',
    emptyDescription: '媒体库尚未收录内容，请前往设置触发扫描。',
    infinite: true,
    hasMore: false,
    skeletonCount: 12,
  },
)

const emit = defineEmits<{
  (e: 'card-click', video: Video): void
  (e: 'favorite', video: Video): void
  (e: 'load-more'): void
}>()

const showEmpty = computed(() => !props.loading && props.videos.length === 0)
</script>

<template>
  <div>
    <!-- 采用纯 CSS scoped 响应式网格，百分之百保证在 PC/平板/手机 均精准生效 -->
    <div class="yy-video-grid">
      <VideoCard
        v-for="video in videos"
        :key="video.id"
        :video="video"
        :progress="progressMap[video.id] ?? 0"
        @click="emit('card-click', video)"
        @favorite="emit('favorite', video)"
        @play="emit('card-click', video)"
      />

      <template v-if="loading && videos.length === 0">
        <div v-for="index in skeletonCount" :key="`skeleton-${index}`">
          <Skeleton class="aspect-[2/3] w-full" rounded="rounded-lg" />
          <Skeleton class="mt-1.5 h-2.5 w-3/4" rounded="rounded" />
          <Skeleton class="mt-1 h-2 w-1/2" rounded="rounded" />
        </div>
      </template>
    </div>

    <EmptyState
      v-if="showEmpty"
      :title="emptyTitle"
      :description="emptyDescription"
    />

    <InfiniteScroll
      v-if="infinite && videos.length > 0"
      :disabled="!hasMore || loading"
      @load="emit('load-more')"
    />

    <div
      v-if="loading && videos.length > 0"
      class="py-6 text-center text-xs text-ink-mute"
    >
      加载中…
    </div>

    <div
      v-else-if="!hasMore && videos.length > 0"
      class="py-6 text-center text-[11px] tracking-bangou text-ink-mute"
    >
      — 已经到底了 —
    </div>
  </div>
</template>

<style scoped>
.yy-video-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.625rem;
}

@media (min-width: 640px) {
  .yy-video-grid {
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 0.875rem;
  }
}

@media (min-width: 768px) {
  .yy-video-grid {
    grid-template-columns: repeat(5, minmax(0, 1fr));
    gap: 1rem;
  }
}

@media (min-width: 1024px) {
  .yy-video-grid {
    grid-template-columns: repeat(auto-fill, minmax(160px, 185px));
    gap: 1.25rem;
  }
}
</style>
