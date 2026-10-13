/**
 * 夭夭影社 · 应用更新服务。
 *
 * 优先请求自家服务端 ``/api/system/check-update``(带内存缓存,规避 GitHub 匿名限流),
 * 服务端不可达时回退到客户端直连 GitHub Releases API。
 */
import { apiBase } from '@/api/client'

export interface ReleaseAsset {
  name: string
  size: number
  downloadUrl: string
  acceleratedUrl: string
}

export interface AppReleaseInfo {
  tagName: string
  versionName: string
  title: string
  body: string
  publishedAt: string
  hasUpdate: boolean
  apkAsset?: ReleaseAsset
}

interface NormalizedRelease {
  tagName: string
  versionName: string
  title: string
  body: string
  publishedAt: string
  apkAsset?: ReleaseAsset | null
}

export const GITHUB_REPO = 'TIANXT97/yaoyao-cinema'
export const CURRENT_APP_VERSION: string = __APP_VERSION__

const TIMEOUT_MS = 8000

/**
 * 语义化版本号比较。
 * 若 v1 > v2 返回 1;v1 < v2 返回 -1;相等返回 0。
 */
export function compareVersions(v1: string, v2: string): number {
  const clean1 = v1.replace(/^[^\d]*/, '').trim()
  const clean2 = v2.replace(/^[^\d]*/, '').trim()

  const parts1 = clean1.split('.').map((p) => parseInt(p, 10) || 0)
  const parts2 = clean2.split('.').map((p) => parseInt(p, 10) || 0)

  const maxLen = Math.max(parts1.length, parts2.length)
  for (let i = 0; i < maxLen; i++) {
    const num1 = parts1[i] ?? 0
    const num2 = parts2[i] ?? 0
    if (num1 > num2) return 1
    if (num1 < num2) return -1
  }
  return 0
}

function withTimeout(): { signal: AbortSignal; clear: () => void } {
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), TIMEOUT_MS)
  return { signal: controller.signal, clear: () => clearTimeout(timeoutId) }
}

async function fetchFromServer(): Promise<NormalizedRelease> {
  const { signal, clear } = withTimeout()
  try {
    const res = await fetch(`${apiBase()}/system/check-update`, { signal })
    if (!res.ok) {
      throw new Error(`服务端检查更新失败 (HTTP ${res.status})`)
    }
    return (await res.json()) as NormalizedRelease
  } finally {
    clear()
  }
}

async function fetchFromGithub(): Promise<NormalizedRelease> {
  const url = `https://api.github.com/repos/${GITHUB_REPO}/releases/latest`
  const { signal, clear } = withTimeout()
  try {
    const res = await fetch(url, {
      signal,
      headers: { Accept: 'application/vnd.github.v3+json' },
    })
    if (!res.ok) {
      throw new Error(`无法获取更新信息 (HTTP ${res.status})`)
    }
    const data = await res.json()
    const tagName = String(data.tag_name || '')
    let apkAsset: ReleaseAsset | undefined
    if (Array.isArray(data.assets)) {
      const found = data.assets.find(
        (a: { name?: string }) => typeof a?.name === 'string' && a.name.toLowerCase().endsWith('.apk'),
      )
      if (found) {
        const rawUrl = String(found.browser_download_url || '')
        apkAsset = {
          name: String(found.name),
          size: Number(found.size) || 0,
          downloadUrl: rawUrl,
          acceleratedUrl: `https://ghfast.top/${rawUrl}`,
        }
      }
    }
    return {
      tagName,
      versionName: tagName.replace(/^v/i, ''),
      title: String(data.name || tagName),
      body: String(data.body || ''),
      publishedAt: String(data.published_at || ''),
      apkAsset,
    }
  } finally {
    clear()
  }
}

/**
 * 检查最新版本:服务端代理优先,失败回退 GitHub 直连。
 */
export async function checkForUpdate(currentVersion = CURRENT_APP_VERSION): Promise<AppReleaseInfo> {
  let release: NormalizedRelease
  try {
    release = await fetchFromServer()
  } catch {
    release = await fetchFromGithub()
  }
  return {
    tagName: release.tagName,
    versionName: release.versionName,
    title: release.title,
    body: release.body,
    publishedAt: release.publishedAt,
    hasUpdate: compareVersions(release.versionName, currentVersion) > 0,
    apkAsset: release.apkAsset ?? undefined,
  }
}
