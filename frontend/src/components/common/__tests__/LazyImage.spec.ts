import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import LazyImage from '@/components/common/LazyImage.vue'

const POSTER = 'http://192.168.31.235:9900/api/poster/1'
const OTHER_POSTER = 'http://192.168.31.235:9900/api/poster/2'

describe('LazyImage 图片容错', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('加载失败后自动重试,超过次数后显示失败占位', async () => {
    const wrapper = mount(LazyImage, { props: { src: POSTER } })

    for (let i = 0; i < 2; i++) {
      await wrapper.find('img').trigger('error')
      vi.advanceTimersByTime(1000)
      await nextTick()
      expect(wrapper.find('img').exists()).toBe(true)
    }

    await wrapper.find('img').trigger('error')
    expect(wrapper.find('img').exists()).toBe(false)
    expect(wrapper.find('svg').exists()).toBe(true)
    wrapper.unmount()
  })

  it('更换 src 后重置失败状态并重新加载', async () => {
    const wrapper = mount(LazyImage, { props: { src: POSTER } })

    for (let i = 0; i < 2; i++) {
      await wrapper.find('img').trigger('error')
      vi.advanceTimersByTime(1000)
      await nextTick()
    }
    await wrapper.find('img').trigger('error')

    await wrapper.setProps({ src: OTHER_POSTER })
    expect(wrapper.find('img').attributes('src')).toBe(OTHER_POSTER)
    wrapper.unmount()
  })
})
