/**
 * 通用 API 响应类型（对齐 server/models.py）。
 */

/** 分页信封（`Pagination`）。 */
export interface Pagination {
  page: number
  per_page: number
  total: number
  total_pages: number
}

/** 列表信封（`VideoListResponse` / `Paginated[T]`）。 */
export interface Paginated<T> {
  items: T[]
  pagination: Pagination
}

/** 通用消息响应（`MessageResponse`）。 */
export interface MessageResponse {
  success: boolean
  message: string
}

/** 健康检查（`HealthResponse`）。 */
export interface HealthResponse {
  status: string
  database: string
  version: string
}

/** FastAPI 错误体。 */
export interface ApiErrorPayload {
  detail?: string | { msg?: string; type?: string }[]
}

export type QueryValue = string | number | boolean | null | undefined

export type QueryParams = Record<string, QueryValue>
