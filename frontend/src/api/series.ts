/**
 * 系列 API（与 tags.ts 分离，保持目录树一一对应）。
 */

import type { Series } from '@/types/actor'

import { http } from './client'

/** `GET /series` 系列列表（series.video_count 由触发器维护）。 */
export function listSeries(): Promise<Series[]> {
  return http.get<Series[]>('/series')
}
