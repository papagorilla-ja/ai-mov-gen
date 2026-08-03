<template>
  <v-container fluid class="pa-6">
    <!-- ヘッダー行 (グラスモーフィズム ブランドヘッダー) -->
    <div class="d-flex align-center mb-6 glass-card pa-4 px-6 rounded-xl home-header-banner">
      <div class="d-flex align-center">
        <div class="home-logo-wrapper mr-4">
          <img :src="logoUrl" alt="AI-MovGen Logo" class="home-logo-img" />
          <div class="home-logo-glow"></div>
        </div>
        <div>
          <div class="d-flex align-center gap-2">
            <h1 class="text-h5 font-weight-bold title-gradient">AI-MovGen</h1>
            <v-chip size="x-small" color="primary" variant="flat" class="font-weight-bold ml-1">PRO</v-chip>
          </div>
          <p class="text-body-2 text-medium-emphasis mt-1">動画プロジェクトを管理・作成します</p>
        </div>
      </div>
      <v-spacer />
      <v-btn
        :color="selectMode ? 'warning' : 'default'"
        :variant="selectMode ? 'flat' : 'outlined'"
        prepend-icon="mdi-checkbox-multiple-marked-outline"
        class="mr-2"
        @click="toggleSelectMode"
      >
        {{ selectMode ? '選択モード終了' : '選択モード' }}
      </v-btn>
      <v-btn prepend-icon="mdi-plus" color="primary" class="mr-2 btn-gradient" @click="newProjectDialog = true">
        新規プロジェクト
      </v-btn>
      <v-btn prepend-icon="mdi-import" variant="outlined" @click="importDialog = true">
        ZIP インポート
      </v-btn>
    </div>

    <!-- 検索バー / 選択ツールバー -->
    <div class="mb-4">
      <!-- 通常時: 検索バー -->
      <v-text-field
        v-if="!selectMode"
        v-model="searchQuery"
        prepend-inner-icon="mdi-magnify"
        label="プロジェクトを検索"
        clearable
        hide-details
        density="compact"
        variant="outlined"
        class="glass-card"
      />

      <!-- 選択モード時: 選択ツールバー -->
      <v-card v-else class="pa-3 d-flex align-center gap-3 glass-card" rounded>
        <span class="text-body-2 font-weight-bold">
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
    </div>

    <!-- プロジェクトカード一覧 -->
    <v-row v-if="filteredProjects.length">
      <v-col
        v-for="project in filteredProjects"
        :key="project.id"
        cols="12" sm="6" md="4" lg="3"
      >
        <v-card
          class="glass-card glass-card-interactive position-relative"
          :class="{ 'border-primary border-opacity-100': selectMode && isSelected(project.id) }"
          :style="selectMode && isSelected(project.id) ? 'border: 2px solid rgb(var(--v-theme-primary));' : ''"
          :to="selectMode ? undefined : { name: 'Project', params: { projectId: project.id } }"
          @click="selectMode ? toggleSelect(project.id) : undefined"
        >
          <!-- 選択モード: チェックボックスオーバーレイ -->
          <div
            v-if="selectMode"
            class="position-absolute"
            style="top: 6px; left: 6px; z-index: 2;"
            @click.stop="toggleSelect(project.id)"
          >
            <v-checkbox-btn
              :model-value="isSelected(project.id)"
              color="primary"
              density="compact"
            />
          </div>

          <div class="d-flex flex-column" style="height: 100%;">
            <v-card-item>
              <template v-slot:prepend>
                <v-icon size="40" class="mr-3" color="primary">mdi-folder-video-outline</v-icon>
              </template>
              <v-card-title class="font-weight-bold">{{ project.name }}</v-card-title>
              <v-card-subtitle>{{ project.description || '説明なし' }}</v-card-subtitle>
            </v-card-item>
            <v-card-text class="text-caption text-medium-emphasis pb-0">
              {{ project.video_count ?? 0 }} 本の動画
            </v-card-text>
            <v-card-actions class="justify-end">
              <template v-if="!selectMode">
                <v-btn
                  icon="mdi-export"
                  color="secondary"
                  variant="text"
                  size="small"
                  @click.stop.prevent="handleExport(project)"
                />
                <v-btn
                  icon="mdi-delete-outline"
                  color="error"
                  variant="text"
                  size="small"
                  @click.stop.prevent="confirmDelete(project)"
                />
              </template>
            </v-card-actions>
          </div>
        </v-card>
      </v-col>
    </v-row>

    <!-- 空状態: 検索にヒットしない場合 -->
    <div v-else-if="searchQuery && store.projects.length" class="text-center py-16">
      <v-icon size="64" color="medium-emphasis">mdi-magnify</v-icon>
      <p class="text-body-1 text-medium-emphasis mt-4">
        「{{ searchQuery }}」に一致するプロジェクトが見つかりませんでした。
      </p>
    </div>

    <!-- 空状態: プロジェクトがない場合 -->
    <div v-else class="text-center py-16">
      <v-icon size="64" color="medium-emphasis">mdi-folder-open-outline</v-icon>
      <p class="text-body-1 text-medium-emphasis mt-4">
        まだプロジェクトがありません。<br />「新規プロジェクト」から作成してください。
      </p>
    </div>

    <!-- 新規プロジェクト作成ダイアログ -->
    <v-dialog v-model="newProjectDialog" max-width="480">
      <v-card>
        <v-card-title class="pa-4">新規プロジェクト</v-card-title>
        <v-card-text>
          <v-text-field v-model="newProject.name" label="プロジェクト名" autofocus />
          <v-textarea v-model="newProject.description" label="説明（任意）" rows="3" />
        </v-card-text>
        <v-card-actions class="pa-4 pt-0">
          <v-spacer />
          <v-btn @click="newProjectDialog = false">キャンセル</v-btn>
          <v-btn color="primary" :disabled="!newProject.name" @click="handleCreate">作成</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- 個別削除確認ダイアログ -->
    <v-dialog v-model="deleteDialog" max-width="400">
      <v-card>
        <v-card-title class="text-h6 pa-4">プロジェクトを削除しますか？</v-card-title>
        <v-card-text>
          プロジェクト「{{ projectToDelete?.name }}」を削除すると、紐づくすべての動画および物理ファイルが削除されます。この操作は取り消せません。
        </v-card-text>
        <v-card-actions class="pa-4">
          <v-spacer />
          <v-btn variant="text" @click="deleteDialog = false">キャンセル</v-btn>
          <v-btn color="error" variant="flat" @click="handleDelete">削除する</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- 一括削除確認ダイアログ -->
    <v-dialog v-model="bulkDeleteDialog" max-width="400">
      <v-card>
        <v-card-title class="text-h6 pa-4">一括削除の確認</v-card-title>
        <v-card-text>
          選択した <strong>{{ selectedIds.length }} 件</strong>のプロジェクトをすべて削除します。
          紐づく動画・物理ファイルも含めて削除され、取り消せません。
        </v-card-text>
        <v-card-actions class="pa-4">
          <v-spacer />
          <v-btn variant="text" :disabled="bulkDeleting" @click="bulkDeleteDialog = false">
            キャンセル
          </v-btn>
          <v-btn color="error" variant="flat" :loading="bulkDeleting" @click="handleBulkDelete">
            {{ selectedIds.length }} 件を削除する
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- ZIP インポートダイアログ -->
    <v-dialog v-model="importDialog" max-width="480">
      <v-card>
        <v-card-title class="pa-4">プロジェクトのインポート</v-card-title>
        <v-card-text>
          <p class="text-body-2 text-medium-emphasis mb-4">
            エクスポートした ZIP ファイルを選択してください。新しいプロジェクトとして追加されます。
          </p>
          <v-file-input
            v-model="importFile"
            label="ZIP ファイルを選択"
            accept=".zip"
            prepend-icon="mdi-zip-box"
            show-size
          />
        </v-card-text>
        <v-card-actions class="pa-4 pt-0">
          <v-spacer />
          <v-btn variant="text" @click="importDialog = false">キャンセル</v-btn>
          <v-btn
            color="primary"
            :loading="importing"
            :disabled="!importFile"
            @click="handleImport"
          >
            インポート
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-container>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useProjectsStore } from '@/stores/projects'
import { useUiStore } from '@/stores/ui'
import { api } from '@/api/index.js'
import logoUrl from '@/assets/logo.jpg'

