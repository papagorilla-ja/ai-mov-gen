<template>
  <v-container fluid class="pa-6 home-container">
    <!-- ─── ヒーローヘッダー & スタジオバナー ─── -->
    <div class="hero-studio-card mb-6 glass-card overflow-hidden position-relative">
      <div class="hero-bg-overlay"></div>
      <img :src="heroBannerUrl" alt="Studio Banner" class="hero-banner-image" />
      
      <div class="hero-content position-relative pa-6 d-flex flex-column justify-space-between">
        <div class="d-flex align-center justify-space-between flex-wrap gap-4">
          <div class="d-flex align-center">
            <div class="home-logo-wrapper mr-4">
              <img :src="logoUrl" alt="AI-MovGen Logo" class="home-logo-img" />
              <div class="home-logo-glow"></div>
            </div>
            <div>
              <div class="d-flex align-center gap-2">
                <h1 class="text-h4 font-weight-black title-gradient">AI-MovGen Studio</h1>
                <v-chip size="small" class="neon-pro-chip font-weight-bold ml-2">
                  <span class="pulse-dot mr-1"></span> PRO 3.0
                </v-chip>
              </div>
              <p class="text-body-2 text-medium-emphasis mt-1">
                シナリオ生成・AI音声合成・シーンレンダリングを統合した次世代AI動画制作スタジオ
              </p>
            </div>
          </div>

          <!-- クイックアクションボタン群 -->
          <div class="d-flex align-center gap-2">
            <v-btn
              :color="selectMode ? 'warning' : undefined"
              :variant="selectMode ? 'flat' : 'outlined'"
              prepend-icon="mdi-checkbox-multiple-marked-outline"
              class="glass-btn"
              @click="toggleSelectMode"
            >
              {{ selectMode ? '選択モード終了' : '選択モード' }}
            </v-btn>
            <v-btn
              prepend-icon="mdi-import"
              variant="outlined"
              class="glass-btn"
              @click="importDialog = true"
            >
              ZIP インポート
            </v-btn>
            <v-btn
              prepend-icon="mdi-plus-box"
              class="btn-neon-primary"
              elevation="4"
              @click="newProjectDialog = true"
            >
              新規プロジェクト
            </v-btn>
          </div>
        </div>

        <!-- ─── KPI / 統計サマリーウィジェット ─── -->
        <div class="stats-row mt-6 d-flex gap-4 flex-wrap">
          <div class="stat-glass-card flex-grow-1 pa-3 rounded-lg d-flex align-center gap-3">
            <div class="stat-icon-wrapper cyan">
              <v-icon size="22" color="#06b6d4">mdi-folder-multiple-outline</v-icon>
            </div>
            <div>
              <div class="text-caption text-medium-emphasis">総プロジェクト</div>
              <div class="text-h6 font-weight-bold">{{ store.projects.length }} <span class="text-caption text-medium-emphasis font-weight-normal">件</span></div>
            </div>
          </div>

          <div class="stat-glass-card flex-grow-1 pa-3 rounded-lg d-flex align-center gap-3">
            <div class="stat-icon-wrapper purple">
              <v-icon size="22" color="#c084fc">mdi-video-vintage</v-icon>
            </div>
            <div>
              <div class="text-caption text-medium-emphasis">作成動画総数</div>
              <div class="text-h6 font-weight-bold">{{ totalVideosCount }} <span class="text-caption text-medium-emphasis font-weight-normal">本</span></div>
            </div>
          </div>

          <div class="stat-glass-card flex-grow-1 pa-3 rounded-lg d-flex align-center gap-3">
            <div class="stat-icon-wrapper emerald">
              <v-icon size="22" color="#10b981">mdi-flash-outline</v-icon>
            </div>
            <div>
              <div class="text-caption text-medium-emphasis">AI 音声エンジン</div>
              <div class="text-body-2 font-weight-bold text-emerald">Qwen3-TTS 稼働中</div>
            </div>
          </div>

          <div class="stat-glass-card flex-grow-1 pa-3 rounded-lg d-flex align-center gap-3">
            <div class="stat-icon-wrapper indigo">
              <v-icon size="22" color="#818cf8">mdi-auto-fix</v-icon>
            </div>
            <div>
              <div class="text-caption text-medium-emphasis">シナリオ解析</div>
              <div class="text-body-2 font-weight-bold text-indigo">PPTX / テキスト / Chat</div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- ─── 検索 & フィルター & 表示切り替えツールバー ─── -->
    <div class="mb-5 d-flex align-center gap-3 flex-wrap">
      <!-- 選択モード時のツールバー -->
      <v-card v-if="selectMode" class="pa-3 flex-grow-1 d-flex align-center gap-3 glass-card" rounded>
        <span class="text-body-2 font-weight-bold text-cyan">
          <v-icon icon="mdi-check-circle-outline" class="mr-1" />
          {{ selectedIds.length }} 件選択中
        </span>
        <v-btn size="small" variant="text" @click="selectAll">全選択</v-btn>
        <v-btn size="small" variant="text" @click="clearSelection">全解除</v-btn>
        <v-spacer />
        <v-btn
          color="error"
          variant="flat"
          prepend-icon="mdi-delete-outline"
          size="small"
          :disabled="selectedIds.length === 0"
          @click="bulkDeleteDialog = true"
        >
          一括削除 ({{ selectedIds.length }} 件)
        </v-btn>
      </v-card>

      <!-- 通常時の検索・ソートバー -->
      <template v-else>
        <!-- 検索フィールド -->
        <div class="flex-grow-1" style="min-width: 260px;">
          <v-text-field
            v-model="searchQuery"
            prepend-inner-icon="mdi-magnify"
            label="プロジェクト名・説明文で検索"
            clearable
            hide-details
            density="comfortable"
            class="glass-search-input"
          />
        </div>

        <!-- ソート順セレクト -->
        <div style="width: 170px;">
          <v-select
            v-model="sortBy"
            :items="sortOptions"
            item-title="label"
            item-value="value"
            prepend-inner-icon="mdi-sort-variant"
            hide-details
            density="comfortable"
            class="glass-select"
          />
        </div>

        <!-- グリッド / リスト 表示切り替えトグル -->
        <v-btn-toggle
          v-model="viewMode"
          mandatory
          density="comfortable"
          variant="outlined"
          class="glass-toggle"
        >
          <v-btn value="grid" icon="mdi-view-grid-outline" title="グリッド表示" />
          <v-btn value="list" icon="mdi-view-list" title="リスト表示" />
        </v-btn-toggle>
      </template>
    </div>

    <!-- ─── プロジェクト一覧 (グリッド表示) ─── -->
    <v-row v-if="filteredAndSortedProjects.length && viewMode === 'grid'">
      <v-col
        v-for="project in filteredAndSortedProjects"
        :key="project.id"
        cols="12" sm="6" md="4" lg="3"
      >
        <v-card
          class="project-glass-card glass-card glass-card-interactive position-relative overflow-hidden d-flex flex-column"
          :class="{ 'is-selected': selectMode && isSelected(project.id) }"
          :to="selectMode ? undefined : { name: 'Project', params: { projectId: project.id } }"
          @click="selectMode ? toggleSelect(project.id) : undefined"
        >
          <!-- 選択モード用チェックボックス -->
          <div
            v-if="selectMode"
            class="position-absolute checkbox-overlay"
            @click.stop="toggleSelect(project.id)"
          >
            <v-checkbox-btn
              :model-value="isSelected(project.id)"
              color="primary"
              density="compact"
            />
          </div>

          <!-- カード上部: 16:9 サムネイルプレビュー領域 -->
          <div class="project-thumb-wrapper position-relative">
            <img :src="cardThumbUrl" alt="Project Visual" class="project-thumb-img" />
            <div class="project-thumb-gradient"></div>
            
            <!-- 動画本数バッジ -->
            <div class="thumb-badge-count position-absolute">
              <v-icon size="14" class="mr-1">mdi-movie-open-outline</v-icon>
              <span>{{ project.video_count ?? 0 }} 動画</span>
            </div>

            <!-- プロジェクト名頭文字シンボル -->
            <div class="thumb-initial-avatar position-absolute">
              {{ (project.name || 'P').charAt(0).toUpperCase() }}
            </div>
          </div>

          <!-- カードコンテンツ部 -->
          <div class="pa-4 d-flex flex-column flex-grow-1">
            <div class="d-flex align-start justify-space-between mb-1">
              <h3 class="text-subtitle-1 font-weight-bold text-truncate project-title" :title="project.name">
                {{ project.name }}
              </h3>
            </div>
            
            <p class="text-caption text-medium-emphasis line-clamp-2 mb-3 flex-grow-1" :title="project.description">
              {{ project.description || 'プロジェクトの説明はありません。' }}
            </p>

            <v-divider class="border-opacity-10 mb-2" />

            <!-- フッター部: アクションボタン -->
            <div class="d-flex align-center justify-space-between pt-1">
              <span class="text-xxs text-medium-emphasis">
                ID: {{ project.id.slice(0, 8) }}
              </span>

              <div class="d-flex align-center gap-1" v-if="!selectMode">
                <v-btn
                  icon="mdi-export-variant"
                  color="secondary"
                  variant="text"
                  size="small"
                  title="プロジェクトをZIPエクスポート"
                  @click.stop.prevent="handleExport(project)"
                />
                <v-btn
                  icon="mdi-delete-outline"
                  color="error"
                  variant="text"
                  size="small"
                  title="プロジェクトを削除"
                  @click.stop.prevent="confirmDelete(project)"
                />
              </div>
            </div>
          </div>
        </v-card>
      </v-col>
    </v-row>

    <!-- ─── プロジェクト一覧 (リスト表示) ─── -->
    <v-card v-else-if="filteredAndSortedProjects.length && viewMode === 'list'" class="glass-card overflow-hidden">
      <v-table class="bg-transparent cyber-table">
        <thead>
          <tr>
            <th v-if="selectMode" style="width: 50px;"></th>
            <th>プロジェクト名</th>
            <th>説明</th>
            <th style="width: 120px;">動画本数</th>
            <th style="width: 140px;" class="text-right">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="project in filteredAndSortedProjects"
            :key="project.id"
            class="cyber-table-row cursor-pointer"
            :class="{ 'is-selected': selectMode && isSelected(project.id) }"
            @click="selectMode ? toggleSelect(project.id) : $router.push({ name: 'Project', params: { projectId: project.id } })"
          >
            <td v-if="selectMode" @click.stop="toggleSelect(project.id)">
              <v-checkbox-btn
                :model-value="isSelected(project.id)"
                color="primary"
                density="compact"
              />
            </td>
            <td>
              <div class="d-flex align-center gap-3">
                <div class="list-thumb-mini">
                  <v-icon size="20" color="#06b6d4">mdi-folder-video-outline</v-icon>
                </div>
                <div class="font-weight-bold text-white">{{ project.name }}</div>
              </div>
            </td>
            <td class="text-medium-emphasis text-caption text-truncate" style="max-width: 300px;">
              {{ project.description || '—' }}
            </td>
            <td>
              <v-chip size="x-small" variant="tonal" color="primary">
                {{ project.video_count ?? 0 }} 本
              </v-chip>
            </td>
            <td class="text-right" @click.stop>
              <template v-if="!selectMode">
                <v-btn
                  icon="mdi-export-variant"
                  color="secondary"
                  variant="text"
                  size="small"
                  title="エクスポート"
                  @click.prevent="handleExport(project)"
                />
                <v-btn
                  icon="mdi-delete-outline"
                  color="error"
                  variant="text"
                  size="small"
                  title="削除"
                  @click.prevent="confirmDelete(project)"
                />
              </template>
            </td>
          </tr>
        </tbody>
      </v-table>
    </v-card>

    <!-- ─── 空状態: 検索にヒットしない場合 ─── -->
    <div v-else-if="searchQuery && store.projects.length" class="empty-state-wrapper text-center py-16">
      <div class="empty-icon-glow mb-4">
        <v-icon size="64" color="#06b6d4">mdi-magnify</v-icon>
      </div>
      <h3 class="text-h6 font-weight-bold">一致するプロジェクトが見つかりません</h3>
      <p class="text-body-2 text-medium-emphasis mt-2 mb-4">
        「{{ searchQuery }}」に一致するプロジェクトはありませんでした。検索語句を変更してください。
      </p>
      <v-btn variant="outlined" color="primary" @click="searchQuery = ''">
        検索条件をクリア
      </v-btn>
    </div>

    <!-- ─── 空状態: プロジェクトが1件もない場合 (AIアート導入) ─── -->
    <div v-else class="empty-project-showcase glass-card pa-8 pa-md-12 text-center rounded-xl mx-auto my-8">
      <div class="empty-art-container position-relative mb-6">
        <img :src="emptyProjectsArtUrl" alt="Empty Projects Canvas" class="empty-art-img" />
        <div class="empty-art-glow"></div>
      </div>
      <h2 class="text-h5 font-weight-bold mb-2">クリエイティブな動画制作を始めましょう</h2>
      <p class="text-body-2 text-medium-emphasis mb-6" style="max-width: 540px; margin: 0 auto;">
        まだ作成されたプロジェクトはありません。AIによるシナリオ生成、スライド構成、高品質な音声合成を組み合わせて、魅力的で高品質な動画を瞬時に作成できます。
      </p>
      <div class="d-flex align-center justify-center gap-3">
        <v-btn
          prepend-icon="mdi-plus-box"
          class="btn-neon-primary px-6"
          size="large"
          @click="newProjectDialog = true"
        >
          最初のプロジェクトを作成
        </v-btn>
        <v-btn
          prepend-icon="mdi-import"
          variant="outlined"
          size="large"
          class="glass-btn"
          @click="importDialog = true"
        >
          ZIPからインポート
        </v-btn>
      </div>
    </div>

    <!-- ─── 新規プロジェクト作成ダイアログ ─── -->
    <v-dialog v-model="newProjectDialog" max-width="520">
      <v-card class="glass-card pa-2">
        <v-card-title class="pa-4 d-flex align-center gap-2">
          <v-icon color="#06b6d4">mdi-folder-plus-outline</v-icon>
          <span class="font-weight-bold">新規プロジェクト作成</span>
        </v-card-title>
        <v-card-text class="pa-4 pt-0">
          <p class="text-caption text-medium-emphasis mb-4">
            制作する動画を管理するためのプロジェクト名と説明を入力してください。
          </p>
          <v-text-field
            v-model="newProject.name"
            label="プロジェクト名"
            placeholder="例: サービス紹介動画 2026"
            autofocus
            class="mb-3"
            :rules="[v => !!v || 'プロジェクト名は必須です']"
          />
          <v-textarea
            v-model="newProject.description"
            label="説明（任意）"
            placeholder="プロジェクトの目的やターゲットなどを入力できます"
            rows="3"
          />
        </v-card-text>
        <v-card-actions class="pa-4 pt-0">
          <v-spacer />
          <v-btn variant="text" @click="newProjectDialog = false">キャンセル</v-btn>
          <v-btn
            class="btn-neon-primary"
            :disabled="!newProject.name.trim()"
            @click="handleCreate"
          >
            作成する
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- ─── 個別削除確認ダイアログ ─── -->
    <v-dialog v-model="deleteDialog" max-width="420">
      <v-card class="glass-card pa-2">
        <v-card-title class="pa-4 d-flex align-center gap-2 text-error">
          <v-icon color="error">mdi-alert-circle-outline</v-icon>
          <span class="font-weight-bold">プロジェクトを削除</span>
        </v-card-title>
        <v-card-text class="pa-4 pt-0">
          プロジェクト「<strong>{{ projectToDelete?.name }}</strong>」を削除すると、含まれるすべての動画・シーン・レンダリングファイルが物理的に削除されます。<br />
          この操作は取り消せません。
        </v-card-text>
        <v-card-actions class="pa-4">
          <v-spacer />
          <v-btn variant="text" @click="deleteDialog = false">キャンセル</v-btn>
          <v-btn color="error" variant="flat" @click="handleDelete">削除する</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- ─── 一括削除確認ダイアログ ─── -->
    <v-dialog v-model="bulkDeleteDialog" max-width="420">
      <v-card class="glass-card pa-2">
        <v-card-title class="pa-4 d-flex align-center gap-2 text-error">
          <v-icon color="error">mdi-delete-sweep</v-icon>
          <span class="font-weight-bold">一括削除の確認</span>
        </v-card-title>
        <v-card-text class="pa-4 pt-0">
          選択した <strong class="text-error">{{ selectedIds.length }} 件</strong> のプロジェクトをすべて削除します。<br />
          紐づく動画・音声・スライド画像も完全に消去されます。
        </v-card-text>
        <v-card-actions class="pa-4">
          <v-spacer />
          <v-btn variant="text" :disabled="bulkDeleting" @click="bulkDeleteDialog = false">
            キャンセル
          </v-btn>
          <v-btn color="error" variant="flat" :loading="bulkDeleting" @click="handleBulkDelete">
            {{ selectedIds.length }} 件を完全に削除
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- ─── ZIP インポートダイアログ ─── -->
    <v-dialog v-model="importDialog" max-width="500">
      <v-card class="glass-card pa-2">
        <v-card-title class="pa-4 d-flex align-center gap-2">
          <v-icon color="#06b6d4">mdi-zip-box</v-icon>
          <span class="font-weight-bold">プロジェクトのインポート</span>
        </v-card-title>
        <v-card-text class="pa-4 pt-0">
          <p class="text-body-2 text-medium-emphasis mb-4">
            以前エクスポートした ZIP ファイルを選択してください。新しいプロジェクトとしてスタジオに復元されます。
          </p>
          <v-file-input
            v-model="importFile"
            label="ZIP ファイルを選択"
            accept=".zip"
            prepend-icon="mdi-paperclip"
            show-size
          />
        </v-card-text>
        <v-card-actions class="pa-4 pt-0">
          <v-spacer />
          <v-btn variant="text" @click="importDialog = false">キャンセル</v-btn>
          <v-btn
            class="btn-neon-primary"
            :loading="importing"
            :disabled="!importFile"
            @click="handleImport"
          >
            インポート実行
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-container>
</template>

