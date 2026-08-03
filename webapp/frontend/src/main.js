import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { createVuetify } from 'vuetify'
import * as components from 'vuetify/components'
import * as directives from 'vuetify/directives'
import 'vuetify/styles'
import '@mdi/font/css/materialdesignicons.css'

import App from './App.vue'
import router from './router'

// ─── Vuetify テーマ設定 ───────────────────────────────────
const vuetify = createVuetify({
  components,
  directives,
  theme: {
    defaultTheme: 'dark',
    themes: {
      dark: {
        colors: {
          primary:    '#6366f1',   // インディゴ
          secondary:  '#8b5cf6',   // バイオレット
          accent:     '#22d3ee',   // シアン
          background: '#0f0f1a',   // ダークネイビー
          surface:    '#1a1a2e',
          error:      '#ef4444',
          warning:    '#f59e0b',
          info:       '#3b82f6',
          success:    '#10b981',
        },
      },
    },
  },
  defaults: {
    VBtn: { variant: 'tonal' },
    VCard: { rounded: 'lg' },
  },
})

// ─── アプリ組み立て ───────────────────────────────────────
createApp(App)
  .use(createPinia())
  .use(router)
  .use(vuetify)
  .mount('#app')
