import type { Config } from 'tailwindcss'

/**
 * 夭夭影社 · Tailwind CSS v4 配置
 *
 * 设计哲学：东方纯白极简通透（Anti-Slop Minimalist Editorial）。
 * 主色板与设计 Token 同时以 CSS 变量（`:root --yy-*`）与
 * Tailwind `@theme`（`src/style.css`）双重暴露，便于 DevTools 审阅。
 *
 * 说明：Tailwind v4 采用 CSS-first 配置，主配置位于 `src/style.css` 的
 * `@theme` 块中；本文件保留给编辑器 / 工具链语义提示，并可通过
 * `@config "../tailwind.config.ts"` 显式加载。
 */
const config: Config = {
  content: ['./index.html', './src/**/*.{vue,js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        paper: {
          DEFAULT: '#FFFFFF',
          soft: '#FAFAFA',
          mute: '#F5F5F5',
          elevated: '#FFFFFF',
        },
        ink: {
          DEFAULT: '#1A1A1A',
          soft: '#666666',
          faint: '#999999',
          mute: '#CCCCCC',
        },
        line: '#EBEBEB',
        accent: {
          DEFAULT: '#D4A574',
          hover: '#C49464',
        },
        player: {
          DEFAULT: '#000000',
        },
      },
      fontFamily: {
        sans: [
          'SF Pro Text',
          'PingFang SC',
          'Hiragino Sans',
          'Noto Sans SC',
          'system-ui',
          'sans-serif',
        ],
        serif: ['Noto Serif SC', 'Source Han Serif SC', 'SimSun', 'serif'],
        mono: ['SF Mono', 'JetBrains Mono', 'Fira Code', 'monospace'],
      },
      borderRadius: {
        sm: '4px',
        md: '8px',
        lg: '12px',
        xl: '16px',
      },
      transitionTimingFunction: {
        yy: 'cubic-bezier(0.25, 0.1, 0.25, 1)',
      },
      boxShadow: {
        poster: '0 8px 32px rgba(0, 0, 0, 0.08)',
        soft: '0 1px 2px rgba(0, 0, 0, 0.03)',
      },
    },
  },
  plugins: [],
}

export default config
