/**
 * 刮削控制 API（对齐 ARCHITECTURE.md 2.5.4 / server/api/scraper_api.py）。
 */

import { http } from './client'

export interface ScanResult {
  discovered: number
  added: number
  skipped: number
  missing: number
  media_root: string
  started_at: string | null
  finished_at: string | null
}

export interface PipelineStatus {
  running: boolean
  started_at: string | null
  finished_at: string | null
  total: number
  processed: number
  matched: number
  failed: number
  last_video_id: string | null
  last_result: unknown
}

export interface ScannerStatus {
  running: boolean
  started_at: string | null
  finished_at: string | null
  last_result: ScanResult | null
}

export interface ScraperStatus extends ScannerStatus {
  pipeline: PipelineStatus
}

export interface ScrapeResult {
  success: boolean
  video_id?: string
  source?: string
  message?: string
  [key: string]: unknown
}

export interface ScrapeAllResult {
  started: boolean
  sync?: boolean
  reason?: string
  total?: number
  processed?: number
  matched?: number
  failed?: number
  [key: string]: unknown
}

/** `POST /scraper/scan` 触发全库文件扫描。 */
export function triggerScan(): Promise<ScanResult> {
  return http.post<ScanResult>('/scraper/scan')
}

/** `GET /scraper/status` 扫描 / 刮削任务状态。 */
export function getScraperStatus(): Promise<ScraperStatus> {
  return http.get<ScraperStatus>('/scraper/status')
}

/** `POST /scraper/scrape/{id}` 单部影片刮削。 */
export function scrapeVideo(videoId: string): Promise<ScrapeResult> {
  return http.post<ScrapeResult>(`/scraper/scrape/${encodeURIComponent(videoId)}`)
}

/** `POST /scraper/scrape-all` 批量刮削 pending / failed 影片。 */
export function scrapeAll(options?: {
  sync?: boolean
  statuses?: string
  limit?: number
}): Promise<ScrapeAllResult> {
  return http.post<ScrapeAllResult>('/scraper/scrape-all', undefined, {
    query: {
      sync: options?.sync,
      statuses: options?.statuses,
      limit: options?.limit,
    },
  })
}
