import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import { tanstackRouter } from '@tanstack/router-plugin/vite'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  // Load HACHI_* (non-VITE) vars too so the dev proxy can read the token.
  const env = loadEnv(mode, process.cwd(), ['VITE_', 'HACHI_'])
  const gatewayTarget = env.HACHI_GATEWAY_PROXY_TARGET || 'http://127.0.0.1:8787'
  const gatewayToken = env.HACHI_GATEWAY_TOKEN || ''

  return {
    plugins: [
      // tanstackRouter MUST come before react
      tanstackRouter({
        target: 'react',
        autoCodeSplitting: true,
      }),
      react(),
    ],
    server: {
      port: 5173,
      proxy: {
        // Proxy REST + SSE to the gateway, stripping the /api prefix and
        // injecting the bearer token so the browser never holds it. SSE works
        // because we never buffer the streamed body.
        '/api': {
          target: gatewayTarget,
          changeOrigin: true,
          ws: true,
          rewrite: (path) => path.replace(/^\/api/, ''),
          configure: (proxy) => {
            proxy.on('proxyReq', (proxyReq) => {
              if (gatewayToken) {
                proxyReq.setHeader('Authorization', `Bearer ${gatewayToken}`)
              }
            })
          },
        },
      },
    },
    test: {
      environment: 'jsdom',
    },
  }
})
