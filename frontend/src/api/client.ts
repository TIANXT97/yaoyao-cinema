/**
 * 夭夭影社 · 基础 HTTP 客户端
 *
 * 统一封装 fetch：JSON 编解码、查询串构建、超时、AbortSignal、错误规整。
 * 基础路径默认为同源 `/api`（开发环境由 Vite 代理，生产由 FastAPI 伺服）。
 */

import type { ApiErrorPayload, QueryParams } from '@/types/api'
import { isCapacitorNative } from '@/utils/platform'

/** localStorage 中持久化的自定义 API 基址键名。 */
export const API_BASE_STORAGE_KEY = 'yaoyao.apiBase'

/** 局域网 NAS 默认标准网关（移动端/原生容器免配置开箱即用兜底）。 */
export const DEFAULT_LAN_API_BASE = 'http://192.168.31.235:9900/api'

/** 规范化基址：去空白、去尾部斜杠,绝对地址缺 /api 时自动补全；空串视为未配置。 */
function normalizeBase(value: string | null | undefined): string {
  const raw = value?.trim().replace(/\/+$/, '')
  if (!raw) return ''
  if (!/^https?:\/\//i.test(raw) || /\/api$/i.test(raw)) return raw
  return `${raw}/api`
}

/** 环境变量注入的兜底基址（构建期注入一次）。 */
const ENV_BASE = normalizeBase(import.meta.env.VITE_API_BASE)

let cachedApiBase: string | null = null

/**
 * 解析 API 基址，优先级：
 * 1. ``localStorage['yaoyao.apiBase']``（用户在设置页填写，适配安卓 / 跨设备）；
 * 2. ``import.meta.env.VITE_API_BASE``（构建期注入）；
 * 3. Capacitor 原生移动容器环境下兜底回退内网直连 ``http://192.168.31.235:9900/api``；
 * 4. 普通浏览器环境同源相对路径 ``/api``。
 */
export function resolveApiBase(): string {
  if (cachedApiBase !== null) return cachedApiBase

  let stored: string | null = null
  if (typeof window !== 'undefined') {
    try {
      stored = window.localStorage.getItem(API_BASE_STORAGE_KEY)
    } catch {
      stored = null
    }
  }

  const explicit = normalizeBase(stored) || ENV_BASE
  if (explicit) {
    cachedApiBase = explicit
    return cachedApiBase
  }

  // Capacitor 原生移动容器首屏兜底：防止请求打向本地 http://localhost 导致空白
  if (isCapacitorNative()) {
    cachedApiBase = DEFAULT_LAN_API_BASE
    return cachedApiBase
  }

  cachedApiBase = '/api'
  return cachedApiBase
}

/**
 * 设置 / 清除自定义 API 基址并持久化。
 * 传入空串或 null 时回退到环境变量 / 相对路径。
 */
export function setApiBase(value: string | null | undefined): string {
  const normalized = normalizeBase(value)
  if (typeof window !== 'undefined') {
    try {
      if (normalized) {
        window.localStorage.setItem(API_BASE_STORAGE_KEY, normalized)
      } else {
        window.localStorage.removeItem(API_BASE_STORAGE_KEY)
      }
    } catch {
      // 隐私模式 / 配额异常时忽略，内存态仍然生效
    }
  }
  cachedApiBase = normalized || ENV_BASE || '/api'
  return cachedApiBase
}

/** 统一 API 错误。 */
export class ApiError extends Error {
  readonly status: number
  readonly payload: ApiErrorPayload | null

  constructor(status: number, message: string, payload: ApiErrorPayload | null = null) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.payload = payload
  }

  get isNotFound(): boolean {
    return this.status === 404
  }
}

export interface RequestOptions extends Omit<RequestInit, 'body'> {
  /** 查询参数（自动过滤 undefined / null / 空串）。 */
  query?: QueryParams
  /** 请求体（对象自动 JSON 序列化）。 */
  body?: unknown
  /** 超时毫秒数，默认 20000。 */
  timeout?: number
  /** 原始响应类型，默认 json。 */
  responseType?: 'json' | 'text' | 'blob'
}