<script setup>
/**
 * HomeView.vue - ホーム画面（ダッシュボード＆プロジェクト管理）
 * Cyber Studio / Neon Glass テーマに合わせたリッチなUI/UXを提供
 */
import { ref, reactive, computed, onMounted } from 'vue'
import { useProjectsStore } from '@/stores/projects'
import { useUiStore } from '@/stores/ui'
import { api } from '@/api/index.js'

// アセット画像
import logoUrl from '@/assets/logo.jpg'
import heroBannerUrl from '@/assets/hero_banner_art.jpg'
import cardThumbUrl from '@/assets/card_thumb_default.jpg'
import emptyProjectsArtUrl from '@/assets/empty_projects_art.jpg'

const store = useProjectsStore()
const ui = useUiStore()

// ─── 画面ステート ──────────────────────────────────────────
const newProjectDialog = ref(false)
const deleteDialog = ref(false)
const projectToDelete = ref(null)
const newProject = reactive({ name: '', description: '' })
const importDialog = ref(false)
const importFile = ref(null)
const importing = ref(false)

// ─── 表示切り替え & ソート ───────────────────────────────
const viewMode = ref('grid') // 'grid' | 'list'
const sortBy = ref('updated_desc')
const sortOptions = [
  { label: '最新順', value: 'updated_desc' },
  { label: '名前順 (A-Z)', value: 'name_asc' },
  { label: '動画数が多い順', value: 'videos_desc' },
]

