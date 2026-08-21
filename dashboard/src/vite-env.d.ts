/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_OPENPC_TOKEN?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}