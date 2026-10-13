<script setup lang="ts">
/**
 * SettingsView —— 媒体库扫描与刮削控制台。
 */
import {
  AlertCircle,
  Check,
  Database,
  FolderOpen,
  RefreshCw,
  RotateCcw,
  ScanLine,
  Server,
  Sparkles,
  Download,
  ExternalLink,
  ArrowUpCircle,
} from 'lucide-vue-next'
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

import { apiBase, setApiBase } from '@/api/client'
import {
  checkForUpdate,
  CURRENT_APP_VERSION,
  type AppReleaseInfo,
} from '@/services/updateService'
import {
  getScraperStatus,
  scrapeAll,
  triggerScan,
  type ScanResult,
  type ScraperStatus,
} from '@/api/scraper'
import { getSystemStats, type SystemStats } from '@/api/system'
import PageHeader from '@/components/layout/PageHeader.vue'
import { formatDateTime, formatFileSize } from '@/utils/format'

const stats = ref<SystemStats | null>(null)
const status = ref<ScraperStatus | null>(null)
const scanning = ref(false)
const scraping = ref(false)
const notice = ref<string | null>(null)
const error = ref<string | null>(null)

// NAS 服务器地址（API 基址）设置
const apiBaseInput = ref(apiBase())
const apiBaseSaved = ref(false)
let apiBaseTimer: ReturnType<typeof setTimeout> | null = null

function flashApiBaseSaved(): void {
  apiBaseSaved.value = true
  if (apiBaseTimer) clearTimeout(apiBaseTimer)
  apiBaseTimer = setTimeout(() => {
    apiBaseSaved.value = false
  }, 2000)
}

function onSaveApiBase(): void {
  const normalized = setApiBase(apiBaseInput.value)
  apiBaseInput.value = normalized
  error.value = null
  notice.value = `API 基址已更新为 ${normalized}`
  flashApiBaseSaved()
}

function onResetApiBase(): void {
  const normalized = setApiBase('')
  apiBaseInput.value = normalized
  error.value = null
  notice.value = `API 基址已重置为默认（${normalized}）`
  flashApiBaseSaved()
}

// 应用更新检测
const checkingUpdate = ref(false)
const releaseInfo = ref<AppReleaseInfo | null>(null)
const updateChecked = ref(false)

async function onCheckUpdate(): Promise<void> {
  if (checkingUpdate.value) return
  checkingUpdate.value = true
  error.value = null
  try {
    const info = await checkForUpdate(CURRENT_APP_VERSION)
    releaseInfo.value = info
    updateChecked.value = true
    if (!info.hasUpdate) {
      notice.value = `当前已是最新版本（v${CURRENT_APP_VERSION}）`
    }
  } catch (err) {
    error.value = describeError(err, '检测更新失败，请检查网络连接')
  } finally {
    checkingUpdate.value = false
  }
}

let pollTimer: ReturnType<typeof setInterval> | null = null

function describeError(err: unknown, fallback: string): string {
  return err instanceof Error ? err.message : fallback
}

const metrics = computed(() => {
  const videos = stats.value?.videos
  return [
    { label: '影片总数', value: String(videos?.total ?? 0), suffix: '部' },
    { label: '占用空间', value: formatFileSize(videos?.total_size ?? 0), suffix: '' },
    { label: '私房收藏', value: String(videos?.favorites ?? 0), suffix: '部' },
    { label: '已观看', value: String(videos?.watched ?? 0), suffix: '部' },
  ]
})

const scrapeProgress = computed(() => {
  const videos = stats.value?.videos
  const total = videos?.total ?? 0
  const matched = videos?.matched ?? 0
  return total > 0 ? Math.round((matched / total) * 100) : 0
})

const pipelineRunning = computed(() => status.value?.pipeline?.running === true)
const pipelinePercent = computed(() => {
  const pipeline = status.value?.pipeline
  if (!pipeline || !pipeline.total) return 0
  return Math.min(100, Math.round((pipeline.processed / pipeline.total) * 100))
})

async function refreshStats(): Promise<void> {
  try {
    stats.value = await getSystemStats()
  } catch (err) {
    error.value = describeError(err, '系统统计加载失败')
  }
}

async function refreshStatus(): Promise<void> {
  try {
    status.value = await getScraperStatus()
  } catch {
    // 状态轮询失败静默处理
  }
}

async function refreshAll(): Promise<void> {
  await Promise.all([refreshStats(), refreshStatus()])
}

async function onScan(): Promise<void> {
  if (scanning.value) return
  scanning.value = true
  notice.value = null
  error.value = null
  try {
    const result: ScanResult = await triggerScan()
    notice.value = `扫描完成 · 发现 ${result.discovered} 个文件，新增 ${result.added} 部，跳过 ${result.skipped} 部`
    await refreshAll()
  } catch (err) {
    error.value = describeError(err, '媒体库扫描失败')
  } finally {
    scanning.value = false
  }
}

