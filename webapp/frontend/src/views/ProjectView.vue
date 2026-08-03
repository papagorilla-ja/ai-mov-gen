<template>
  <v-container fluid class="pa-6">
    <v-btn
      variant="text"
      prepend-icon="mdi-arrow-left"
      class="mb-4"
      :to="{ path: '/' }"
    >
      プロジェクト一覧
    </v-btn>

    <div class="d-flex align-center mb-6">
      <div>
        <h1 class="text-h5 font-weight-bold">{{ projectStore.currentProject?.name ?? '読み込み中...' }}</h1>
        <p class="text-body-2 text-medium-emphasis mt-1">{{ projectStore.currentProject?.description }}</p>
      </div>
      <v-spacer />
      <v-btn prepend-icon="mdi-plus" color="primary" @click="newVideoDialog = true">
        新しい動画を作成
      </v-btn>
    </div>

    <!-- 動画カード一覧 -->
    <v-row v-if="videoStore.videos.length">
      <v-col v-for="video in videoStore.videos" :key="video.id" cols="12" sm="6" md="4">
        <v-card class="glass-card glass-card-interactive" :to="{ name: 'VideoEditor', params: { videoId: video.id } }">
          <div class="d-flex flex-column" style="height: 100%;">
            <v-card-item>
              <template v-slot:prepend>
                <v-icon size="40" class="mr-3" color="secondary">mdi-video-outline</v-icon>
              </template>
              <v-card-title class="font-weight-bold">{{ video.name }}</v-card-title>
              <v-card-subtitle>
                <v-chip :color="statusColor(video.status)" size="x-small" class="text-uppercase font-weight-bold">
                  {{ video.status }}
                </v-chip>
              </v-card-subtitle>
            </v-card-item>
            <v-card-text class="text-caption text-medium-emphasis pb-0">
              長さ: {{ video.duration_sec ? `${video.duration_sec.toFixed(1)} 秒` : '未生成' }}
            </v-card-text>
            <v-card-actions class="justify-end">
              <v-btn icon="mdi-content-duplicate" color="secondary" variant="text" size="small" title="複製" @click.stop.prevent="handleDuplicate(video.id)" />
              <v-btn icon="mdi-delete-outline" color="error" variant="text" size="small" title="削除" @click.stop.prevent="confirmDelete(video)" />
            </v-card-actions>
          </div>
        </v-card>
      </v-col>
    </v-row>

    <div v-else class="text-center py-16">
      <v-icon size="64" color="medium-emphasis">mdi-video-outline</v-icon>
      <p class="text-body-1 text-medium-emphasis mt-4">
        まだ動画がありません。「新しい動画を作成」から始めてください。
      </p>
    </div>

    <!-- 新しい動画作成ダイアログ -->
    <v-dialog v-model="newVideoDialog" max-width="480">
      <v-card>
        <v-card-title class="pa-4">新しい動画</v-card-title>
        <v-card-text>
          <v-text-field v-model="newVideo.name" label="動画名" autofocus />
        </v-card-text>
        <v-card-actions class="pa-4 pt-0">
          <v-spacer />
          <v-btn @click="newVideoDialog = false">キャンセル</v-btn>
          <v-btn color="primary" :disabled="!newVideo.name" @click="handleCreateVideo">作成</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- 動画削除確認ダイアログ -->
    <v-dialog v-model="deleteDialog" max-width="400">
      <v-card>
        <v-card-title class="text-h6 pa-4">動画を削除しますか？</v-card-title>
        <v-card-text>
          動画「{{ videoToDelete?.name }}」およびその生成ファイルが削除されます。この操作は取り消せません。
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
import { ref, reactive, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useProjectsStore } from '@/stores/projects'
import { useVideosStore } from '@/stores/videos'

const route = useRoute()
const projectId = route.params.projectId

const projectStore = useProjectsStore()
const videoStore = useVideosStore()

const newVideoDialog = ref(false)
const deleteDialog = ref(false)
const videoToDelete = ref(null)
const newVideo = reactive({ name: '' })

onMounted(async () => {
  await projectStore.fetchOne(projectId)
  await videoStore.fetchAll(projectId)
})

async function handleCreateVideo() {
  if (!newVideo.name) return
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

function statusColor(status) {
  return { draft: 'default', generating: 'warning', completed: 'success', failed: 'error' }[status] ?? 'default'
}
</script>