// ─── 検索 & フィルター計算 ───────────────────────────────
const searchQuery = ref('')

const totalVideosCount = computed(() => {
  return store.projects.reduce((acc, p) => acc + (p.video_count || 0), 0)
})

const filteredAndSortedProjects = computed(() => {
  let list = [...store.projects]
  
  // 検索クエリでフィルタリング
  const q = searchQuery.value.trim().toLowerCase()
  if (q) {
    list = list.filter(p =>
      (p.name && p.name.toLowerCase().includes(q)) ||
      (p.description && p.description.toLowerCase().includes(q))
    )
  }

  // ソート順の適用
  if (sortBy.value === 'name_asc') {
    list.sort((a, b) => (a.name || '').localeCompare(b.name || ''))
  } else if (sortBy.value === 'videos_desc') {
    list.sort((a, b) => (b.video_count || 0) - (a.video_count || 0))
  }

  return list
})

// ─── 選択モード / 一括削除 ───────────────────────────────
const selectMode = ref(false)
const selectedIds = ref([])
const bulkDeleteDialog = ref(false)
const bulkDeleting = ref(false)

function isSelected(id) {
  return selectedIds.value.includes(id)
}

function toggleSelect(id) {
  const idx = selectedIds.value.indexOf(id)
  if (idx === -1) {
    selectedIds.value.push(id)
  } else {
    selectedIds.value.splice(idx, 1)
  }
}

