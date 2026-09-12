<script setup lang="ts">
/**
 * HomeView —— 主页：继续观看 + 快速筛选 + 最新入库海报墙。
 */
import { Play } from 'lucide-vue-next'
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { mediaUrl } from '@/api/client'
import LazyImage from '@/components/common/LazyImage.vue'
import ProgressBar from '@/components/media/ProgressBar.vue'
import TagPill from '@/components/media/TagPill.vue'
import VideoGrid from '@/components/media/VideoGrid.vue'
import { useNativePlayer } from '@/composables/useNativePlayer'
import { useHistoryStore } from '@/stores/history'
import { useVideoStore } from '@/stores/video'
import type { RecentRecord } from '@/types/history'
import { QUICK_FILTERS, type Video } from '@/types/video'
import { displayTitle, formatClock, formatRelativeTime } from '@/utils/format'

const router = useRouter()
const videoStore = useVideoStore()
const historyStore = useHistoryStore()
const { playVideo } = useNativePlayer()

const activeQuick = ref('all')

const continueList = computed(() => historyStore.recentVideos.slice(0, 12))
const progressMap = computed(() => {
  const map: Record<string, number> = {}
  for (const record of historyStore.recentVideos) {
    map[record.video_id] = record.progress
  }
  return map
})

function openVideo(video: Video): void {
  void router.push({ name: 'VideoDetail', params: { id: video.id } })
}

function resumePlay(record: RecentRecord): void {
  void playVideo(record.video_id, {
    title: record.title ?? '',
    resumeMs: record.position ?? 0,
  })
}

async function applyQuick(key: string): Promise<void> {
  activeQuick.value = key
  const quick = QUICK_FILTERS.find((item) => item.key === key)
  videoStore.setFilters({
    favorite: quick?.favorite,
    status: quick?.status,
    sort: quick?.sort ?? 'date_added',
    order: quick?.order ?? 'desc',
  })
  await videoStore.fetchVideos(true)
}

onMounted(async () => {
  videoStore.resetFilters()
  activeQuick.value = 'all'
  await Promise.all([videoStore.fetchVideos(true), historyStore.fetchRecent(12)])
})
</script>

<template>
  <div class="pb-10">
    <!-- Hero -->
    <section class="mx-auto max-w-[1600px] px-4 pt-10 sm:px-6 lg:px-8">
      <p class="font-mono text-[11px] tracking-[0.22em] text-accent">
        TIAN'S PRIVATE CINEMA
      </p>
      <h1 class="mt-3 font-serif text-3xl leading-tight text-ink sm:text-4xl">
        今日想看点什么？
      </h1>
      <p class="mt-2 text-sm text-ink-faint">
        全链路原画直出 · 馆藏
        <span class="text-ink-soft">{{ videoStore.total }}</span>
        部
      </p>
    </section>

    <!-- 继续观看 -->
    <section
      v-if="continueList.length > 0"
      class="mx-auto mt-10 max-w-[1600px] px-4 sm:px-6 lg:px-8"
    >
      <div class="mb-4 flex items-baseline justify-between">
        <h2 class="text-base text-ink">继续观看</h2>
        <router-link
          :to="{ name: 'History' }"
          class="text-xs text-ink-faint transition-colors duration-150 ease-yy hover:text-ink"
        >
          全部历史
        </router-link>
      </div>

      <div class="no-scrollbar -mx-4 flex gap-3 overflow-x-auto px-4 pb-1 sm:mx-0 sm:px-0">
        <button
          v-for="record in continueList"
          :key="record.video_id"
          type="button"
          class="group w-32 shrink-0 text-left sm:w-40"
          @click="resumePlay(record)"
        >
          <div class="relative overflow-hidden rounded-lg bg-paper-mute shadow-soft">
            <LazyImage
              :src="mediaUrl(record.poster_path) || mediaUrl(record.thumb_path)"
              :alt="displayTitle(record.title)"
              aspect="2 / 3"
            />
            <div
              class="absolute inset-0 flex items-center justify-center bg-black/0 opacity-0 transition-all duration-300 ease-yy group-hover:bg-black/10 group-hover:opacity-100"
            >
              <span
                class="flex h-8 w-8 items-center justify-center rounded-full bg-white/90 shadow-soft"
              >
                <Play :size="13" :stroke-width="1.5" class="ml-0.5 text-ink" />
              </span>
            </div>
            <div class="absolute inset-x-0 bottom-0">
              <ProgressBar :value="record.progress" height="h-[3px]" />
            </div>
          </div>
          <p class="mt-2 truncate text-[13px] text-ink">
            {{ displayTitle(record.title) }}
          </p>
          <p class="mt-0.5 truncate text-[11px] text-ink-faint">
            看到 {{ formatClock((record.position ?? 0) / 1000) }} ·
            {{ formatRelativeTime(record.watched_at) }}
          </p>
        </button>
      </div>
    </section>

    <!-- 最新入库 -->
    <section class="mx-auto mt-12 max-w-[1600px] px-4 sm:px-6 lg:px-8">
      <div class="mb-5 flex flex-wrap items-center justify-between gap-3">
        <h2 class="text-base text-ink">最新入库</h2>
        <div class="flex items-center gap-2 overflow-x-auto no-scrollbar">
          <TagPill
            v-for="quick in QUICK_FILTERS.slice(0, 3)"
            :key="quick.key"
            :label="quick.label"
            :active="activeQuick === quick.key"
            @click="applyQuick(quick.key)"
          />
        </div>
      </div>

      <VideoGrid
        :videos="videoStore.videos"
        :loading="videoStore.loading"
        :progress-map="progressMap"
        :has-more="videoStore.hasMore"
        empty-title="媒体库还是空的"
        empty-description="前往「设置」触发一次媒体库扫描，开始整理你的私家馆藏。"
        @card-click="openVideo"
        @favorite="(video) => videoStore.toggleFavorite(video.id)"
        @load-more="videoStore.loadMore()"
      />
    </section>
  </div>
</template>
