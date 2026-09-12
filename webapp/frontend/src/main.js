import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { createVuetify } from 'vuetify'
import * as components from 'vuetify/components'
import * as directives from 'vuetify/directives'
import 'vuetify/styles'
import '@mdi/font/css/materialdesignicons.css'

import App from './App.vue'
import router from './router'

// ─── Vuetify テーマ設定 (Cyber Studio / Neon Glass スタイル) ───
const vuetify = createVuetify({
  components,
  directives,
  theme: {
    defaultTheme: 'dark',
    themes: {
      dark: {
        dark: true,
        colors: {
          primary:    '#06b6d4',   // エレクトリック・シアン（メインアクション、ハイライト）
          secondary:  '#a855f7',   // ネオン・パープル（クリエイティブ、AIアクセント）
          accent:     '#6366f1',   // ネオン・インディゴ（補色、深度）
          background: '#090a14',   // 超暗色ディープスペース背景
          surface:    '#131628',   // カード・パネル用サーフェス
          'surface-variant': '#1a1e36',
          error:      '#f43f5e',   // ネオン・ローズレッド
          warning:    '#fbbf24',   // アンバー
          info:       '#38bdf8',   // ライトスカイ
          success:    '#10b981',   // エメラルドグリーン
        },
      },
    },
  },
  defaults: {
    VBtn: {
      rounded: 'lg',
      elevation: 0,
    },
    VCard: {
      rounded: 'xl',
      elevation: 0,
    },
    VTextField: {
      variant: 'outlined',
      density: 'comfortable',
    },
    VSelect: {
      variant: 'outlined',
      density: 'comfortable',
    },
  },
})

// ─── アプリ組み立て ───────────────────────────────────────
createApp(App)
  .use(createPinia())
  .use(router)
  .use(vuetify)
  .mount('#app')