function selectAll() {
  selectedIds.value = filteredAndSortedProjects.value.map(p => p.id)
}

function clearSelection() {
  selectedIds.value = []
}

function toggleSelectMode() {
  selectMode.value = !selectMode.value
  if (!selectMode.value) {
    selectedIds.value = []
  }
}

async function handleBulkDelete() {
  const targets = [...selectedIds.value]
  bulkDeleting.value = true
  try {
    for (const id of targets) {
      await store.remove(id)
    }
    bulkDeleteDialog.value = false
    selectedIds.value = []
    selectMode.value = false
    ui.notify(`${targets.length} 件のプロジェクトを削除しました`)
  } catch (e) {
    ui.notifyError('削除中にエラーが発生しました: ' + e.message)
  } finally {
    bulkDeleting.value = false
  }
}

// ─── プロジェクト操作ハンドラ ────────────────────────────
onMounted(() => {
  store.fetchAll()
})

async function handleCreate() {
  if (!newProject.name.trim()) return
  await store.create({ ...newProject })
  newProject.name = ''
  newProject.description = ''
  newProjectDialog.value = false
}

function confirmDelete(project) {
  projectToDelete.value = project
  deleteDialog.value = true
}

async function handleDelete() {
  if (projectToDelete.value) {
    await store.remove(projectToDelete.value.id)
    deleteDialog.value = false
    projectToDelete.value = null
  }
}

