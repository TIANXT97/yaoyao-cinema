<script setup lang="ts">
/**
 * HistoryView —— 播放历史与续播时间线。
 */
import { Play, RefreshCw } from 'lucide-vue-next'
import { computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'

import EmptyState from '@/components/common/EmptyState.vue'
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

    <section class="mx-auto max-w-4xl px-4 pt-6 pb-12 sm:px-6">
      <EmptyState
        v-if="historyStore.empty"
        title="还没有观看记录"
        description="开始播放任意影片后，这里会留下你的观看足迹。"
      />

      <div v-else class="space-y-6">
        <div v-for="group in grouped" :key="group.label">
          <div class="mb-2.5 flex items-center justify-between">
            <p class="text-[11px] font-medium tracking-[0.16em] text-ink-faint">
              {{ group.label }}
            </p>
            <span class="text-[11px] text-ink-mute">
              {{ group.records.length }} 部影片
            </span>
          </div>

          <div class="space-y-2">
            <div
              v-for="record in group.records"
              :key="record.id"
              class="group flex cursor-pointer items-center gap-3.5 rounded-xl border border-line/70 bg-paper px-3.5 py-2.5 shadow-soft transition-all duration-200 ease-yy hover:border-accent/40 hover:bg-paper-soft hover:shadow-md"
              @click="openDetail(record)"
            >
              <!-- 左侧：极简播放圆钮，秒续播 + 悬浮微光 -->
              <button
                type="button"
                class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-line bg-paper text-ink-soft shadow-soft transition-all duration-200 ease-yy hover:scale-105 hover:border-accent hover:bg-accent hover:text-white hover:shadow-[0_0_12px_rgba(212,165,116,0.35)]"
                aria-label="继续播放"
                @click.stop="resume(record)"
              >
                <Play :size="13" :stroke-width="2" class="ml-0.5" />
              </button>

              <!-- 中间：影片标题 + 番号/分集/完结徽标 + 极细圆润进度槽 -->
              <div class="min-w-0 flex-1">
                <div class="flex items-center gap-2">
                  <span
                    class="truncate text-[13px] font-medium text-ink transition-colors duration-150 ease-yy group-hover:text-accent sm:text-sm"
                  >
                    {{ displayTitle(record.title) }}
                  </span>
                  <span
                    v-if="record.bangou"
                    class="shrink-0 rounded border border-line/60 bg-paper-mute px-1.5 py-0.5 font-mono text-[10px] tracking-bangou text-ink-faint"
                  >
                    {{ record.bangou }}
                  </span>
                  <span
                    v-if="record.completed"
                    class="shrink-0 rounded bg-accent/10 px-1.5 py-0.5 text-[10px] font-medium text-accent"
                  >
                    已看完
                  </span>
                </div>

                <div class="mt-1.5 flex items-center gap-2.5">
                  <div class="flex-1">
                    <ProgressBar :value="record.progress" height="h-[2.5px]" track="bg-line" />
                  </div>
                  <span class="shrink-0 font-mono text-[10px] text-ink-faint">
                    {{ Math.round(record.progress * 100) }}%
                  </span>
                </div>
              </div>

              <!-- 右侧：当前进度 / 总时长 与 上次观看相对时间 -->
              <div class="shrink-0 text-right">
                <div class="font-mono text-[11px] text-ink-soft sm:text-xs">
                  {{ formatClock(watchedSeconds(record)) }}
                  <span class="text-ink-mute">/</span>
                  {{ formatClock(totalSeconds(record)) }}
                </div>
                <div class="mt-0.5 text-[10px] text-ink-faint sm:text-[11px]">
                  {{ formatRelativeTime(record.watched_at) }}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>
