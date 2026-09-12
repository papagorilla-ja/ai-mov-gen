<template>
  <v-container fluid class="pa-6 project-container">
    <!-- ─── パンくずリスト & ナビゲーション ─── -->
    <div class="d-flex align-center mb-4">
      <v-btn
        variant="text"
        prepend-icon="mdi-arrow-left"
        size="small"
        class="text-medium-emphasis mr-2"
        :to="{ path: '/' }"
      >
        プロジェクト一覧
      </v-btn>
      <v-icon size="16" color="medium-emphasis" class="mr-2">mdi-chevron-right</v-icon>
      <span class="text-caption font-weight-bold text-cyan">
        {{ projectStore.currentProject?.name ?? 'Loading...' }}
      </span>
    </div>

    <!-- ─── プロジェクトヘッダーバナー ─── -->
    <div class="project-header-card glass-card pa-6 mb-6 rounded-xl position-relative overflow-hidden">
      <div class="header-glow"></div>
      <div class="d-flex align-start justify-space-between flex-wrap gap-4 position-relative" style="z-index: 2;">
        <div class="d-flex align-start gap-4">
          <div class="project-icon-box">
            <v-icon size="32" color="#06b6d4">mdi-folder-video-outline</v-icon>
          </div>
          <div>
            <div class="d-flex align-center gap-2 mb-1">
              <h1 class="text-h5 font-weight-black project-heading">
                {{ projectStore.currentProject?.name ?? 'プロジェクト読み込み中...' }}
              </h1>
              <v-chip size="x-small" color="primary" variant="flat" class="font-weight-bold">
                {{ videoStore.videos.length }} 本の動画
              </v-chip>
            </div>
            <p class="text-body-2 text-medium-emphasis" style="max-width: 700px;">
              {{ projectStore.currentProject?.description || 'このプロジェクトにはまだ説明がありません。' }}
            </p>
          </div>
        </div>

        <div class="d-flex align-center gap-2">
          <v-btn
            prepend-icon="mdi-video-plus"
            class="btn-neon-primary"
            elevation="4"
            @click="newVideoDialog = true"
          >
            新しい動画を作成
          </v-btn>
        </div>
      </div>
    </div>

    <!-- ─── 動画カード一覧 ─── -->
    <div v-if="videoStore.videos.length">
      <div class="d-flex align-center justify-space-between mb-4">
        <h2 class="text-subtitle-1 font-weight-bold d-flex align-center gap-2">
          <v-icon size="20" color="#06b6d4">mdi-filmstrip</v-icon>
          動画クリップ一覧 ({{ videoStore.videos.length }})
        </h2>
      </div>

      <v-row>
        <v-col
          v-for="video in videoStore.videos"
          :key="video.id"
          cols="12" sm="6" md="4" lg="3"
        >
          <v-card
            class="video-card glass-card glass-card-interactive position-relative overflow-hidden d-flex flex-column"
            :to="{ name: 'VideoEditor', params: { videoId: video.id } }"
          >
            <!-- 16:9 サムネイルプレビュー領域 -->
            <div class="video-thumb-wrapper position-relative">
              <img :src="cardThumbUrl" alt="Video Thumbnail" class="video-thumb-img" />
              <div class="video-thumb-overlay"></div>
              
              <!-- 再生アイコンオーバーレイ (ホバー時強調) -->
              <div class="play-overlay position-absolute">
                <v-icon size="36" color="#ffffff">mdi-play-circle-outline</v-icon>
              </div>

              <!-- ステータスバッジ -->
              <div class="status-badge-chip position-absolute" :class="`status-${video.status}`">
                <span v-if="video.status === 'generating'" class="status-dot-pulse"></span>
                <span class="text-uppercase font-weight-bold text-xxs">{{ video.status }}</span>
              </div>

              <!-- 長さバッジ -->
              <div class="duration-badge-chip position-absolute">
                <v-icon size="12" class="mr-1">mdi-clock-outline</v-icon>
                <span>{{ video.duration_sec ? `${video.duration_sec.toFixed(1)}s` : '未生成' }}</span>
              </div>
            </div>

            <!-- カードコンテンツ部 -->
            <div class="pa-4 d-flex flex-column flex-grow-1">
              <h3 class="text-subtitle-1 font-weight-bold text-truncate mb-1 text-white" :title="video.name">
                {{ video.name }}
              </h3>

              <div class="text-caption text-medium-emphasis mb-3">
                解像度: 1920x1080 (16:9)
              </div>

              <v-divider class="border-opacity-10 mb-2 mt-auto" />

              <!-- 操作アクションフッター -->
              <div class="d-flex align-center justify-space-between pt-1">
                <span class="text-xxs text-medium-emphasis">ID: {{ video.id.slice(0, 8) }}</span>

                <div class="d-flex align-center gap-1">
                  <v-btn
                    icon="mdi-content-duplicate"
                    color="secondary"
                    variant="text"
                    size="small"
                    title="複製"
                    @click.stop.prevent="handleDuplicate(video.id)"
                  />
                  <v-btn
                    icon="mdi-delete-outline"
                    color="error"
                    variant="text"
                    size="small"
                    title="削除"
                    @click.stop.prevent="confirmDelete(video)"
                  />
                </div>
              </div>
            </div>
          </v-card>
        </v-col>
      </v-row>
    </div>

    <!-- ─── 空状態: 動画がまだない場合 (AIアートワーク & ガイド) ─── -->
    <div v-else class="empty-video-showcase glass-card pa-8 pa-md-12 text-center rounded-xl mx-auto my-8">
      <div class="empty-video-art mb-6 position-relative">
        <img :src="emptyVideosArtUrl" alt="No Videos Clapperboard" class="empty-art-img" />
        <div class="empty-art-glow"></div>
      </div>

      <h2 class="text-h5 font-weight-bold mb-2">まだ動画が作成されていません</h2>
      <p class="text-body-2 text-medium-emphasis mb-6" style="max-width: 520px; margin: 0 auto;">
        「新しい動画を作成」ボタンから動画エディタを開き、シナリオやスライド構成を入力してください。
      </p>

      <!-- 制作ステップの案内カード -->
      <div class="creation-steps-grid mb-6 mx-auto">
        <div class="step-card pa-3 rounded-lg text-left">
          <div class="text-cyan font-weight-bold text-caption mb-1">STEP 1</div>
          <div class="text-subtitle-2 font-weight-bold">シナリオ入力</div>
          <div class="text-xxs text-medium-emphasis">PPTX・テキスト貼付・AIチャット対応</div>
        </div>
        <div class="step-card pa-3 rounded-lg text-left">
          <div class="text-purple font-weight-bold text-caption mb-1">STEP 2</div>
          <div class="text-subtitle-2 font-weight-bold">シーン &amp; 話者設定</div>
          <div class="text-xxs text-medium-emphasis">スライドレイアウトと高品質TTS話者</div>
        </div>
        <div class="step-card pa-3 rounded-lg text-left">
          <div class="text-cyan font-weight-bold text-caption mb-1">STEP 3</div>
          <div class="text-subtitle-2 font-weight-bold">動画レンダリング</div>
          <div class="text-xxs text-medium-emphasis">HyperFramesによる高速高画質出力</div>
        </div>
      </div>

      <v-btn
        prepend-icon="mdi-video-plus"
        class="btn-neon-primary px-6"
        size="large"
        @click="newVideoDialog = true"
      >
        新しい動画を作成
      </v-btn>
    </div>

    <!-- ─── 新しい動画作成ダイアログ ─── -->
    <v-dialog v-model="newVideoDialog" max-width="500">
      <v-card class="glass-card pa-2">
        <v-card-title class="pa-4 d-flex align-center gap-2">
          <v-icon color="#06b6d4">mdi-video-plus-outline</v-icon>
          <span class="font-weight-bold">新しい動画の作成</span>
        </v-card-title>
        <v-card-text class="pa-4 pt-0">
          <p class="text-caption text-medium-emphasis mb-4">
            作成する動画クリップの名称を入力してください。作成後、シナリオ入力エディタが開きます。
          </p>
          <v-text-field
            v-model="newVideo.name"
            label="動画名"
            placeholder="例: 第1章 サービス概要紹介"
            autofocus
            class="mb-2"
            :rules="[v => !!v || '動画名は必須です']"
          />
        </v-card-text>
        <v-card-actions class="pa-4 pt-0">
          <v-spacer />
          <v-btn variant="text" @click="newVideoDialog = false">キャンセル</v-btn>
          <v-btn
            class="btn-neon-primary"
            :disabled="!newVideo.name.trim()"
            @click="handleCreateVideo"
          >
            エディタで作成する
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- ─── 動画削除確認ダイアログ ─── -->
    <v-dialog v-model="deleteDialog" max-width="420">
      <v-card class="glass-card pa-2">
        <v-card-title class="pa-4 d-flex align-center gap-2 text-error">
          <v-icon color="error">mdi-alert-circle-outline</v-icon>
          <span class="font-weight-bold">動画を削除しますか？</span>
        </v-card-title>
        <v-card-text class="pa-4 pt-0">
          動画「<strong>{{ videoToDelete?.name }}</strong>」および、生成された音声・レンダリング済み動画ファイルがすべて削除されます。<br />
          この操作は元に戻せません。
        </v-card-text>
        <v-card-actions class="pa-4">
          <v-spacer />
          <v-btn variant="text" @click="deleteDialog = false">キャンセル</v-btn>
          <v-btn color="error" variant="flat" @click="handleDeleteVideo">削除する</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-container>
