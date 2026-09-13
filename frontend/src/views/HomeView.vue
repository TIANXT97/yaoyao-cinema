<script setup lang="ts">
/**
 * HomeView —— 主页：继续观看 + 快速筛选 + 最新入库海报墙。
 */
import { Play, Trash2 } from 'lucide-vue-next'
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import ProgressBar from '@/components/media/ProgressBar.vue'
import TagPill from '@/components/media/TagPill.vue'
import VideoGrid from '@/components/media/VideoGrid.vue'
import CategoryNav from '@/components/browse/CategoryNav.vue'

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
const activeCategory = ref('all')

async function onCategoryChange(cat: string): Promise<void> {
  activeCategory.value = cat
  videoStore.setFilters({ category: cat === 'all' ? undefined : cat })
  await videoStore.fetchVideos(true)
}


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

async function handleDeleteHistory(record: RecentRecord, event?: Event): Promise<void> {
  event?.stopPropagation()
  try {
    await historyStore.deleteRecord(record.id)
  } catch {
    // 忽略错误
  }
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

    <!-- 继续观看（极简纯白胶囊卡片，免海报直出） -->
    <section
      v-if="continueList.length > 0"
      class="mx-auto mt-8 max-w-[1600px] px-4 sm:px-6 lg:px-8"
    >
      <div class="mb-3.5 flex items-baseline justify-between">
        <div class="flex items-center gap-2">
          <h2 class="text-base font-medium text-ink">继续观看</h2>
          <span class="rounded-full bg-paper-mute px-2 py-0.5 font-mono text-[11px] text-ink-faint">
            {{ continueList.length }}
          </span>
        </div>
        <router-link
          :to="{ name: 'History' }"
          class="text-xs text-ink-faint transition-colors duration-150 ease-yy hover:text-accent"
        >
          全部历史 &rarr;
        </router-link>
      </div>

      <div class="no-scrollbar -mx-4 flex gap-3 overflow-x-auto px-4 pb-2 sm:mx-0 sm:px-0">
        <div
          v-for="record in continueList"
          :key="record.video_id"
          class="group relative flex w-48 shrink-0 cursor-pointer flex-col justify-between rounded-xl border border-line/70 bg-paper p-3 text-left shadow-soft transition-all duration-200 ease-yy hover:-translate-y-0.5 hover:border-accent/40 hover:bg-paper-soft hover:shadow-md sm:w-56"
          @click="resumePlay(record)"
        >
          <!-- 右上角悬浮删除按钮 -->
          <button
            type="button"
            class="absolute right-2 top-2 flex h-6 w-6 items-center justify-center rounded-md bg-paper/90 text-ink-faint opacity-0 shadow-sm transition-all duration-150 ease-yy hover:bg-rose-50 hover:text-rose-500 group-hover:opacity-100 z-10"
            aria-label="删除观看历史"
            title="删除此项记录"
            @click.stop="handleDeleteHistory(record, $event)"
          >
            <Trash2 :size="12" :stroke-width="1.6" />
          </button>

          <!-- 头部：标题与播放图标 -->
          <div class="flex items-start justify-between gap-2 pr-5">
            <div class="min-w-0 flex-1">
              <p
                class="truncate text-[13px] font-medium text-ink transition-colors duration-150 ease-yy group-hover:text-accent"
                :title="displayTitle(record.title)"
              >
                {{ displayTitle(record.title) }}
              </p>
              <p
                v-if="record.bangou"
                class="mt-0.5 truncate font-mono text-[10px] tracking-bangou text-ink-faint"
              >
                {{ record.bangou }}
              </p>
            </div>
            <span
              class="flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-line/60 bg-paper-mute text-ink-soft transition-all duration-200 ease-yy group-hover:border-accent group-hover:bg-accent group-hover:text-white"
            >
              <Play :size="11" :stroke-width="2" class="ml-0.5" />
            </span>
          </div>

          <!-- 底部：细进度条与观看时间信息 -->
          <div class="mt-3 w-full">
            <ProgressBar :value="record.progress" height="h-[2.5px]" track="bg-line" />
            <div class="mt-1.5 flex items-center justify-between font-mono text-[10px] text-ink-faint">
              <span>看到 {{ formatClock((record.position ?? 0) / 1000) }}</span>
              <span>{{ Math.round(record.progress * 100) }}%</span>
            </div>
          </div>
        </div>
      </div>
    </section>


    <!-- 分类胶囊栏 -->
    <section class="mx-auto mt-8 max-w-[1600px] px-4 sm:px-6 lg:px-8">
      <CategoryNav v-model="activeCategory" @change="onCategoryChange" />
    </section>

    <!-- 最新入库 -->
    <section class="mx-auto mt-6 max-w-[1600px] px-4 sm:px-6 lg:px-8">
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
