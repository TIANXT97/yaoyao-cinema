/**
 * 观看历史 Store（续播时间线）。
 */

import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { deleteHistory, getRecentHistory, HISTORY_CAP } from '@/api/history'
import type { HistoryGroup, RecentRecord } from '@/types/history'
import { formatDate } from '@/utils/format'

export const useHistoryStore = defineStore('history', () => {
  const recentVideos = ref<RecentRecord[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  const empty = computed(() => !loading.value && recentVideos.value.length === 0)

  async function fetchRecent(limit = HISTORY_CAP): Promise<void> {
    loading.value = true
    error.value = null
    try {
      recentVideos.value = await getRecentHistory(limit)
    } catch (err) {
      error.value = err instanceof Error ? err.message : '观看历史加载失败'
    } finally {
      loading.value = false
    }
  }

  /** 按自然日分组（今天 / 昨天 / 具体日期）。 */
  const grouped = computed<HistoryGroup[]>(() => {
    const groups: HistoryGroup[] = []
    for (const record of recentVideos.value) {
      const label = formatDate(record.watched_at)
      const existing = groups.find((group) => group.label === label)
      if (existing) existing.records.push(record)
      else groups.push({ label, records: [record] })
    }
    return groups
  })

  function remove(videoId: string): void {
    recentVideos.value = recentVideos.value.filter(
      (record) => record.video_id !== videoId,
    )
  }

  async function deleteRecord(historyId: string): Promise<void> {
    // 乐观更新：前端列表即刻移除匹配项（按 record.id === historyId 或 record.video_id === historyId）
    recentVideos.value = recentVideos.value.filter(
      (record) => record.id !== historyId && record.video_id !== historyId,
    )
    try {
      await deleteHistory(historyId)
    } catch (err) {
      // 若后端删除失败，刷新列表保证状态最终一致
      await fetchRecent()
      throw err
    }
  }

  function clear(): void {
    recentVideos.value = []
  }

  return {
    recentVideos,
    loading,
    error,
    empty,
    grouped,
    fetchRecent,
    deleteRecord,
    remove,
    clear,
  }
})

