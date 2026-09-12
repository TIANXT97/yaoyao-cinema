<script setup lang="ts">
/**
 * VideoDetailView —— 影片详情：Backdrop 大图、演员头像网格、标签、一键原画直解。
 */
import {
  ArrowLeft,
  Calendar,
  Clock,
  HardDrive,
  Heart,
  Layers,
  MonitorPlay,
  Play,
} from 'lucide-vue-next'
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { mediaUrl } from '@/api/client'
import { listVideos } from '@/api/videos'
import { useNativePlayer } from '@/composables/useNativePlayer'
import EmptyState from '@/components/common/EmptyState.vue'
import LazyImage from '@/components/common/LazyImage.vue'
import ActorCard from '@/components/media/ActorCard.vue'
import TagPill from '@/components/media/TagPill.vue'
import VideoGrid from '@/components/media/VideoGrid.vue'
import { useVideoStore } from '@/stores/video'
import type { Actor } from '@/types/actor'
import type { Video } from '@/types/video'
import {
  displayBangou,
  displayTitle,
  formatClock,
  formatDate,
  formatDurationText,
  formatFileSize,
  resolutionBadge,
} from '@/utils/format'

const route = useRoute()
const router = useRouter()
const store = useVideoStore()
const { playVideo } = useNativePlayer()

const id = computed(() => String(route.params.id))
const detail = computed(() => store.currentVideo)
const seriesVideos = ref<Video[]>([])
const favoriting = ref(false)

const backdrop = computed(
  () => mediaUrl(detail.value?.backdrop_path) || mediaUrl(detail.value?.poster_path),
)
const poster = computed(() => mediaUrl(detail.value?.poster_path))
const quality = computed(() => resolutionBadge(detail.value?.resolution))
const resumePercent = computed(() => detail.value?.resume_progress ?? 0)
const resumeSeconds = computed(() => (detail.value?.resume_position ?? 0) / 1000)
const isFavorite = computed(() => Number(detail.value?.is_favorite) === 1)

const metaItems = computed(() => {
  const video = detail.value
  if (!video) return []
  return [
    { icon: Calendar, label: video.release_date ? formatDate(video.release_date) : '—' },
    { icon: Clock, label: formatDurationText(video.duration) },
    { icon: MonitorPlay, label: quality.value ?? video.resolution ?? '原画' },
    { icon: HardDrive, label: formatFileSize(video.file_size) },
  ]
})

function play(): void {
  const video = detail.value
  if (!video) return
  // 原生环境走 ExoPlayer 硬解直出，Web/PWA 回退到 CustomPlayer 路由
  void playVideo(video.id, {
    title: video.title ?? '',
    resumeMs: video.resume_position ?? 0,
  })
}

async function toggleFavorite(): Promise<void> {
  if (!detail.value || favoriting.value) return
  favoriting.value = true
  try {
    await store.toggleFavorite(detail.value.id)
  } finally {
    favoriting.value = false
  }
}

function openActor(actor: Actor): void {
  void router.push({ name: 'ActorDetail', params: { id: actor.id } })
}

function openVideo(video: Video): void {
  void router.push({ name: 'VideoDetail', params: { id: video.id } })
}

function goBack(): void {
  if (window.history.length > 1) router.back()
  else void router.push({ name: 'Home' })
}

async function load(): Promise<void> {
  store.currentVideo = null
  seriesVideos.value = []
  const result = await store.fetchVideoDetail(id.value)
  if (result?.series_id) {
    try {
      const data = await listVideos({ series_id: result.series_id, per_page: 12 })
      seriesVideos.value = data.items.filter((item) => item.id !== result.id)
    } catch {
      seriesVideos.value = []
    }
  }
}

onMounted(load)
watch(
  () => route.params.id,
  () => {
    if (route.name === 'VideoDetail') void load()
  },
)
</script>

