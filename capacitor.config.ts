/// <reference types="@capacitor/cli" />

import type { CapacitorConfig } from '@capacitor/cli'

/**
 * 夭夭影社 · Capacitor 配置
 *
 * 对齐 docs/ARCHITECTURE.md 4.1：
 * - 根工程加载 `frontend/dist`（同一套 Vue SPA，双轨同构）
 * - `androidScheme: 'https'` + `allowMixedContent` 允许局域网 NAS 明文直连
 * - 状态栏 / 键盘 / 屏幕方向对齐「东方纯白通透」
 */
const config: CapacitorConfig = {
  appId: 'com.yaoyao.cinema',
  appName: '夭夭影社',
  webDir: 'frontend/dist',

  server: {
    // 生产模式：加载本地打包文件（离线可用）
    androidScheme: 'https',
    // 允许直接访问 NAS 局域网地址（含 API 与 206 流）
    allowNavigation: ['192.168.31.235:9900', '192.168.31.235'],
    cleartext: true,
  },

  android: {
    // 允许明文 HTTP（局域网 NAS 场景）
    allowMixedContent: true,
    // 纯白背景，避免首帧黑闪
    backgroundColor: '#FFFFFF',
    // 发布构建关闭 WebView 远程调试
    webContentsDebuggingEnabled: false,
  },

  plugins: {
    StatusBar: {
      style: 'LIGHT', // 浅色背景 → 深色状态栏文字
      backgroundColor: '#FFFFFF',
    },
    Keyboard: {
      resize: 'body',
      style: 'LIGHT',
    },
    ScreenOrientation: {}, // 播放器横屏锁定
  },
}

export default config
