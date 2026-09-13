/**
 * 观看历史 API（对齐 ARCHITECTURE.md 2.5.3 / server/api/history.py）。
 */

import type { MessageResponse } from '@/types/api'
import type { RecentRecord, WatchRecord } from '@/types/history'

import { http } from './client'

export interface ReportProgressPayload {
  video_id: string
  position: number
  duration: number
  device?: string
}

/** `POST /history` 上报播放进度。 */
export function reportProgress(
  payload: ReportProgressPayload,
): Promise<MessageResponse> {
  return http.post<MessageResponse>('/history', payload)
}

/** `GET /history/recent` 最近观看（续播列表，附影片摘要）。 */
export function getRecentHistory(limit = 20): Promise<RecentRecord[]> {
  return http.get<RecentRecord[]>('/history/recent', { query: { limit } })
}

/** `GET /history/{video_id}` 某影片最新续播点。 */
export function getResumePoint(videoId: string): Promise<WatchRecord> {
  return http.get<WatchRecord>(`/history/${encodeURIComponent(videoId)}`)
}

/** `DELETE /history/{id}` 删除历史记录。 */
export function deleteHistory(historyId: string): Promise<MessageResponse> {
  return http.delete<MessageResponse>(`/history/${encodeURIComponent(historyId)}`)
}

