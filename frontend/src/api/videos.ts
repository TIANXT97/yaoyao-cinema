/**
 * 影片 API（对齐 ARCHITECTURE.md 2.5.1 / server/api/videos.py）。
 */

import type { MessageResponse, Paginated, QueryParams } from '@/types/api'
import type { ScrapeStatus, SortField, SortOrder, Video, VideoDetail, VideoFilters } from '@/types/video'

import { http } from './client'

export interface ListVideosParams {
  page?: number
  per_page?: number
  sort?: SortField
  order?: SortOrder
  search?: string
  actor_id?: string
  tag_id?: string
  series_id?: string
  studio?: string
  favorite?: boolean
  status?: ScrapeStatus
  /** 剧集按系列聚合成一张海报卡片；电影保持单部展示。 */
  group_series?: boolean
}

export interface UpdateVideoPayload {
  title?: string
  original_title?: string
  sort_title?: string
  bangou?: string
  bangou_norm?: string
  series_id?: string
  studio?: string
  director?: string
  release_date?: string
  poster_path?: string
  thumb_path?: string
  backdrop_path?: string
  plot?: string
  rating?: number
  scrape_status?: ScrapeStatus
  scrape_source?: string
  is_favorite?: number
  is_hidden?: number
}

/** 将前端筛选对象映射为后端查询参数。 */
export function filtersToParams(
  filters: VideoFilters,
  page: number,
  perPage: number,
): ListVideosParams {
  return {
    page,
    per_page: perPage,
    sort: filters.sort,
    order: filters.order,
    search: filters.search.trim() || undefined,
    actor_id: filters.actorId,
    tag_id: filters.tagId,
    series_id: filters.seriesId,
    studio: filters.studio,
    favorite: filters.favorite,
    status: filters.status,
    group_series: filters.groupSeries,
  }
}

/** `GET /videos` 影片列表（分页、排序、筛选）。 */
export function listVideos(params: ListVideosParams = {}): Promise<Paginated<Video>> {
  return http.get<Paginated<Video>>('/videos', {
    query: params as QueryParams,
  })
}

/** `GET /videos/{id}` 影片详情（含演员、标签、续播点）。 */
export function getVideo(id: string): Promise<VideoDetail> {
  return http.get<VideoDetail>(`/videos/${encodeURIComponent(id)}`)
}

/** `PUT /videos/{id}` 更新影片元数据。 */
export function updateVideo(
  id: string,
  payload: UpdateVideoPayload,
): Promise<VideoDetail> {
  return http.put<VideoDetail>(`/videos/${encodeURIComponent(id)}`, payload)
}

/** `DELETE /videos/{id}` 删除记录（不删磁盘文件）。 */
export function deleteVideo(id: string): Promise<MessageResponse> {
  return http.delete<MessageResponse>(`/videos/${encodeURIComponent(id)}`)
}

/** `POST /videos/{id}/favorite` 切换收藏，返回新的 is_favorite 值。 */
export async function toggleFavorite(id: string): Promise<boolean> {
  const res = await http.post<MessageResponse>(
    `/videos/${encodeURIComponent(id)}/favorite`,
  )
  const matched = /is_favorite=(\d)/.exec(res.message)
  return matched ? matched[1] === '1' : true
}

/** `POST /videos/{id}/hide` 切换隐藏，返回新的 is_hidden 值。 */
export async function toggleHide(id: string): Promise<boolean> {
  const res = await http.post<MessageResponse>(
    `/videos/${encodeURIComponent(id)}/hide`,
  )
  const matched = /is_hidden=(\d)/.exec(res.message)
  return matched ? matched[1] === '1' : true
}
