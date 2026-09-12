/**
 * 演员 API（对齐 ARCHITECTURE.md 2.5.5 / server/api/actors.py）。
 */

import type { Actor } from '@/types/actor'
import type { Video } from '@/types/video'

import { http } from './client'

export interface ActorDetail extends Actor {
  videos: Video[]
}

/** `GET /actors` 演员列表（带影片计数）。 */
export function listActors(params?: {
  search?: string
  limit?: number
  offset?: number
}): Promise<Actor[]> {
  return http.get<Actor[]>('/actors', {
    query: {
      search: params?.search,
      limit: params?.limit,
      offset: params?.offset,
    },
  })
}

/** `GET /actors/{id}` 演员详情 + 作品列表。 */
export function getActor(id: string): Promise<ActorDetail> {
  return http.get<ActorDetail>(`/actors/${encodeURIComponent(id)}`)
}
