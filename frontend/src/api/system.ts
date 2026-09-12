/**
 * 系统 API（对齐 ARCHITECTURE.md 2.5.6 / server/api/system.py）。
 */

import type { HealthResponse } from '@/types/api'

import { http } from './client'

export interface VideoStats {
  total: number
  total_size: number
  favorites: number
  watched: number
  pending: number
  matched: number
  failed: number
  manual: number
}

export interface SystemStats {
  videos: VideoStats
  series: number
  actors: number
  tags: number
  history_records: number
  media_root: string
  database_path: string
  media_root_exists: boolean
}

export interface StudioItem {
  name: string
  video_count: number
}

/** `GET /system/stats` 系统统计。 */
export function getSystemStats(): Promise<SystemStats> {
  return http.get<SystemStats>('/system/stats')
}

/** `GET /system/health` 健康检查。 */
export function getHealth(): Promise<HealthResponse> {
  return http.get<HealthResponse>('/system/health')
}

/** `GET /studios` 制作商列表（从 videos 聚合）。 */
export function listStudios(): Promise<StudioItem[]> {
  return http.get<StudioItem[]>('/studios')
}
