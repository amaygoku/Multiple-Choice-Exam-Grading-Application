import fs from 'fs';
import path from 'path';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import { defineConfig, loadEnv } from 'vite';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '.', '');
  const httpsCertFile = env.VITE_HTTPS_CERT_FILE;
  const httpsKeyFile = env.VITE_HTTPS_KEY_FILE;
  const backendProxyTarget = env.VITE_BACKEND_PROXY_TARGET || 'https://127.0.0.1:8000';
  const httpsEnabled = Boolean(
    httpsCertFile &&
    httpsKeyFile &&
    fs.existsSync(httpsCertFile) &&
    fs.existsSync(httpsKeyFile)
  );

  return {
    plugins: [react(), tailwindcss()],
    define: {
      'process.env.GEMINI_API_KEY': JSON.stringify(env.GEMINI_API_KEY),
    },
    resolve: {
      alias: {
        '@': path.resolve(__dirname, '.'),
      },
    },
    server: {
      host: '0.0.0.0',
      port: Number(env.VITE_PORT ?? 3000),
      strictPort: true,
      // HMR is disabled in AI Studio via DISABLE_HMR env var.
      hmr: process.env.DISABLE_HMR !== 'true',
      proxy: {
        '/api': {
          target: backendProxyTarget,
          changeOrigin: true,
          secure: false,
        },
        '/results': {
          target: backendProxyTarget,
          changeOrigin: true,
          secure: false,
        },
        '/static': {
          target: backendProxyTarget,
          changeOrigin: true,
          secure: false,
        },
        '/static_results': {
          target: backendProxyTarget,
          changeOrigin: true,
          secure: false,
        },
      },
      https: httpsEnabled
        ? {
            cert: fs.readFileSync(httpsCertFile),
            key: fs.readFileSync(httpsKeyFile),
          }
        : undefined,
    },
  };
});
