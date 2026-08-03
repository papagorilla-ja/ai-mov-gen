<template>
  <v-app>
    <!-- グローバルナビゲーションドロワー -->
    <v-navigation-drawer permanent width="240" class="glass-sidebar">
      <div class="pa-4 d-flex align-center logo-header">
        <div class="logo-avatar-wrapper mr-3">
          <img :src="logoUrl" alt="AI-MovGen Logo" class="logo-img" />
          <div class="logo-glow"></div>
        </div>
        <div>
          <div class="text-subtitle-1 font-weight-bold logo-title">AI-MovGen</div>
          <div class="text-caption text-medium-emphasis">AI 動画作成</div>
        </div>
      </div>
      <v-divider class="border-opacity-15 mb-2" />
      <v-list density="compact" nav>
        <v-list-item
          prepend-icon="mdi-home-outline"
          title="ホーム"
          value="home"
          :to="{ path: '/' }"
          exact
        />
        <v-list-item
          prepend-icon="mdi-cog-outline"
          title="設定"
          value="settings"
          :to="{ path: '/settings' }"
        />
      </v-list>
    </v-navigation-drawer>

    <!-- メインコンテンツ -->
    <v-main>
      <router-view v-slot="{ Component }">
        <transition name="fade" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </v-main>

    <!-- グローバルスナックバー (Pinia の ui ストアで制御) -->
    <v-snackbar
      v-model="snackbar.show"
      :color="snackbar.color"
      :timeout="snackbar.timeout"
      location="bottom end"
    >
      {{ snackbar.message }}
      <template #actions>
        <v-btn icon="mdi-close" @click="snackbar.show = false" />
      </template>
    </v-snackbar>
  </v-app>
</template>

<script setup>
import { storeToRefs } from 'pinia'
import { useUiStore } from '@/stores/ui'
import logoUrl from '@/assets/logo.jpg'

const uiStore = useUiStore()
const { snackbar } = storeToRefs(uiStore)
</script>

<style>
#app {
  background: #0f0f1a !important;
  background-image: 
    radial-gradient(at 0% 0%, rgba(99, 102, 241, 0.15) 0px, transparent 50%),
    radial-gradient(at 100% 0%, rgba(139, 92, 246, 0.12) 0px, transparent 50%),
    radial-gradient(at 50% 100%, rgba(34, 211, 238, 0.08) 0px, transparent 50%) !important;
  background-attachment: fixed !important;
}

.v-application {
  background: transparent !important;
}
.v-main {
  background: transparent !important;
}

/* グラスモーフィズム共通定義 */
.glass-card {
  background: rgba(26, 26, 46, 0.45) !important;
  backdrop-filter: blur(16px) saturate(180%) !important;
  -webkit-backdrop-filter: blur(16px) saturate(180%) !important;
  border: 1px solid rgba(255, 255, 255, 0.08) !important;
  box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3) !important;
  border-radius: 12px !important;
}

/* ホバー可能なグラスカード */
.glass-card-interactive {
  transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1) !important;
}
.glass-card-interactive:hover {
  background: rgba(26, 26, 46, 0.6) !important;
  border-color: rgba(99, 102, 241, 0.25) !important;
  box-shadow: 0 12px 40px 0 rgba(99, 102, 241, 0.15) !important;
  transform: translateY(-2px);
}

/* グラスサイドバー */
.glass-sidebar {
  background: rgba(15, 15, 26, 0.45) !important;
  backdrop-filter: blur(20px) !important;
  -webkit-backdrop-filter: blur(20px) !important;
  border-right: 1px solid rgba(255, 255, 255, 0.06) !important;
}

/* グラスパネル (エディタのツールバー等用) */
.glass-panel {
  background: rgba(26, 26, 46, 0.5) !important;
  backdrop-filter: blur(12px) !important;
  -webkit-backdrop-filter: blur(12px) !important;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08) !important;
}

/* グラスモーフィズムダイアログ */
.v-dialog > .v-overlay__content > .v-card {
  background: rgba(26, 26, 46, 0.65) !important;
  backdrop-filter: blur(24px) saturate(180%) !important;
  -webkit-backdrop-filter: blur(24px) saturate(180%) !important;
  border: 1px solid rgba(255, 255, 255, 0.12) !important;
  box-shadow: 0 24px 64px 0 rgba(0, 0, 0, 0.5) !important;
  border-radius: 16px !important;
}

/* スナックバーもグラスモーフィズム調に */
.v-snackbar__wrapper {
  background: rgba(26, 26, 46, 0.8) !important;
  backdrop-filter: blur(12px) !important;
  -webkit-backdrop-filter: blur(12px) !important;
  border: 1px solid rgba(255, 255, 255, 0.1) !important;
  box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3) !important;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.15s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

/* ロゴ・ブランド部のグラスモーフィズムデザイン */
.logo-header {
  position: relative;
  background: rgba(255, 255, 255, 0.02);
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.logo-avatar-wrapper {
  position: relative;
  width: 42px;
  height: 42px;
  border-radius: 12px;
  overflow: visible;
}

.logo-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.25);
  box-shadow: 0 4px 16px rgba(34, 211, 238, 0.35), 0 0 8px rgba(139, 92, 246, 0.25);
  position: relative;
  z-index: 2;
  transition: transform 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.logo-avatar-wrapper:hover .logo-img {
  transform: scale(1.08) rotate(3deg);
}

.logo-glow {
  position: absolute;
  top: -4px;
  left: -4px;
  right: -4px;
  bottom: -4px;
  background: linear-gradient(135deg, rgba(34, 211, 238, 0.6), rgba(168, 85, 247, 0.6));
  border-radius: 14px;
  filter: blur(8px);
  opacity: 0.6;
  z-index: 1;
  transition: opacity 0.3s ease;
}

.logo-avatar-wrapper:hover .logo-glow {
  opacity: 0.95;
  filter: blur(10px);
}

.logo-title {
  background: linear-gradient(135deg, #ffffff 30%, #22d3ee 70%, #c084fc 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  letter-spacing: 0.5px;
}
</style>
