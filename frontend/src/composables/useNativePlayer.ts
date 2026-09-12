/**
 * useNativePlayer —— 播放调度（PWA / 安卓原生）。
 *
 * 对齐 docs/ARCHITECTURE.md 4.2.4「前端调用桥接」：
 * - 安卓 Capacitor 环境 → 通过 registerPlugin('NativePlayer') 调起原生 Media3 硬解播放器
 * - PWA / 桌面浏览器 → 路由进入自研 HTML5 播放器
 *
 * 说明：原生播放器需要可直连的绝对 URL。请在为安卓打包时通过
 * `VITE_API_BASE=http://<NAS-IP>:9900/api` 注入 API 基址；PWA 场景保持同源相对路径。
 */

import { Capacitor, registerPlugin } from '@capacitor/core'
import { computed } from 'vue'
import { useRouter } from 'vue-router'

import { resolveApiBase, streamUrl } from '@/api/client'
import { reportProgress } from '@/api/history'
import { deviceLabel } from '@/utils/platform'

export interface NativePlayResult {
  position: number
  duration: number
  completed: boolean
  cancelled?: boolean
}

interface NativePlayerPlugin {
  play(options: {
    url: string
    position?: number
    title?: string
  }): Promise<NativePlayResult>
}

const NativePlayer = registerPlugin<NativePlayerPlugin>('NativePlayer')

/**
 * 将流地址规整为原生可加载的绝对 URL。
 *
 * ``streamUrl`` 已按当前 API 基址拼接：若设置页配置了绝对 NAS 地址
 * （如 ``http://192.168.31.235:9900/api``），结果天然是完整绝对 URL，
 * ExoPlayer 可直接直连；仅当尚未配置时才退回页面 origin（Web/PWA 场景）。
 */
function absoluteStreamUrl(videoId: string): string {
  const url = streamUrl(videoId)
  if (/^https?:\/\//i.test(url)) return url
  const base = resolveApiBase()
  if (/^https?:\/\//i.test(base)) {
    const normalized = base.endsWith('/') ? base : `${base}/`
    return new URL(url.replace(/^\/+/, ''), normalized).toString()
  }
  return new URL(url, window.location.origin).toString()
}

/** 原生播放结束后回传毫秒进度（与 Web 播放器单位统一）。 */
async function reportNativeProgress(
  videoId: string,
  result: NativePlayResult,
): Promise<void> {
  const duration = Math.max(0, Math.round(result.duration ?? 0))
  const position = Math.max(0, Math.round(result.position ?? 0))
  if (duration <= 0 && position <= 0) return
  try {
    await reportProgress({
      video_id: videoId,
      position,
      duration,
      device: deviceLabel(),
    })
  } catch {
    // 进度上报失败不阻断播放
  }
}

export function useNativePlayer() {
  const router = useRouter()
  const isNative = computed(() => Capacitor.isNativePlatform())

  /** 播放影片：原生硬解优先，否则跳转内置 HTML5 播放器页。 */
  async function playVideo(
    videoId: string,
    options: { title?: string; resumeMs?: number } = {},
  ): Promise<void> {
    if (isNative.value) {
      try {
        const result = await NativePlayer.play({
          url: absoluteStreamUrl(videoId),
          position: Math.max(0, Math.round(options.resumeMs ?? 0)),
          title: options.title ?? '',
        })
        // 成功或用户主动取消都在原生侧闭环，不再跳转 Web 播放器
        if (!result.cancelled) {
          await reportNativeProgress(videoId, result)
        }
        return
      } catch {
        // 原生桥接失败时静默回退到 Web 播放器，保证可用性
      }
    }

    await router.push({ name: 'Player', params: { id: videoId } })
  }

  return { isNative, playVideo }
}
