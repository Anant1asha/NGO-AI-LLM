/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_HACHI_GATEWAY_URL?: string
  readonly VITE_HACHI_USE_MOCKS?: string
  readonly VITE_HACHI_TOKEN?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
