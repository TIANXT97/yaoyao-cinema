/**
 * 观看历史类型（对齐 server/models.py WatchHistoryOut / ResumeRecord
 * 与 history_service.get_recent 联表返回结构）。
 */

import type { Video } from './video'

export interface WatchRecord {
  id: string
  video_id: string
  position: number
  duration: number
  progress: number
  completed: number
  watched_at: string | null
  device: string | null
}

/**
 * `GET /api/history/recent` 每行：历史字段 + 影片摘要
 * （title / bangou / poster_path / thumb_path / file_size / video_duration）。
 */
export interface RecentRecord extends WatchRecord {
  title: string | null
  bangou: string | null
  poster_path: string | null
  thumb_path: string | null
  file_size: number | null
  video_duration: number | null
  is_hidden: number
}

export interface ResumeRecord {
  video: Video
  position: number
  duration: number
  progress: number
  watched_at: string | null
}

/** 历史时间线分组。 */
export interface HistoryGroup {
  label: string
  records: RecentRecord[]
}
