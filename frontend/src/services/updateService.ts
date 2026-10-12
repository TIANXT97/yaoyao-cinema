/**
 * 夭夭影社 · 应用更新服务 (对齐 GitHub Releases API)。
 *
 * 手机端直接请求公开仓库 GitHub API 获取最新版本信息与 APK 下载直链。
 * 提供官方 GitHub Releases CDN 与国内镜像加速源（ghfast.top），保障手机快速直连更新。
 */

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

export const GITHUB_REPO = 'TIANXT97/yaoyao-cinema'
export const CURRENT_APP_VERSION = '1.0.3'

/**
 * 语义化版本号比较。
 * 若 v1 > v2 返回 1；v1 < v2 返回 -1；相等返回 0。
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

/**
 * 检查 GitHub Releases 最新版本。
 */
export async function checkForUpdate(currentVersion = CURRENT_APP_VERSION): Promise<AppReleaseInfo> {
  const url = `https://api.github.com/repos/${GITHUB_REPO}/releases/latest`

  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), 8000)

  try {
    const res = await fetch(url, {
      signal: controller.signal,
      headers: {
        Accept: 'application/vnd.github.v3+json',
      },
    })

    if (!res.ok) {
      throw new Error(`无法获取更新信息 (HTTP ${res.status})`)
    }

    const data = await res.json()
    const tagName = String(data.tag_name || '')
    const versionName = tagName.replace(/^v/i, '')
    const title = String(data.name || tagName)
    const body = String(data.body || '')
    const publishedAt = String(data.published_at || '')

    // 寻找 .apk 资源文件
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

    const hasUpdate = compareVersions(versionName, currentVersion) > 0

    return {
      tagName,
      versionName,
      title,
      body,
      publishedAt,
      hasUpdate,
      apkAsset,
    }
  } finally {
    clearTimeout(timeoutId)
  }
}
