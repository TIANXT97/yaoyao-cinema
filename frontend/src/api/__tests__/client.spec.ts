import { beforeEach, describe, expect, it } from 'vitest'

import { buildUrl, setApiBase } from '@/api/client'

describe('setApiBase 基址规整', () => {
  beforeEach(() => {
    window.localStorage.clear()
    setApiBase('')
  })

  it.each([
    ['http://cinema.yaoyao:9900', 'http://cinema.yaoyao:9900/api'],
    ['http://cinema.yaoyao:9900/', 'http://cinema.yaoyao:9900/api'],
    ['  http://cinema.yaoyao:9900  ', 'http://cinema.yaoyao:9900/api'],
    ['http://192.168.31.235:9900/api', 'http://192.168.31.235:9900/api'],
    ['http://192.168.31.235:9900/api/', 'http://192.168.31.235:9900/api'],
    ['/api', '/api'],
  ])('输入 %s 规整为 %s', (input, expected) => {
    expect(setApiBase(input)).toBe(expected)
  })

  it('空串与根路径回退到默认相对路径 /api', () => {
    expect(setApiBase('')).toBe('/api')
    expect(setApiBase('/')).toBe('/api')
  })

  it('规整后的基址用于拼接请求地址', () => {
    setApiBase('http://cinema.yaoyao:9900')
    expect(buildUrl('/system/stats')).toBe('http://cinema.yaoyao:9900/api/system/stats')
  })
})