const store = useProjectsStore()
const ui = useUiStore()

// ─── 既存 state ──────────────────────────────────────────
const newProjectDialog = ref(false)
const deleteDialog = ref(false)
const projectToDelete = ref(null)
const newProject = reactive({ name: '', description: '' })
const importDialog = ref(false)
const importFile = ref(null)
const importing = ref(false)

// ─── 検索 ────────────────────────────────────────────────
const searchQuery = ref('')

const filteredProjects = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  if (!q) return store.projects
  return store.projects.filter(p =>
    p.name.toLowerCase().includes(q) ||
    (p.description || '').toLowerCase().includes(q)
  )
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
  selectedIds.value = filteredProjects.value.map(p => p.id)
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
  const targets = [...selectedIds.value]  // コピーして削除中の変更を防ぐ
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

// ─── 既存関数（変更なし） ─────────────────────────────────
onMounted(() => {
  store.fetchAll()
})

async function handleCreate() {
  if (!newProject.name) return
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
.home-header-banner {
  background: rgba(26, 26, 46, 0.45) !important;
  border: 1px solid rgba(255, 255, 255, 0.08) !important;
  box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3), inset 0 1px 0 0 rgba(255, 255, 255, 0.1) !important;
}

.home-logo-wrapper {
  position: relative;
  width: 48px;
  height: 48px;
}

.home-logo-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  border-radius: 14px;
  border: 1px solid rgba(255, 255, 255, 0.25);
  box-shadow: 0 4px 20px rgba(34, 211, 238, 0.35), 0 0 10px rgba(139, 92, 246, 0.25);
  position: relative;
  z-index: 2;
  transition: transform 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.home-logo-wrapper:hover .home-logo-img {
  transform: scale(1.08) rotate(3deg);
}

.home-logo-glow {
  position: absolute;
  top: -4px;
  left: -4px;
  right: -4px;
  bottom: -4px;
  background: linear-gradient(135deg, rgba(34, 211, 238, 0.6), rgba(168, 85, 247, 0.6));
  border-radius: 16px;
  filter: blur(8px);
  opacity: 0.7;
  z-index: 1;
}

.title-gradient {
  background: linear-gradient(135deg, #ffffff 0%, #22d3ee 50%, #c084fc 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.btn-gradient {
  background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%) !important;
  color: #ffffff !important;
  font-weight: 700 !important;
  box-shadow: 0 4px 14px 0 rgba(99, 102, 241, 0.5) !important;
}

.btn-gradient :deep(.v-btn__content),
.btn-gradient :deep(.v-icon) {
  color: #ffffff !important;
}
</style>