function handleExport(project) {
  window.location.href = `/api/v1/projects/${project.id}/export`
}

async function handleImport() {
  if (!importFile.value) return
  importing.value = true
  try {
    const formData = new FormData()
    const file = Array.isArray(importFile.value) ? importFile.value[0] : importFile.value
    formData.append('file', file)
    await api.post('/projects/import', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 60_000,
    })
    importDialog.value = false
    importFile.value = null
    await store.fetchAll()
    ui.notify('プロジェクトをインポートしました')
  } catch (e) {
    console.error('インポートエラー:', e)
    ui.notifyError('インポートに失敗しました: ' + e.message)
  } finally {
    importing.value = false
  }
}
</script>

<style scoped>
.home-container {
  max-width: 1600px;
  margin: 0 auto;
}

/* ─── ヒーローバナー ─── */
.hero-studio-card {
  min-height: 220px;
  border-radius: 20px !important;
  border: 1px solid rgba(6, 182, 212, 0.25) !important;
  box-shadow: 
    0 20px 48px -10px rgba(0, 0, 0, 0.7),
    0 0 30px 0 rgba(6, 182, 212, 0.15) !important;
}

.hero-banner-image {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  opacity: 0.22;
  filter: saturate(140%) contrast(110%);
}

.hero-bg-overlay {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: linear-gradient(90deg, rgba(9, 10, 20, 0.95) 0%, rgba(15, 23, 42, 0.85) 50%, rgba(9, 10, 20, 0.9) 100%);
  z-index: 1;
}

