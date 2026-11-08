import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig({
  plugins: [
    vue(),
    VitePWA({
      registerType: 'autoUpdate',
      manifest: {
        name: '我的家',
        short_name: '我的家',
        description: '本地智能家居控制',
        lang: 'zh-CN',
        display: 'standalone',
        background_color: '#f6f7f9',
        theme_color: '#f6f7f9',
        icons: [
          { src: '/icon-192.png', sizes: '192x192', type: 'image/png' },
          { src: '/icon-512.png', sizes: '512x512', type: 'image/png' },
          { src: '/icon-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
        ],
      },
      workbox: {
        navigateFallbackDenylist: [/^\/api/],
      },
    }),
  ],
  server: {
    host: true,
    proxy: {
      '/api': { target: 'http://127.0.0.1:8080', ws: true },
    },
  },
})
