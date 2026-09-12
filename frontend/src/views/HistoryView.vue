<script setup lang="ts">
/**
 * HistoryView —— 播放历史与续播时间线。
 */
import { Play, RefreshCw } from 'lucide-vue-next'
import { computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'

import { mediaUrl } from '@/api/client'
import EmptyState from '@/components/common/EmptyState.vue'
import LazyImage from '@/components/common/LazyImage.vue'
import ProgressBar from '@/components/media/ProgressBar.vue'
import PageHeader from '@/components/layout/PageHeader.vue'
import { useNativePlayer } from '@/composables/useNativePlayer'
import { useHistoryStore } from '@/stores/history'
import type { RecentRecord } from '@/types/history'
import { displayTitle, formatClock, formatRelativeTime } from '@/utils/format'

const router = useRouter()
const historyStore = useHistoryStore()
const { playVideo } = useNativePlayer()

function groupLabel(dateKey: string): string {
  const today = new Date()
  const iso = (d: Date) =>
    `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(
      d.getDate(),
    ).padStart(2, '0')}`
  if (dateKey === iso(today)) return '今天'
  const yesterday = new Date(today.getTime() - 24 * 60 * 60 * 1000)
  if (dateKey === iso(yesterday)) return '昨天'
  return dateKey
}

function totalSeconds(record: RecentRecord): number {
  if (record.video_duration && record.video_duration > 0) return record.video_duration
  return (record.duration ?? 0) / 1000
}

const watchedSeconds = (record: RecentRecord): number => (record.position ?? 0) / 1000

function resume(record: RecentRecord): void {
  void playVideo(record.video_id, {
    title: record.title ?? '',
    resumeMs: record.position ?? 0,
  })
}

function openDetail(record: RecentRecord): void {
  void router.push({ name: 'VideoDetail', params: { id: record.video_id } })
}

const grouped = computed(() =>
  historyStore.grouped.map((group) => ({
    ...group,
    label: groupLabel(group.label),
  })),
)

onMounted(() => {
  void historyStore.fetchRecent(60)
})
</script>

<template>
  <div>
    <PageHeader
      title="播放历史"
      :subtitle="`${historyStore.recentVideos.length} 条观看记录 · 点击即可续播`"
      bordered
    >
      <template #actions>
        <button
          type="button"
          class="flex h-8 w-8 items-center justify-center rounded-full text-ink-faint transition-colors duration-150 ease-yy hover:bg-paper-mute hover:text-ink"
          aria-label="刷新"
          @click="historyStore.fetchRecent(60)"
        >
          <RefreshCw
            :size="16"
            :stroke-width="1.5"
            :class="historyStore.loading ? 'animate-spin' : ''"
          />
        </button>
      </template>
    </PageHeader>

    <section class="mx-auto max-w-3xl px-4 pt-6 pb-12 sm:px-6">
      <EmptyState
        v-if="historyStore.empty"
        title="还没有观看记录"
        description="开始播放任意影片后，这里会留下你的观看足迹。"
      />

      <div v-else class="space-y-8">
        <div v-for="group in grouped" :key="group.label">
          <p class="mb-3 text-[11px] tracking-[0.16em] text-ink-faint">
            {{ group.label }}
          </p>

          <div class="divide-y divide-line">
            <div
              v-for="record in group.records"
              :key="record.id"
              class="group flex items-center gap-4 py-3"
            >
              <button
                type="button"
                class="relative w-14 shrink-0 overflow-hidden rounded-md bg-paper-mute sm:w-16"
                @click="openDetail(record)"
              >
                <LazyImage
                  :src="mediaUrl(record.poster_path) || mediaUrl(record.thumb_path)"
                  :alt="displayTitle(record.title)"
                  aspect="2 / 3"
                />
                <div class="absolute inset-x-0 bottom-0">
                  <ProgressBar :value="record.progress" height="h-[3px]" />
                </div>
              </button>

              <div class="min-w-0 flex-1">
                <button
                  type="button"
                  class="block max-w-full truncate text-left text-sm text-ink transition-colors duration-150 ease-yy hover:text-accent"
                  @click="openDetail(record)"
                >
                  {{ displayTitle(record.title) }}
                </button>
                <p
                  v-if="record.bangou"
                  class="mt-0.5 truncate font-mono text-[11px] tracking-bangou text-ink-faint"
                >
                  {{ record.bangou }}
                </p>
                <div class="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-ink-mute">
                  <span class="font-mono">
                    {{ formatClock(watchedSeconds(record)) }} /
                    {{ formatClock(totalSeconds(record)) }}
                  </span>
                  <span>{{ formatRelativeTime(record.watched_at) }}</span>
                  <span v-if="record.completed" class="text-accent">已看完</span>
                </div>
              </div>

              <button
                type="button"
                class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-line text-ink-soft transition-colors duration-150 ease-yy hover:border-accent/50 hover:text-accent"
                aria-label="继续播放"
                @click="resume(record)"
              >
                <Play :size="14" :stroke-width="1.5" class="ml-0.5" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>
