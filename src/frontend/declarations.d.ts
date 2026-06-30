declare module "*.png" {
    const value: string;
    export default value;
}

/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_APP_WEB_CLIENT_ID: string
  readonly VITE_APP_WEB_AUTHORITY: string
  readonly VITE_APP_REDIRECT_URL: string
  readonly VITE_APP_POST_REDIRECT_URL: string
  readonly VITE_APP_WEB_SCOPE: string
  readonly VITE_APP_API_SCOPE: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
  