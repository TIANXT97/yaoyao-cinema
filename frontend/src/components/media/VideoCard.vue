<script setup lang="ts">
/**
 * VideoCard —— 2:3 精致海报卡片。
 *
 * 纯图无边框；hover 轻微 scale(1.02) + 阴影浮起；
 * 右上角原画画质 / 时长角标；底部观看进度细条。
 */
import { Heart, Play } from 'lucide-vue-next'
import { computed } from 'vue'

import LazyImage from '@/components/common/LazyImage.vue'
import ProgressBar from '@/components/media/ProgressBar.vue'
import { mediaUrl } from '@/api/client'
import type { Video } from '@/types/video'
import { displayBangou, displayTitle, formatClock, resolutionBadge } from '@/utils/format'

const props = withDefaults(
  defineProps<{
    video: Video
    progress?: number
    eager?: boolean
  }>(),
  { progress: 0, eager: false },
)

const emit = defineEmits<{
  (e: 'click', video: Video): void
  (e: 'favorite', video: Video): void
  (e: 'play', video: Video): void
}>()

import { buildUrl } from '@/api/client'

const poster = computed(() => {
  if (props.video.id) {
    return buildUrl(`/poster/${props.video.id}?v=${encodeURIComponent(props.video.updated_at || '1')}`)
  }
  return mediaUrl(props.video.poster_path) || mediaUrl(props.video.thumb_path)
})
const title = computed(() => displayTitle(props.video.title))
const bangou = computed(() => displayBangou(props.video.bangou, props.video.file_name))
const quality = computed(() => resolutionBadge(props.video.resolution))
const durationText = computed(() => {
  const seconds = props.video.duration ?? 0
  return seconds > 0 ? formatClock(seconds) : null
})
const isFavorite = computed(() => Number(props.video.is_favorite) === 1)
const hasProgress = computed(() => props.progress > 0.001 && props.progress < 0.98)
const episodeCount = computed(() =>
  props.video.is_series ? Math.max(Number(props.video.episode_count) || 0, 0) : 0,
)
</script>

<template>
  <article class="group cursor-pointer select-none" @click="emit('click', video)">
    <div
      class="relative overflow-hidden rounded-lg bg-paper-mute shadow-soft transition-all duration-300 ease-yy group-hover:scale-[1.02] group-hover:shadow-poster"
    >
      <LazyImage :src="poster" :alt="title" :eager="eager" aspect="2 / 3" class="w-full" />

      <!-- 右上角：原画画质 / 时长角标 -->
      <div class="pointer-events-none absolute right-1.5 top-1.5 flex flex-col items-end gap-1">
        <span
          v-if="quality"
          class="rounded-[4px] bg-white/85 px-1.5 py-0.5 text-[10px] font-medium leading-none tracking-bangou text-ink backdrop-blur-sm"
        >
          {{ quality }}
        </span>
        <span
          v-if="durationText"
          class="rounded-[4px] bg-white/85 px-1.5 py-0.5 font-mono text-[10px] leading-none tracking-bangou text-ink-soft backdrop-blur-sm"
        >
          {{ durationText }}
        </span>
      </div>

      <!-- 收藏标记 -->
      <button
        v-if="isFavorite"
        type="button"
        class="absolute left-1.5 top-1.5 flex h-6 w-6 items-center justify-center rounded-full bg-white/85 backdrop-blur-sm transition-transform duration-150 ease-yy hover:scale-105"
        aria-label="取消收藏"
        @click.stop="emit('favorite', video)"
      >
        <Heart :size="12" :stroke-width="1.5" class="fill-accent text-accent" />
      </button>

      <!-- 悬浮播放按钮 -->
      <div
        class="pointer-events-none absolute inset-0 flex items-center justify-center bg-black/0 opacity-0 transition-all duration-300 ease-yy group-hover:bg-black/10 group-hover:opacity-100"
      >
        <span
          class="flex h-9 w-9 items-center justify-center rounded-full bg-white/90 shadow-soft"
        >
          <Play :size="14" :stroke-width="1.5" class="ml-0.5 text-ink" />
        </span>
      </div>

      <!-- 剧集聚合角标：共 N 集 -->
      <span
        v-if="episodeCount > 1"
        class="pointer-events-none absolute bottom-1.5 left-1.5 rounded-[4px] bg-ink/75 px-1.5 py-0.5 text-[10px] font-medium leading-none text-white backdrop-blur-sm"
      >
        共{{ episodeCount }}集
      </span>

      <!-- 观看进度 -->
      <div v-if="hasProgress" class="absolute inset-x-0 bottom-0">
        <ProgressBar :value="progress" color="bg-accent" height="h-[3px]" />
      </div>
    </div>

    <div class="mt-2 px-0.5">
      <h3 class="truncate text-[13px] font-normal leading-snug text-ink">{{ title }}</h3>
      <p
        v-if="bangou && bangou !== '—'"
        class="mt-0.5 truncate font-mono text-[11px] tracking-bangou text-ink-faint"
      >
        {{ bangou }}
      </p>
    </div>
  </article>
</template>
