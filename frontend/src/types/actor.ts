/**
 * 演员 / 标签 / 系列类型（对齐 server/models.py ActorOut / TagOut / SeriesOut）。
 */

export type TagCategory = 'genre' | 'theme' | 'feature'

export interface Actor {
  id: string
  name: string
  name_ja: string | null
  aliases: unknown
  photo_path: string | null
  birth_date: string | null
  measurements: string | null
  cup_size: string | null
  height: number | null
  nationality: string | null
  video_count: number
  created_at: string | null
  updated_at: string | null
}

export interface Tag {
  id: string
  name: string
  name_ja: string | null
  category: TagCategory
  video_count?: number
  created_at?: string | null
}

export interface Series {
  id: string
  name: string
  name_ja: string | null
  description: string | null
  poster_path: string | null
  video_count: number
  created_at: string | null
  updated_at: string | null
}

export interface Studio {
  name: string
  video_count: number
}
