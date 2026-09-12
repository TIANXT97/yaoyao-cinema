/**
 * 前端工具函数：时间、体积、日期、数值格式化。
 */

/** 秒 → `mm:ss` 或 `h:mm:ss`。 */
export function formatClock(seconds: number | null | undefined): string {
  const total = Math.max(0, Math.floor(Number(seconds) || 0))
  const h = Math.floor(total / 3600)
  const m = Math.floor((total % 3600) / 60)
  const s = total % 60
  const mm = h > 0 ? String(m).padStart(2, '0') : String(m)
  const ss = String(s).padStart(2, '0')
  return h > 0 ? `${h}:${mm}:${ss}` : `${mm}:${ss}`
}

/** 秒 → 中文时长「1 小时 23 分」。 */
export function formatDurationText(seconds: number | null | undefined): string {
  const total = Math.max(0, Math.floor(Number(seconds) || 0))
  if (!total) return '—'
  const h = Math.floor(total / 3600)
  const m = Math.round((total % 3600) / 60)
  if (h > 0) return m > 0 ? `${h} 小时 ${m} 分` : `${h} 小时`
  return `${m} 分钟`
}

/** 字节 → 人类可读体积。 */
export function formatFileSize(bytes: number | null | undefined): string {
  const value = Number(bytes) || 0
  if (value <= 0) return '—'
  const units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
  const exponent = Math.min(
    Math.floor(Math.log(value) / Math.log(1024)),
    units.length - 1,
  )
  const size = value / Math.pow(1024, exponent)
  const digits = exponent === 0 ? 0 : size >= 100 ? 0 : size >= 10 ? 1 : 2
  return `${size.toFixed(digits)} ${units[exponent]}`
}

/** 分辨率字符串 → 原画等级标签（4K / 1080P / 720P）。 */
export function resolutionBadge(resolution: string | null | undefined): string | null {
  if (!resolution) return null
  const normalized = resolution.toLowerCase().replace(/\s/g, '')
  if (/(2160|4k|3840)/.test(normalized)) return '4K'
  if (/(1440|2k|2560)/.test(normalized)) return '2K'
  if (/(1080|1920|fhd)/.test(normalized)) return '1080P'
  if (/(720|1280|hd)/.test(normalized)) return '720P'
  return resolution.toUpperCase()
}

function parseDate(value: string | null | undefined): Date | null {
  if (!value) return null
  const normalized = value.includes('T') ? value : value.replace(' ', 'T')
  const date = new Date(normalized)
  return Number.isNaN(date.getTime()) ? null : date
}

/** 日期 → `YYYY-MM-DD`。 */
export function formatDate(value: string | null | undefined): string {
  const date = parseDate(value)
  if (!date) return '—'
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const d = String(date.getDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
}

/** 日期 → `YYYY-MM-DD HH:mm`。 */
export function formatDateTime(value: string | null | undefined): string {
  const date = parseDate(value)
  if (!date) return '—'
  const hh = String(date.getHours()).padStart(2, '0')
  const mm = String(date.getMinutes()).padStart(2, '0')
  return `${formatDate(value)} ${hh}:${mm}`
}

/** 相对时间「刚刚 / 3 分钟前 / 昨天 / 07-12」。 */
export function formatRelativeTime(value: string | null | undefined): string {
  const date = parseDate(value)
  if (!date) return '—'
  const diff = Date.now() - date.getTime()
  if (diff < 0) return formatDate(value)
  const minute = 60 * 1000
  const hour = 60 * minute
  const day = 24 * hour

  if (diff < minute) return '刚刚'
  if (diff < hour) return `${Math.floor(diff / minute)} 分钟前`
  if (diff < day) return `${Math.floor(diff / hour)} 小时前`
  if (diff < 2 * day) return '昨天'
  if (diff < 7 * day) return `${Math.floor(diff / day)} 天前`

  const now = new Date()
  const md = `${String(date.getMonth() + 1).padStart(2, '0')}-${String(
    date.getDate(),
  ).padStart(2, '0')}`
  return date.getFullYear() === now.getFullYear()
    ? md
    : `${date.getFullYear()}-${md}`
}

/** 数值裁剪到 [min, max]。 */
export function clamp(value: number, min = 0, max = 1): number {
  return Math.min(max, Math.max(min, value))
}

/** 0~1 进度 → 百分比整数。 */
export function formatPercent(progress: number | null | undefined): string {
  return `${Math.round(clamp(Number(progress) || 0) * 100)}%`
}

/** 取番号显示文本（回退文件名）。 */
export function displayBangou(
  bangou: string | null | undefined,
  fileName?: string | null,
): string {
  if (bangou) return bangou
  if (fileName) return fileName.replace(/\.[^.]+$/, '')
  return '—'
}

/** 取标题显示文本。 */
export function displayTitle(title: string | null | undefined, fallback = '未命名影片'): string {
  const trimmed = (title ?? '').trim()
  return trimmed.length > 0 ? trimmed : fallback
}

/** 截断文本。 */
export function truncate(text: string, max: number): string {
  return text.length > max ? `${text.slice(0, max)}…` : text
}
