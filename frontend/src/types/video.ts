/**
 * 影片类型（对齐 server/models.py VideoOut / VideoDetail 与 videos 表字段）。
 */

import type { Actor, Series, Tag } from './actor'
import type { Paginated } from './api'

export type ScrapeStatus = 'pending' | 'matched' | 'failed' | 'manual'

export type BangouType = 'censored' | 'uncensored' | 'fc2'

export interface Video {
  id: string
  title: string | null
  original_title: string | null
  sort_title: string | null
  bangou: string | null
  bangou_norm: string | null
  series_id: string | null
  studio: string | null
  director: string | null
  release_date: string | null
  duration: number | null
  resolution: string | null
  video_codec: string | null
  audio_codec: string | null
  container: string | null
  bitrate: number | null
  poster_path: string | null
  thumb_path: string | null
  backdrop_path: string | null
  plot: string | null
  rating: number | null
  scrape_status: ScrapeStatus
  scrape_source: string | null
  nfo_path: string | null
  play_count: number
  last_played: string | null
  is_favorite: number
  is_hidden: number
  file_path: string
  file_name: string
  file_size: number
  date_added: string | null
  scrape_time: string | null
  created_at: string | null
  updated_at: string | null
}

export interface VideoDetail extends Video {
  actors: Actor[]
  tags: Tag[]
  series: Series | null
  resume_position: number
  resume_progress: number
}

export type VideoListResponse = Paginated<Video>

/** 排序字段白名单（对齐 server/services/video_service.py SORTABLE_COLUMNS）。 */
export type SortField =
  | 'date_added'
  | 'release_date'
  | 'title'
  | 'rating'
  | 'play_count'
  | 'last_played'
  | 'file_size'

export type SortOrder = 'asc' | 'desc'

/** 列表筛选状态（映射为 `/api/videos` 查询参数）。 */
export interface VideoFilters {
  sort: SortField
  order: SortOrder
  search: string
  actorId?: string
  tagId?: string
  seriesId?: string
  studio?: string
  favorite?: boolean
  status?: ScrapeStatus
}

export const DEFAULT_FILTERS: VideoFilters = {
  sort: 'date_added',
  order: 'desc',
  search: '',
}

/** 快捷筛选（未看 / 收藏 / 分类）。 */
export interface QuickFilter {
  key: string
  label: string
  favorite?: boolean
  status?: ScrapeStatus
  sort?: SortField
  order?: SortOrder
}

export const QUICK_FILTERS: QuickFilter[] = [
  { key: 'all', label: '全部', sort: 'date_added', order: 'desc' },
  { key: 'favorite', label: '收藏', favorite: true },
  { key: 'unwatched', label: '未看', sort: 'date_added', order: 'desc' },
  { key: 'matched', label: '已刮削', status: 'matched' },
  { key: 'pending', label: '待刮削', status: 'pending' },
]
