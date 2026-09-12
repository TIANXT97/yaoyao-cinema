/**
 * useNativePlayer —— 播放调度（浏览器 / PWA）。
 *
 * 说明：安卓 Capacitor 原生硬解桥接属 Phase 6 范畴，此处仅保留统一入口，
 * 保证 PWA / 桌面浏览器经由路由进入自研 HTML5 播放器；
 * 若运行环境存在原生桥接（window.YaoyaoNative），则优先调用。
 */

import { computed } from 'vue'
import { useRouter } from 'vue-router'

export interface NativePlayResult {
  position: number
  duration: number
  completed: boolean
  cancelled?: boolean
}

interface NativeBridge {
  play: (options: {
    url: string
    position?: number
    title?: string
  }) => Promise<NativePlayResult>
}

function getBridge(): NativeBridge | null {
  if (typeof window === 'undefined') return null
  const candidate = (window as Window & { YaoyaoNative?: NativeBridge })
    .YaoyaoNative
  return candidate && typeof candidate.play === 'function' ? candidate : null
}

export function useNativePlayer() {
  const router = useRouter()
  const isNative = computed(() => getBridge() !== null)

  /** 播放影片：原生桥接优先，否则跳转内置播放器页。 */
  async function playVideo(
    videoId: string,
    options: { title?: string; resumeMs?: number } = {},
  ): Promise<void> {
    const bridge = getBridge()
    if (bridge) {
      try {
        await bridge.play({
          url: `${window.location.origin}/api/stream/${encodeURIComponent(videoId)}`,
          position: options.resumeMs ?? 0,
          title: options.title ?? '',
        })
        return
      } catch {
        // 原生调用失败时静默回退到 Web 播放器
      }
    }

    await router.push({ name: 'Player', params: { id: videoId } })
  }

  return { isNative, playVideo }
}