.hero-content {
  z-index: 2;
  height: 100%;
}

.title-gradient {
  background: linear-gradient(135deg, #ffffff 10%, #22d3ee 65%, #c084fc 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  letter-spacing: -0.5px;
}

.neon-pro-chip {
  background: rgba(6, 182, 212, 0.15) !important;
  border: 1px solid rgba(6, 182, 212, 0.4) !important;
  color: #22d3ee !important;
}

/* ─── KPI スタッツカード ─── */
.stat-glass-card {
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.08);
  backdrop-filter: blur(10px);
  min-width: 180px;
  transition: all 0.2s ease;
}
.stat-glass-card:hover {
  background: rgba(255, 255, 255, 0.07);
  border-color: rgba(6, 182, 212, 0.3);
  transform: translateY(-2px);
}

.stat-icon-wrapper {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.stat-icon-wrapper.cyan {
  background: rgba(6, 182, 212, 0.15);
  box-shadow: 0 0 12px rgba(6, 182, 212, 0.2);
}
.stat-icon-wrapper.purple {
  background: rgba(168, 85, 247, 0.15);
  box-shadow: 0 0 12px rgba(168, 85, 247, 0.2);
}
.stat-icon-wrapper.emerald {
  background: rgba(16, 185, 129, 0.15);
  box-shadow: 0 0 12px rgba(16, 185, 129, 0.2);
}
.stat-icon-wrapper.indigo {
  background: rgba(99, 102, 241, 0.15);
  box-shadow: 0 0 12px rgba(99, 102, 241, 0.2);
}

.text-emerald {
  color: #10b981 !important;
}
.text-indigo {
  color: #818cf8 !important;
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
.glass-btn {
  background: rgba(255, 255, 255, 0.05) !important;
  border: 1px solid rgba(255, 255, 255, 0.12) !important;
}

/* ─── プロジェクトカード (グリッド) ─── */
.project-glass-card {
  height: 100%;
  border-radius: 16px !important;
  border: 1px solid rgba(255, 255, 255, 0.08) !important;
  transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1) !important;
}
.project-glass-card.is-selected {
  border-color: #06b6d4 !important;
  box-shadow: 0 0 20px rgba(6, 182, 212, 0.35) !important;
}

.project-thumb-wrapper {
  width: 100%;
  height: 140px;
  overflow: hidden;
}
.project-thumb-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  transition: transform 0.4s ease;
}
.project-glass-card:hover .project-thumb-img {
  transform: scale(1.08);
}
.project-thumb-gradient {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 70%;
  background: linear-gradient(to top, rgba(19, 22, 40, 0.95), transparent);
}
.thumb-badge-count {
  top: 10px;
  right: 10px;
  background: rgba(9, 10, 20, 0.75);
  backdrop-filter: blur(8px);
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 20px;
  padding: 2px 10px;
  font-size: 0.72rem;
  font-weight: 600;
  color: #22d3ee;
  display: flex;
  align-items: center;
}
.thumb-initial-avatar {
  bottom: 8px;
  left: 14px;
  width: 36px;
  height: 36px;
  border-radius: 10px;
  background: linear-gradient(135deg, #06b6d4, #a855f7);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 800;
  font-size: 1rem;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.5);
}

.project-title {
  color: #f1f5f9;
  letter-spacing: -0.2px;
}
.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  min-height: 2.4em;
}
.checkbox-overlay {
  top: 8px;
  left: 8px;
  z-index: 5;
  background: rgba(9, 10, 20, 0.7);
  border-radius: 8px;
}

/* ─── リスト表示用テーブル ─── */
.cyber-table {
  color: #cbd5e1 !important;
}
.cyber-table th {
  color: rgba(255, 255, 255, 0.6) !important;
  font-weight: 600 !important;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08) !important;
}
.cyber-table-row {
  transition: background 0.15s ease;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05) !important;
}
.cyber-table-row:hover {
  background: rgba(255, 255, 255, 0.04) !important;
}
.list-thumb-mini {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  background: rgba(6, 182, 212, 0.12);
  display: flex;
  align-items: center;
  justify-content: center;
}

/* ─── エンプティステート表示 ─── */
.empty-project-showcase {
  max-width: 680px;
  border: 1px dashed rgba(6, 182, 212, 0.3) !important;
}
.empty-art-container {
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
</style>