/** 拼接完整 URL，附带查询串。 */
export function buildUrl(path: string, query?: QueryParams): string {
  const base = /^https?:\/\//i.test(path)
    ? path
    : `${resolveApiBase()}${path.startsWith('/') ? path : `/${path}`}`

  if (!query) return base

  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(query)) {
    if (value === undefined || value === null || value === '') continue
    search.append(key, String(value))
  }
  const qs = search.toString()
  return qs ? `${base}?${qs}` : base
}

function extractMessage(payload: ApiErrorPayload | null): string | null {
  if (!payload?.detail) return null
  if (typeof payload.detail === 'string') return payload.detail
  if (Array.isArray(payload.detail)) {
    const first = payload.detail[0]
    if (first && typeof first === 'object' && 'msg' in first && first.msg) {
      return String(first.msg)
    }
  }
  return null
}

/** 核心请求方法。 */
export async function request<T>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const { query, body, timeout = 20000, responseType = 'json', ...init } = options

  const controller = new AbortController()
  const timer = timeout > 0 ? setTimeout(() => controller.abort(), timeout) : null

  // 合并外部 signal（若提供）
  if (init.signal) {
    const external = init.signal
    if (external.aborted) controller.abort()
    else external.addEventListener('abort', () => controller.abort(), { once: true })
  }

  const headers = new Headers(init.headers)
  if (body !== undefined && !(body instanceof FormData)) {
    headers.set('Content-Type', 'application/json')
  }
  headers.set('Accept', 'application/json')

  const method = (init.method ?? 'GET').toUpperCase()
  const canHaveBody = !['GET', 'HEAD'].includes(method)
  const payload =
    body === undefined || body === null
      ? undefined
      : body instanceof FormData
        ? body
        : JSON.stringify(body)

  try {
    const response = await fetch(buildUrl(path, query), {
      ...init,
      method,
      headers,
      body: canHaveBody ? payload : undefined,
      signal: controller.signal,
      credentials: 'same-origin',
    })

    if (!response.ok) {
      let detail: ApiErrorPayload | null = null
      try {
        detail = (await response.json()) as ApiErrorPayload
      } catch {
        detail = null
      }
      const message =
        extractMessage(detail) ?? `请求失败（HTTP ${response.status}）`
      throw new ApiError(response.status, message, detail)
    }

    if (response.status === 204) return undefined as T
    if (responseType === 'text') return (await response.text()) as T
    if (responseType === 'blob') return (await response.blob()) as T

    const text = await response.text()
    if (!text) return undefined as T

    try {
      return JSON.parse(text) as T
    } catch {
      return text as unknown as T
    }
  } catch (error) {
    if (error instanceof ApiError) throw error
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new ApiError(408, '请求超时，请检查网络或后端服务')
    }
    throw new ApiError(0, '网络连接异常，无法访问服务器')
  } finally {
    if (timer) clearTimeout(timer)
  }
}

/** HTTP 语法糖。 */
export const http = {
  get: <T>(path: string, options?: RequestOptions) =>
    request<T>(path, { ...options, method: 'GET' }),
  post: <T>(path: string, body?: unknown, options?: RequestOptions) =>
    request<T>(path, { ...options, method: 'POST', body }),
  put: <T>(path: string, body?: unknown, options?: RequestOptions) =>
    request<T>(path, { ...options, method: 'PUT', body }),
  patch: <T>(path: string, body?: unknown, options?: RequestOptions) =>
    request<T>(path, { ...options, method: 'PATCH', body }),
  delete: <T>(path: string, options?: RequestOptions) =>
    request<T>(path, { ...options, method: 'DELETE' }),
}

/** API 基础路径（实时解析，支持运行时切换）。 */
export function apiBase(): string {
  return resolveApiBase()
}

/** 将 MEDIA_ROOT 相对路径安全编码为图片 URL。 */
export function mediaUrl(path: string | null | undefined): string {
  if (!path) return ''
  if (/^https?:\/\//i.test(path)) return path
  const encoded = path
    .replace(/^\/+/, '')
    .split('/')
    .map((segment) => encodeURIComponent(segment))
    .join('/')
  return buildUrl(`/images/${encoded}`)
}

/** 视频流 URL（HTTP 206 Partial Content）。 */
export function streamUrl(videoId: string): string {
  return buildUrl(`/stream/${encodeURIComponent(videoId)}`)
}