</template>

<script setup>
/**
 * ProjectView.vue - プロジェクト内動画一覧画面
 * Cyber Studio / Neon Glass テーマに合わせたリッチなUI/UXを提供
 */
import { ref, reactive, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useProjectsStore } from '@/stores/projects'
import { useVideosStore } from '@/stores/videos'

// アセット画像
import cardThumbUrl from '@/assets/card_thumb_default.jpg'
import emptyVideosArtUrl from '@/assets/empty_videos_art.jpg'

const route = useRoute()
const projectId = route.params.projectId

const projectStore = useProjectsStore()
const videoStore = useVideosStore()

// ─── 画面ダイアログステート ──────────────────────────────
const newVideoDialog = ref(false)
const deleteDialog = ref(false)
const videoToDelete = ref(null)
const newVideo = reactive({ name: '' })

onMounted(async () => {
  await projectStore.fetchOne(projectId)
  await videoStore.fetchAll(projectId)
})

// ─── 動画操作ハンドラ ───────────────────────────────────
async function handleCreateVideo() {
  if (!newVideo.name.trim()) return
  await videoStore.create(projectId, { ...newVideo })
  newVideo.name = ''
  newVideoDialog.value = false
}

async function handleDuplicate(videoId) {
  await videoStore.duplicate(videoId)
}

