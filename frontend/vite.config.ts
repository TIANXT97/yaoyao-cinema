import { fileURLToPath, URL } from 'node:url'

import tailwindcss from '@tailwindcss/vite'
import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'
import { VitePWA } from 'vite-plugin-pwa'

/**
 * 夭夭影社 · Vite 配置
 *
 * - `@` 别名指向 `src/`
 * - Tailwind CSS v4（`@tailwindcss/vite` 插件，CSS-first 配置）
 * - `vite-plugin-pwa`：App Shell / API / 图片分层缓存，视频流永不缓存
 * - 开发环境将 `/api` 代理到 NAS / 本地 FastAPI（默认 127.0.0.1:9900）
 * - 生产构建产物输出到 `frontend/dist`，由 FastAPI 静态伺服
 */
export default defineConfig(({ mode }) => {
  const proxyTarget =
    process.env.VITE_PROXY_TARGET || 'http://127.0.0.1:9900'

  return {
    plugins: [
      vue(),
      tailwindcss(),

      // PWA / Service Worker（对齐 ARCHITECTURE.md 3.3.2）
      VitePWA({
        registerType: 'autoUpdate',
        injectRegister: 'auto',
        // manifest 由 public/manifest.webmanifest 手工维护，避免双重生成
        manifest: false,
        includeAssets: [
          'favicon.svg',
          'icon.svg',
          'icons/*.png',
        ],
        workbox: {
          globPatterns: ['**/*.{js,css,html,svg,png,ico,webmanifest,woff,woff2}'],
          navigateFallback: '/index.html',
          // API 请求绝不回退到 index.html
          navigateFallbackDenylist: [/^\/api\//],
          cleanupOutdatedCaches: true,
          clientsClaim: true,
          skipWaiting: true,
          runtimeCaching: [
            {
              // API 数据 → NetworkFirst（30s 超时回退缓存）
              urlPattern: /^https?:\/\/.*\/api\/(?!stream|images).*/,
              handler: 'NetworkFirst',
              options: {
                cacheName: 'api-cache',
                networkTimeoutSeconds: 30,
                expiration: { maxEntries: 200, maxAgeSeconds: 86400 },
                cacheableResponse: { statuses: [0, 200] },
              },
            },
            {
              // 图片 → CacheFirst（最多 500 张，7 天）
              urlPattern: /^https?:\/\/.*\/api\/images\/.*/,
              handler: 'CacheFirst',
              options: {
                cacheName: 'image-cache',
                expiration: { maxEntries: 500, maxAgeSeconds: 604800 },
                cacheableResponse: { statuses: [0, 200] },
              },
            },
            {
              // 视频流 → NetworkOnly（Range 请求，GB 级，绝不缓存）
              urlPattern: /^https?:\/\/.*\/api\/stream\/.*/,
              handler: 'NetworkOnly',
            },
          ],
        },
        devOptions: { enabled: false },
      }),
    ],

    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url)),
      },
    },

    server: {
      host: true,
      port: 5173,
      strictPort: false,
      proxy: {
        '/api': {
          target: proxyTarget,
          changeOrigin: true,
          ws: false,
        },
      },
    },

    preview: {
      host: true,
      port: 4173,
    },

    build: {
      outDir: 'dist',
      assetsDir: 'assets',
      sourcemap: mode !== 'production',
      target: 'es2020',
      chunkSizeWarningLimit: 1600,
      rollupOptions: {
        output: {
          manualChunks: {
            vue: ['vue', 'vue-router', 'pinia'],
            icons: ['lucide-vue-next'],
          },
        },
      },
    },
  }
})
