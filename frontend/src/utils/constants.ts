/**
 * 前端常量。
 */

import type { SortField, SortOrder } from '@/types/video'

export const APP_NAME = '夭夭影社'
export const APP_TAGLINE = '主人 TIAN 的私家影院'

/** 默认分页大小（对齐后端 DEFAULT_PER_PAGE）。 */
export const DEFAULT_PER_PAGE = 30
export const MAX_PER_PAGE = 100

/** 播放器：双击快进步长（秒）。 */
export const SEEK_STEP = 10

/** 播放器：进度自动上报间隔（毫秒）。 */
export const PROGRESS_REPORT_INTERVAL = 10_000

/** 播放器：控件自动隐藏延时（毫秒）。 */
export const CONTROLS_HIDE_DELAY = 4_000

/** 搜索防抖延时（毫秒）。 */
export const SEARCH_DEBOUNCE = 300

/** 倍速选项。 */
export const PLAYBACK_RATES = [0.5, 0.75, 1, 1.25, 1.5, 2] as const

/** 排序选项（对齐后端白名单）。 */
export const SORT_OPTIONS: { value: SortField; label: string }[] = [
  { value: 'date_added', label: '入库时间' },
  { value: 'release_date', label: '发行日期' },
  { value: 'play_count', label: '播放次数' },
  { value: 'last_played', label: '最近观看' },
  { value: 'rating', label: '评分' },
  { value: 'title', label: '标题' },
  { value: 'file_size', label: '文件大小' },
]

export const ORDER_OPTIONS: { value: SortOrder; label: string }[] = [
  { value: 'desc', label: '降序' },
  { value: 'asc', label: '升序' },
]

/** 刮削状态中文名。 */
export const SCRAPE_STATUS_LABEL: Record<string, string> = {
  pending: '待刮削',
  matched: '已匹配',
  failed: '刮削失败',
  manual: '手动录入',
}

/** 底部导航（对齐 ARCHITECTURE.md 3.2.1 路由）。 */
export interface TabItem {
  name: string
  label: string
  icon: 'home' | 'library' | 'favorite' | 'history' | 'settings'
}

export const TAB_ITEMS: TabItem[] = [
  { name: 'Home', label: '首页', icon: 'home' },
  { name: 'Library', label: '片库', icon: 'library' },
  { name: 'Favorites', label: '收藏', icon: 'favorite' },
  { name: 'History', label: '历史', icon: 'history' },
  { name: 'Settings', label: '设置', icon: 'settings' },
]