function confirmDelete(video) {
  videoToDelete.value = video
  deleteDialog.value = true
}

async function handleDeleteVideo() {
  if (videoToDelete.value) {
    await videoStore.remove(videoToDelete.value.id)
    deleteDialog.value = false
    videoToDelete.value = null
  }
}
</script>

<style scoped>
.project-container {
  max-width: 1600px;
  margin: 0 auto;
}

/* ─── プロジェクトヘッダーカード ─── */
.project-header-card {
  border: 1px solid rgba(6, 182, 212, 0.25) !important;
  background: rgba(19, 22, 40, 0.6) !important;
  box-shadow: 0 12px 32px 0 rgba(0, 0, 0, 0.45) !important;
}
.header-glow {
  position: absolute;
  top: 0;
  right: 0;
  width: 300px;
  height: 100%;
  background: radial-gradient(circle at top right, rgba(6, 182, 212, 0.15), transparent 70%);
  pointer-events: none;
}
.project-icon-box {
  width: 52px;
  height: 52px;
  border-radius: 14px;
  background: rgba(6, 182, 212, 0.12);
  border: 1px solid rgba(6, 182, 212, 0.3);
  display: flex;
  align-items: center;
  justify-content: center;
}
.project-heading {
  color: #f8fafc;
  letter-spacing: -0.3px;
}

