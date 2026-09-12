/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** 后端 API 基础路径；缺省为同源 `/api`（由 Vite 代理 / FastAPI 伺服）。 */
  readonly VITE_API_BASE?: string
  /** 开发代理目标（仅 vite.config.ts 使用）。 */
  readonly VITE_PROXY_TARGET?: string
  /** 应用标题。 */
  readonly VITE_APP_TITLE?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
