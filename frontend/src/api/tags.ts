/**
 * 标签 / 系列 API（对齐 ARCHITECTURE.md 2.5.5）。
 */

import type { Series, Tag, TagCategory } from '@/types/actor'

import { http } from './client'

/** `GET /tags` 标签列表（带影片计数）。 */
export function listTags(category?: TagCategory): Promise<Tag[]> {
  return http.get<Tag[]>('/tags', { query: { category } })
}

/** `GET /series` 系列列表。 */
export function listSeries(): Promise<Series[]> {
  return http.get<Series[]>('/series')
}
