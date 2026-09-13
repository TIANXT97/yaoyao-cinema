/**
 * 影片状态 Store（列表 / 详情 / 筛选 / 收藏）。
 */

import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { getVideo, listVideos, toggleFavorite as toggleFavoriteApi } from '@/api/videos'
import type { Pagination } from '@/types/api'
import {
  DEFAULT_FILTERS,
  type Video,
  type VideoDetail,
  type VideoFilters,
} from '@/types/video'
import { DEFAULT_PER_PAGE } from '@/utils/constants'

export const useVideoStore = defineStore('video', () => {
  // === 状态 ===
  const videos = ref<Video[]>([])
  const currentVideo = ref<VideoDetail | null>(null)
  const loading = ref(false)
  const detailLoading = ref(false)
  const error = ref<string | null>(null)
  const pagination = ref<Pagination>({
    page: 0,
    per_page: DEFAULT_PER_PAGE,
    total: 0,
    total_pages: 0,
  })
  const filters = ref<VideoFilters>({ ...DEFAULT_FILTERS })

  // === 计算 ===
  const hasMore = computed(
    () => pagination.value.page > 0 && pagination.value.page < pagination.value.total_pages,
  )
  const total = computed(() => pagination.value.total)
  const isEmpty = computed(() => !loading.value && videos.value.length === 0)

  // === 动作 ===
  function setFilters(partial: Partial<VideoFilters>): void {
    filters.value = { ...filters.value, ...partial }
  }

  function resetFilters(): void {
    filters.value = { ...DEFAULT_FILTERS }
  }

  /** 拉取影片列表；`reset=true` 时回到第一页并替换数据。 */
  async function fetchVideos(reset = false): Promise<void> {
    if (loading.value) return
    if (reset) {
      pagination.value = { ...pagination.value, page: 0, total: 0, total_pages: 0 }
    }

    const nextPage = pagination.value.page + 1
    loading.value = true
    error.value = null

    try {
      const data = await listVideos({
        page: nextPage,
        per_page: pagination.value.per_page || DEFAULT_PER_PAGE,
        sort: filters.value.sort,
        order: filters.value.order,
        search: filters.value.search.trim() || undefined,
        actor_id: filters.value.actorId,
        tag_id: filters.value.tagId,
        series_id: filters.value.seriesId,
        studio: filters.value.studio,
        favorite: filters.value.favorite,
        status: filters.value.status,
        group_series: filters.value.groupSeries,
      })

      videos.value = reset ? data.items : [...videos.value, ...data.items]
      pagination.value = data.pagination
    } catch (err) {
      error.value = err instanceof Error ? err.message : '影片列表加载失败'
    } finally {
      loading.value = false
    }
  }

  /** 无限滚动追加下一页。 */
  async function loadMore(): Promise<void> {
    if (loading.value || !hasMore.value) return
    await fetchVideos(false)
  }

  /** 加载影片详情。 */
  async function fetchVideoDetail(id: string): Promise<VideoDetail | null> {
    detailLoading.value = true
    error.value = null
    try {
      currentVideo.value = await getVideo(id)
      return currentVideo.value
    } catch (err) {
      currentVideo.value = null
      error.value = err instanceof Error ? err.message : '影片详情加载失败'
      return null
    } finally {
      detailLoading.value = false
    }
  }

  /** 切换收藏（乐观更新列表与详情）。 */
  async function toggleFavorite(id: string): Promise<boolean> {
    const value = await toggleFavoriteApi(id)
    for (const video of videos.value) {
      if (video.id === id) video.is_favorite = value ? 1 : 0
    }
    if (currentVideo.value?.id === id) {
      currentVideo.value.is_favorite = value ? 1 : 0
    }
    return value
  }

  /** 局部更新（播放进度等）。 */
  function patchVideo(id: string, patch: Partial<Video>): void {
    for (const video of videos.value) {
      if (video.id === id) Object.assign(video, patch)
    }
    if (currentVideo.value?.id === id) Object.assign(currentVideo.value, patch)
  }

  function clear(): void {
    videos.value = []
    currentVideo.value = null
    error.value = null
    pagination.value = { ...pagination.value, page: 0, total: 0, total_pages: 0 }
  }

  return {
    // state
    videos,
    currentVideo,
    loading,
    detailLoading,
    error,
    pagination,
    filters,
    // getters
    hasMore,
    total,
    isEmpty,
    // actions
    setFilters,
    resetFilters,
    fetchVideos,
    loadMore,
    fetchVideoDetail,
    toggleFavorite,
    patchVideo,
    clear,
  }
})