/* ─── ネオンボタン ─── */
.btn-neon-primary {
  background: linear-gradient(135deg, #06b6d4 0%, #6366f1 100%) !important;
  color: #ffffff !important;
  font-weight: 700 !important;
  box-shadow: 0 4px 18px 0 rgba(6, 182, 212, 0.45) !important;
  transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1) !important;
}
.btn-neon-primary:hover {
  box-shadow: 0 6px 24px 0 rgba(6, 182, 212, 0.65) !important;
  transform: translateY(-1px);
}

/* ─── 動画カード ─── */
.video-card {
  height: 100%;
  border-radius: 16px !important;
  border: 1px solid rgba(255, 255, 255, 0.08) !important;
  transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1) !important;
}
.video-thumb-wrapper {
  width: 100%;
  height: 150px;
  overflow: hidden;
}
.video-thumb-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  transition: transform 0.4s ease;
}
.video-card:hover .video-thumb-img {
  transform: scale(1.08);
}
.video-thumb-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: linear-gradient(to top, rgba(19, 22, 40, 0.95) 0%, rgba(19, 22, 40, 0.2) 60%, transparent 100%);
}

.play-overlay {
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  opacity: 0.8;
  transition: all 0.3s ease;
}
.video-card:hover .play-overlay {
  opacity: 1;
  transform: translate(-50%, -50%) scale(1.15);
}

.status-badge-chip {
  top: 10px;
  left: 10px;
  padding: 3px 10px;
  border-radius: 20px;
  backdrop-filter: blur(8px);
  border: 1px solid rgba(255, 255, 255, 0.15);
  display: flex;
  align-items: center;
  gap: 4px;
}
.status-draft {
  background: rgba(100, 116, 139, 0.6);
  color: #cbd5e1;
}
.status-generating {
  background: rgba(245, 158, 11, 0.6);
  color: #fef3c7;
  border-color: rgba(245, 158, 11, 0.4);
}
.status-completed {
  background: rgba(16, 185, 129, 0.6);
  color: #d1fae5;
  border-color: rgba(16, 185, 129, 0.4);
}
.status-failed {
  background: rgba(244, 63, 94, 0.6);
  color: #ffe4e6;
}
.status-dot-pulse {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #f59e0b;
  box-shadow: 0 0 6px #f59e0b;
  animation: pulse 1.5s infinite;
}

.duration-badge-chip {
  bottom: 10px;
  right: 10px;
  background: rgba(9, 10, 20, 0.8);
  border-radius: 6px;
  padding: 2px 8px;
  font-size: 0.72rem;
  color: #e2e8f0;
  display: flex;
  align-items: center;
}

/* ─── エンプティステート ─── */
.empty-video-showcase {
  max-width: 680px;
  border: 1px dashed rgba(6, 182, 212, 0.3) !important;
}
.empty-video-art {
  width: 240px;
  height: 140px;
  margin: 0 auto;
}
.empty-art-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  border-radius: 14px;
  border: 1px solid rgba(6, 182, 212, 0.3);
  position: relative;
  z-index: 2;
}
.empty-art-glow {
  position: absolute;
  top: -8px;
  left: -8px;
  right: -8px;
  bottom: -8px;
  background: radial-gradient(circle, rgba(6, 182, 212, 0.4) 0%, rgba(168, 85, 247, 0.2) 60%, transparent 80%);
  filter: blur(12px);
  z-index: 1;
}

.creation-steps-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
  max-width: 620px;
}
.step-card {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.08);
}
</style>
