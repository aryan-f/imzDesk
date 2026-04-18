// https://nuxt.com/docs/api/configuration/nuxt-config
export default defineNuxtConfig({
  ssr: false,

  modules: [
    '@nuxt/ui'
  ],

  devtools: {
    enabled: true
  },

  nitro: {
    devProxy: {
      '/api': {
        target: 'http://127.0.0.1:8000/api',
        changeOrigin: true,
      },
    },
  },

  compatibilityDate: '2026-04-17',

  css: ['~/assets/css/main.css'],
})
