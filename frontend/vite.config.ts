import { fileURLToPath, URL } from 'node:url'

import tailwindcss from '@tailwindcss/vite'
import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'

/**
 * 夭夭影社 · Vite 配置
 *
 * - `@` 别名指向 `src/`
 * - Tailwind CSS v4（`@tailwindcss/vite` 插件，CSS-first 配置）
 * - 开发环境将 `/api` 代理到 NAS / 本地 FastAPI（默认 127.0.0.1:9900）
 * - 生产构建产物输出到 `frontend/dist`，由 FastAPI 静态伺服
 */
export default defineConfig(({ mode }) => {
  const proxyTarget =
    process.env.VITE_PROXY_TARGET || 'http://127.0.0.1:9900'

  return {
    plugins: [vue(), tailwindcss()],

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
