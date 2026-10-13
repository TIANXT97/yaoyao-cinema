import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { getScraperStatus } from '@/api/scraper'
import { getSystemStats } from '@/api/system'
import SettingsView from '@/views/SettingsView.vue'

vi.mock('@/api/client', () => ({
  apiBase: () => '/api',
  setApiBase: (value: string) => value,
}))
vi.mock('@/api/system', () => ({ getSystemStats: vi.fn() }))
vi.mock('@/api/scraper', () => ({
  getScraperStatus: vi.fn(),
  scrapeAll: vi.fn(),
  triggerScan: vi.fn(),
}))
vi.mock('@/services/updateService', () => ({
  CURRENT_APP_VERSION: '1.0.3',
  checkForUpdate: vi.fn(),
}))

const SPA_FALLBACK_HTML = '<!doctype html><html><body></body></html>' as never

function mountSettings() {
  return mount(SettingsView, { global: { stubs: { PageHeader: true } } })
}

describe('SettingsView 渲染防御', () => {
  let wrapper: ReturnType<typeof mountSettings> | undefined

  afterEach(() => {
    wrapper?.unmount()
    wrapper = undefined
  })

  it('统计为 null 时显示默认值 0', async () => {
    vi.mocked(getSystemStats).mockResolvedValue(null as never)
    vi.mocked(getScraperStatus).mockResolvedValue(null as never)
    wrapper = mountSettings()
    await flushPromises()
    expect(wrapper.text()).toContain('已匹配 0')
  })

  it('接口返回 HTML 回退页(API 基址缺少 /api)时不崩溃', async () => {
    vi.mocked(getSystemStats).mockResolvedValue(SPA_FALLBACK_HTML)
    vi.mocked(getScraperStatus).mockResolvedValue(SPA_FALLBACK_HTML)
    wrapper = mountSettings()
    await flushPromises()
    expect(wrapper.text()).toContain('已匹配 0')
    expect(wrapper.text()).toContain('失败 0')
  })
})