async function onScrapeAll(): Promise<void> {
  if (scraping.value) return
  scraping.value = true
  notice.value = null
  error.value = null
  try {
    const result = await scrapeAll()
    notice.value = result.reason
      ? String(result.reason)
      : result.started
        ? '批量刮削任务已启动，进度将自动刷新'
        : '刮削任务启动失败'
    await refreshAll()
  } catch (err) {
    error.value = describeError(err, '批量刮削启动失败')
  } finally {
    scraping.value = false
  }
}

onMounted(() => {
  void refreshAll()
  pollTimer = setInterval(() => {
    if (pipelineRunning.value) void refreshStatus()
  }, 4000)
})

onBeforeUnmount(() => {
  if (pollTimer) clearInterval(pollTimer)
  if (apiBaseTimer) clearTimeout(apiBaseTimer)
})
</script>

<template>
  <div>
    <PageHeader title="设置" subtitle="媒体库扫描 · 刮削控制台 · 系统状态" bordered>
      <template #actions>
        <button
          type="button"
          class="flex h-8 w-8 items-center justify-center rounded-full text-ink-faint transition-colors duration-150 ease-yy hover:bg-paper-mute hover:text-ink"
          aria-label="刷新"
          @click="refreshAll"
        >
          <RefreshCw :size="16" :stroke-width="1.5" />
        </button>
      </template>
    </PageHeader>

    <section class="mx-auto max-w-5xl px-4 pt-8 pb-16 sm:px-6">
      <!-- 统计 -->
      <div class="grid grid-cols-2 gap-px overflow-hidden rounded-xl border border-line bg-line sm:grid-cols-4">
        <div v-for="metric in metrics" :key="metric.label" class="bg-paper px-5 py-6">
          <p class="text-[11px] tracking-bangou text-ink-faint">{{ metric.label }}</p>
          <p class="mt-2 font-serif text-2xl text-ink">
            {{ metric.value }}
            <span v-if="metric.suffix" class="ml-1 text-xs text-ink-faint">{{ metric.suffix }}</span>
          </p>
        </div>
      </div>

      <!-- 提示 -->
      <div
        v-if="notice"
        class="mt-5 flex items-start gap-2 rounded-lg border border-accent/30 bg-accent/5 px-4 py-3 text-xs text-ink-soft"
      >
        <Check :size="14" :stroke-width="1.5" class="mt-0.5 shrink-0 text-accent" />
        <span>{{ notice }}</span>
      </div>
      <div
        v-if="error"
        class="mt-5 flex items-start gap-2 rounded-lg border border-red-200 bg-red-50/60 px-4 py-3 text-xs text-red-500"
      >
        <AlertCircle :size="14" :stroke-width="1.5" class="mt-0.5 shrink-0" />
        <span>{{ error }}</span>
      </div>

      <!-- 操作 -->
      <div class="mt-8 rounded-xl border border-line p-6">
        <h2 class="text-sm text-ink">媒体库操作</h2>
        <p class="mt-1.5 text-xs leading-relaxed text-ink-faint">
          扫描会深度遍历媒体根目录并登记新文件；刮削将按番号级联网络数据源，
          补全封面、演员与标签。
        </p>

        <div class="mt-5 flex flex-wrap gap-3">
          <button
            type="button"
            class="inline-flex items-center gap-2 rounded-full border border-line px-5 py-2.5 text-sm text-ink-soft transition-colors duration-150 ease-yy hover:border-accent/50 hover:text-ink disabled:opacity-50"
            :disabled="scanning"
            @click="onScan"
          >
            <ScanLine :size="16" :stroke-width="1.5" :class="scanning ? 'animate-pulse' : ''" />
            {{ scanning ? '扫描中…' : '扫描媒体库' }}
          </button>

          <button
            type="button"
            class="inline-flex items-center gap-2 rounded-full border border-line px-5 py-2.5 text-sm text-ink-soft transition-colors duration-150 ease-yy hover:border-accent/50 hover:text-ink disabled:opacity-50"
            :disabled="scraping || pipelineRunning"
            @click="onScrapeAll"
          >
            <Sparkles :size="16" :stroke-width="1.5" :class="scraping ? 'animate-pulse' : ''" />
            {{ pipelineRunning ? '刮削进行中…' : '批量刮削待处理' }}
          </button>
        </div>

        <!-- 刮削总进度 -->
        <div class="mt-6">
          <div class="flex items-center justify-between text-[11px] text-ink-faint">
            <span>刮削完成度</span>
            <span class="font-mono">{{ scrapeProgress }}%</span>
          </div>
          <div class="mt-2 h-[3px] w-full overflow-hidden rounded-full bg-paper-mute">
            <div
              class="h-full rounded-full bg-accent transition-[width] duration-500 ease-yy"
              :style="{ width: `${scrapeProgress}%` }"
            />
          </div>
          <div class="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-[11px] text-ink-faint">
            <span>已匹配 {{ stats?.videos?.matched ?? 0 }}</span>
            <span>待刮削 {{ stats?.videos?.pending ?? 0 }}</span>
            <span>失败 {{ stats?.videos?.failed ?? 0 }}</span>
            <span>手动 {{ stats?.videos?.manual ?? 0 }}</span>
          </div>
        </div>

        <!-- 批量任务实时状态 -->
        <div
          v-if="pipelineRunning"
          class="mt-5 rounded-lg bg-paper-soft px-4 py-3 text-[11px] text-ink-soft"
        >
          <div class="flex items-center justify-between">
            <span>批量刮削进行中</span>
            <span class="font-mono">{{ pipelinePercent }}%</span>
          </div>
          <div class="mt-2 h-[3px] w-full overflow-hidden rounded-full bg-paper-mute">
            <div
              class="h-full rounded-full bg-ink/60 transition-[width] duration-500 ease-yy"
              :style="{ width: `${pipelinePercent}%` }"
            />
          </div>
          <p class="mt-2">
            已处理 {{ status?.pipeline?.processed ?? 0 }} / {{ status?.pipeline?.total ?? 0 }}
            · 成功 {{ status?.pipeline?.matched ?? 0 }} · 失败
            {{ status?.pipeline?.failed ?? 0 }}
          </p>
        </div>
      </div>

      <!-- 路径信息 -->
      <div class="mt-6 rounded-xl border border-line p-6">
        <h2 class="text-sm text-ink">存储与数据</h2>
        <div class="mt-4 space-y-3 text-xs">
          <div class="flex items-start gap-3">
            <FolderOpen :size="15" :stroke-width="1.5" class="mt-0.5 shrink-0 text-ink-mute" />
            <div class="min-w-0">
              <p class="text-ink-faint">媒体根目录</p>
              <p class="mt-0.5 break-all font-mono text-ink-soft">
                {{ stats?.media_root ?? '—' }}
              </p>
            </div>
          </div>
          <div class="flex items-start gap-3">
            <Database :size="15" :stroke-width="1.5" class="mt-0.5 shrink-0 text-ink-mute" />
            <div class="min-w-0">
              <p class="text-ink-faint">数据库</p>
              <p class="mt-0.5 break-all font-mono text-ink-soft">
                {{ stats?.database_path ?? '—' }}
              </p>
            </div>
          </div>
        </div>

        <div class="mt-5 grid grid-cols-3 gap-4 border-t border-line pt-5 text-xs">
          <div>
            <p class="text-ink-faint">演员</p>
            <p class="mt-1 text-ink">{{ stats?.actors ?? 0 }}</p>
          </div>
          <div>
            <p class="text-ink-faint">标签</p>
            <p class="mt-1 text-ink">{{ stats?.tags ?? 0 }}</p>
          </div>
          <div>
            <p class="text-ink-faint">系列</p>
            <p class="mt-1 text-ink">{{ stats?.series ?? 0 }}</p>
          </div>
        </div>
      </div>

      <!-- NAS 服务器地址 -->
      <div class="mt-6 rounded-xl border border-line p-6">
        <h2 class="text-sm text-ink">NAS 服务器地址</h2>
        <p class="mt-1.5 text-xs leading-relaxed text-ink-faint">
          安卓 App 或跨设备访问时，请填写 NAS 的完整 API 基址（例如
          <span class="font-mono text-ink-soft">http://192.168.31.235:9900/api</span>）。
          PWA 同源部署可留空，默认使用相对路径
          <span class="font-mono text-ink-soft">/api</span>。修改后立即生效并永久保存。
        </p>
        <div class="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center">
          <div class="relative flex-1">
            <Server
              :size="15"
              :stroke-width="1.5"
              class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-mute"
            />
            <input
              v-model="apiBaseInput"
              type="url"
              inputmode="url"
              autocomplete="off"
              spellcheck="false"
              placeholder="http://192.168.31.235:9900/api"
              class="w-full rounded-lg border border-line bg-paper py-2.5 pr-3 pl-9 font-mono text-xs text-ink transition-colors duration-150 ease-yy placeholder:text-ink-mute focus:border-accent focus:outline-none"
              @keyup.enter="onSaveApiBase"
            />
          </div>
          <div class="flex items-center gap-2">
            <button
              type="button"
              class="inline-flex items-center gap-2 rounded-full border border-line px-5 py-2.5 text-sm text-ink-soft transition-colors duration-150 ease-yy hover:border-accent/50 hover:text-ink"
              @click="onSaveApiBase"
            >
              <Check v-if="apiBaseSaved" :size="16" :stroke-width="1.6" class="text-accent" />
              <Server v-else :size="16" :stroke-width="1.5" />
              保存
            </button>
            <button
              type="button"
              class="inline-flex items-center gap-2 rounded-full border border-line px-4 py-2.5 text-sm text-ink-faint transition-colors duration-150 ease-yy hover:border-accent/50 hover:text-ink"
              @click="onResetApiBase"
            >
              <RotateCcw :size="15" :stroke-width="1.5" />
              重置
            </button>
          </div>
        </div>
      </div>

      <!-- 版本与更新 -->
      <div class="mt-6 rounded-xl border border-line p-6">
        <div class="flex items-center justify-between">
          <div>
            <h2 class="text-sm text-ink">版本与更新</h2>
            <p class="mt-1 text-xs text-ink-faint">
              当前版本：<span class="font-mono font-medium text-ink">v{{ CURRENT_APP_VERSION }}</span>
            </p>
          </div>
          <button
            type="button"
            class="inline-flex items-center gap-2 rounded-full border border-line px-4 py-2 text-xs text-ink-soft transition-colors duration-150 ease-yy hover:border-accent/50 hover:text-ink disabled:opacity-50"
            :disabled="checkingUpdate"
            @click="onCheckUpdate"
          >
            <RefreshCw :size="14" :stroke-width="1.5" :class="checkingUpdate ? 'animate-spin' : ''" />
            {{ checkingUpdate ? '检查中…' : '检查更新' }}
          </button>
        </div>

        <!-- 发现新版本卡片 -->
        <div
          v-if="releaseInfo?.hasUpdate"
          class="mt-4 rounded-xl border border-accent/40 bg-accent/[0.03] p-4 text-xs"
        >
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-2 font-medium text-accent">
              <ArrowUpCircle :size="16" :stroke-width="1.8" />
              <span>发现新版本 {{ releaseInfo.tagName }}</span>
            </div>
            <span v-if="releaseInfo.apkAsset?.size" class="font-mono text-[11px] text-ink-faint">
              {{ formatFileSize(releaseInfo.apkAsset.size) }}
            </span>
          </div>

          <div
            v-if="releaseInfo.body"
            class="mt-2.5 max-h-36 overflow-y-auto whitespace-pre-wrap rounded-lg bg-paper-mute/50 p-2.5 font-mono text-[11px] leading-relaxed text-ink-soft"
          >
            {{ releaseInfo.body }}
          </div>

          <div class="mt-4 flex flex-wrap items-center gap-2.5">
            <a
              v-if="releaseInfo.apkAsset"
              :href="releaseInfo.apkAsset.acceleratedUrl"
              target="_blank"
              download
              class="inline-flex items-center gap-1.5 rounded-full bg-ink px-4 py-2 text-xs font-medium text-paper transition-opacity hover:opacity-90"
            >
              <Download :size="13" :stroke-width="2" />
              立即下载更新 (高速镜像)
            </a>
            <a
              v-if="releaseInfo.apkAsset"
              :href="releaseInfo.apkAsset.downloadUrl"
              target="_blank"
              download
              class="inline-flex items-center gap-1.5 rounded-full border border-line px-3.5 py-2 text-xs text-ink-soft hover:border-accent/40 hover:text-ink"
            >
              <ExternalLink :size="13" :stroke-width="1.5" />
              官方源
            </a>
          </div>
        </div>

        <div
          v-else-if="updateChecked && !releaseInfo?.hasUpdate"
          class="mt-3 flex items-center gap-2 text-xs text-ink-mute"
        >
          <Check :size="14" :stroke-width="1.8" class="text-accent" />
          <span>已是最新版本，无需更新。</span>
        </div>
      </div>

      <!-- 关于 -->
      <div class="mt-6 rounded-xl border border-line p-6">
        <h2 class="text-sm text-ink">关于</h2>
        <p class="mt-2 text-xs leading-relaxed text-ink-faint">
          夭夭影社（Yaoyao Cinema）· 专为主人 TIAN 量身定制的私家影院系统。<br />
          全链路 Direct Play 原画直出，东方纯白极简通透美学。
        </p>
        <p class="mt-4 font-mono text-[11px] tracking-bangou text-ink-mute">
          最近扫描：{{ formatDateTime(status?.finished_at ?? null) }}
        </p>
      </div>
    </section>
  </div>
</template>