<template>
  <div class="pb-16">
    <div
      v-if="detail"
      class="relative h-[280px] w-full overflow-hidden bg-paper-mute sm:h-[400px]"
    >
      <img
        v-if="backdrop"
        :src="backdrop"
        :alt="displayTitle(detail.title)"
        class="h-full w-full object-cover object-top"
      />
      <div
        class="absolute inset-0 bg-gradient-to-t from-paper via-paper/55 to-transparent"
      />
      <button
        type="button"
        class="absolute left-4 top-4 flex h-9 w-9 items-center justify-center rounded-full bg-white/80 text-ink backdrop-blur-md transition-colors duration-150 ease-yy hover:bg-white sm:left-6"
        aria-label="返回"
        @click="goBack"
      >
        <ArrowLeft :size="18" :stroke-width="1.6" />
      </button>
    </div>

    <div v-if="detail" class="mx-auto max-w-[1200px] px-4 sm:px-6 lg:px-8">
      <div class="flex flex-col gap-6 sm:flex-row sm:gap-8">
        <div class="-mt-20 w-32 shrink-0 sm:-mt-32 sm:w-48">
          <div class="overflow-hidden rounded-lg bg-paper-mute shadow-poster">
            <LazyImage
              :src="poster"
              :alt="displayTitle(detail.title)"
              aspect="2 / 3"
              eager
            />
          </div>
        </div>

        <div class="min-w-0 flex-1 sm:pt-4">
          <h1 class="font-serif text-xl leading-snug text-ink sm:text-3xl">
            {{ displayTitle(detail.title) }}
          </h1>
          <p
            v-if="detail.original_title && detail.original_title !== detail.title"
            class="mt-1.5 truncate text-sm text-ink-faint"
          >
            {{ detail.original_title }}
          </p>
          <p class="mt-2 font-mono text-xs tracking-bangou text-ink-faint">
            {{ displayBangou(detail.bangou, detail.file_name) }}
          </p>

          <!-- 元信息 -->
          <div class="mt-4 flex flex-wrap items-center gap-x-5 gap-y-2 text-xs text-ink-soft">
            <span
              v-for="(item, index) in metaItems"
              :key="index"
              class="inline-flex items-center gap-1.5"
            >
              <component :is="item.icon" :size="14" :stroke-width="1.5" class="text-ink-mute" />
              {{ item.label }}
            </span>
          </div>

          <!-- 操作 -->
          <div class="mt-6 flex flex-wrap items-center gap-3">
            <button
              type="button"
              class="inline-flex items-center gap-2 rounded-full bg-ink px-6 py-2.5 text-sm text-white transition-colors duration-150 ease-yy hover:bg-ink/85"
              @click="play"
            >
              <Play :size="16" :stroke-width="1.6" class="ml-0.5" />
              {{ resumePercent > 0.02 ? '继续观看' : '原画直解' }}
            </button>

            <button
              type="button"
              class="inline-flex items-center gap-2 rounded-full border border-line px-5 py-2.5 text-sm transition-colors duration-150 ease-yy hover:border-accent/50"
              :class="isFavorite ? 'text-accent' : 'text-ink-soft hover:text-ink'"
              @click="toggleFavorite"
            >
              <Heart
                :size="16"
                :stroke-width="1.5"
                :class="isFavorite ? 'fill-accent' : ''"
              />
              {{ isFavorite ? '已收藏' : '收藏' }}
            </button>

            <span
              v-if="resumePercent > 0.02"
              class="text-xs text-ink-faint"
            >
              上次看到 {{ formatClock(resumeSeconds) }}
            </span>
          </div>
        </div>
      </div>

      <!-- 剧情简介 -->
      <section v-if="detail.plot" class="mt-10 max-w-3xl">
        <h2 class="text-sm text-ink">简介</h2>
        <p class="mt-3 whitespace-pre-line text-sm leading-relaxed text-ink-soft">
          {{ detail.plot }}
        </p>
      </section>

      <!-- 演员 -->
      <section v-if="detail.actors.length > 0" class="mt-10">
        <h2 class="mb-4 text-sm text-ink">演员</h2>
        <div class="grid grid-cols-4 gap-4 sm:grid-cols-6 lg:grid-cols-8">
          <ActorCard
            v-for="actor in detail.actors"
            :key="actor.id"
            :actor="actor"
            @click="openActor"
          />
        </div>
      </section>

      <!-- 标签 -->
      <section v-if="detail.tags.length > 0" class="mt-10">
        <h2 class="mb-4 text-sm text-ink">标签</h2>
        <div class="flex flex-wrap gap-2">
          <TagPill
            v-for="tag in detail.tags"
            :key="tag.id"
            :label="tag.name"
            :interactive="false"
          />
        </div>
      </section>

      <!-- 系列 -->
      <section v-if="seriesVideos.length > 0" class="mt-12">
        <div class="mb-5 flex items-center gap-2">
          <Layers :size="16" :stroke-width="1.5" class="text-ink-faint" />
          <h2 class="text-sm text-ink">
            系列 · {{ detail.series?.name ?? '同系列作品' }}
          </h2>
        </div>
        <VideoGrid
          :videos="seriesVideos"
          :infinite="false"
          :has-more="false"
          @card-click="openVideo"
        />
      </section>
    </div>

    <EmptyState
      v-else-if="!store.detailLoading"
      title="影片不存在"
      description="该记录可能已被移除，或链接有误。"
    />

    <div
      v-else
      class="mx-auto flex max-w-[1200px] items-center justify-center px-4 py-32"
    >
      <span class="text-xs text-ink-mute">载入中…</span>
    </div>
  </div>
</template>
