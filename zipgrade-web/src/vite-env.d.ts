/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string;
  readonly VITE_BACKEND_PROXY_TARGET?: string;
  readonly VITE_APP_LOCK_PASSWORD?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
