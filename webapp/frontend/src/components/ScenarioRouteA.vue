<template>
  <div class="pa-4 glass-panel">
    <h3 class="text-subtitle-1 font-weight-bold mb-3">📄 PPTX から取り込む</h3>

    <!-- ファイルアップロード領域 -->
    <v-file-input
      v-model="file"
      label="PPTX ファイルを選択"
      accept=".pptx"
      prepend-icon="mdi-presentation"
      outlined
      dense
      class="mb-4 glass-card"
      hide-details
    />

    <v-btn
      color="primary"
      :disabled="!file"
      :loading="scenarioStore.loading"
      block
      class="mb-4"
      @click="generateFromPptx"
    >
      シナリオを生成する
    </v-btn>

    <!-- 解析中の進捗（同期処理: シーン構成をすぐ確定） -->
    <div v-if="scenarioStore.loading" class="mb-4">
      <div class="text-caption text-medium-emphasis mb-1">PPTXを解析中...</div>
      <v-progress-linear color="primary" indeterminate height="6" rounded />
    </div>

    <!-- ナレーション生成ジョブの進捗（非同期: シーンごとに1回ずつLLMを呼ぶ） -->
    <div v-if="narrationJob && narrationJob.status === 'processing'" class="mb-4">
      <div class="text-caption text-medium-emphasis mb-1">
        ナレーションを生成中... ({{ narrationJob.done }} / {{ narrationJob.total }})
        <span v-if="narrationJob.current_title">— {{ narrationJob.current_title }}</span>
      </div>
      <v-progress-linear
        color="primary"
        :model-value="narrationJob.total ? (narrationJob.done / narrationJob.total) * 100 : 0"
        height="6"
        rounded
      />
    </div>
    <v-alert v-else-if="narrationJob && narrationJob.status === 'error'" type="warning" density="compact" class="mb-4">
      ナレーション生成中にエラーが発生しました: {{ narrationJob.error }}
    </v-alert>

    <!-- 取り込みサマリ -->
    <div v-if="importResult" class="mb-4 text-caption text-medium-emphasis">
      スライド数: {{ importResult.slide_count }} / 取り込んだ画像・図解: {{ importResult.visual_count }}
    </div>

    <!-- 警告 -->
    <v-alert
      v-if="importResult && importResult.warnings && importResult.warnings.length > 0"
      type="warning"
      density="compact"
      variant="tonal"
      class="mb-4"
    >
      <div v-for="(w, i) in importResult.warnings" :key="i">{{ w }}</div>
    </v-alert>

    <!-- 生成結果プレビュー -->
    <div v-if="previewScenes.length > 0" class="mt-4">
      <div class="text-subtitle-2 font-weight-bold mb-2">生成結果プレビュー（{{ previewScenes.length }}シーン）</div>
      <v-card
        v-for="scene in previewScenes"
        :key="scene.index"
        class="mb-2 glass-card border-thin"
        variant="outlined"
      >
        <v-card-item>
          <div class="d-flex justify-between align-center mb-1">
            <span class="text-caption font-weight-bold text-primary">シーン {{ scene.index }}</span>
            <v-chip size="x-small" color="secondary" variant="outlined">{{ scene.layout_hint }}</v-chip>
          </div>
          <div class="text-body-2 font-weight-bold mb-1">{{ scene.title }}</div>

          <div v-if="scene.thumbnails.length > 0" class="d-flex ga-2 mb-2 flex-wrap">
            <v-img
              v-for="(thumb, tIdx) in scene.thumbnails"
              :key="tIdx"
              :src="thumb"
              width="96"
              height="72"
              cover
              class="rounded border-thin"
            />
          </div>

          <div class="text-caption text-medium-emphasis mb-1">
            ナレーション: {{ scene.narration_draft || '(生成中...)' }}
          </div>
          <div v-if="scene.key_points && scene.key_points.length > 0" class="text-caption">
            要点:
            <ul class="pl-4">
              <li v-for="(kp, kIdx) in scene.key_points" :key="kIdx">{{ kp }}</li>
            </ul>
          </div>
        </v-card-item>
      </v-card>

      <v-btn
        color="success"
        block
        class="mt-4"
        @click="finalize"
      >
        このシナリオでシーンを作成する
      </v-btn>
    </div>
  </div>
</template>

<script setup>
import { ref, onBeforeUnmount } from 'vue'
import { useScenarioStore } from '@/stores/scenario'
import { useUiStore } from '@/stores/ui'
import { api } from '@/api/index.js'
import { scenarioApi } from '@/api/scenario.js'
import { assetApi } from '@/api/asset.js'

const props = defineProps({
  videoId: {
    type: String,
    required: true
  }
})

const emit = defineEmits(['finalized'])

const scenarioStore = useScenarioStore()
const ui = useUiStore()

const file = ref(null)
const previewScenes = ref([])
const importResult = ref(null)
const narrationJob = ref(null)
let pollTimer = null

const stopPolling = () => {
  if (pollTimer) {
    clearTimeout(pollTimer)
    pollTimer = null
  }
}

const buildPreviewScenes = async () => {
  const { data: scenes } = await api.get(`/videos/${props.videoId}/scenes`)
  const withAssets = await Promise.all(scenes.map(async (s) => {
    let keyPoints = []
    const layoutHint = s.layout_type
    try {
      const content = JSON.parse(s.slide_content_json || '{}')
      if (Array.isArray(content.bullet_points)) keyPoints = content.bullet_points
      else if (typeof content.bullet_points === 'string') keyPoints = content.bullet_points.split('\n').filter(Boolean)
      else if (content.headers && content.rows) keyPoints = [`表: ${content.headers.join(' / ')}`]
      else if (content.left_text || content.right_text) keyPoints = [content.left_text, content.right_text].filter(Boolean)
      else if (Array.isArray(content.lines)) keyPoints = content.lines.map(l => `${l.speaker}: ${l.text}`)
      else if (content.body) keyPoints = String(content.body).split('\n').filter(Boolean)
    } catch (e) {
      console.error(e)
    }

    let thumbnails = []
    try {
      const { data: assets } = await assetApi.list(s.id)
      thumbnails = assets.filter(a => a.url).map(a => a.url)
    } catch (e) {
      console.error(e)
    }

    return {
      index: s.index,
      title: s.title || '無題のシーン',
      narration_draft: s.narration_text || '',
      layout_hint: layoutHint,
      key_points: keyPoints,
      thumbnails,
    }
  }))
  previewScenes.value = withAssets
}

const pollNarrationJob = async (jobId) => {
  try {
    const { data } = await scenarioApi.getPptxImportStatus(props.videoId, jobId)
    narrationJob.value = data
    if (data.status === 'processing') {
      pollTimer = setTimeout(() => pollNarrationJob(jobId), 2000)
    } else {
      await buildPreviewScenes()
      if (data.status === 'completed') {
        ui.notify('ナレーションの生成が完了しました。')
      }
    }
  } catch (e) {
    console.error(e)
  }
}

const generateFromPptx = async () => {
  if (!file.value) return
  stopPolling()
  narrationJob.value = null
  try {
    const result = await scenarioStore.fromPptx(props.videoId, file.value)
    importResult.value = result

    await buildPreviewScenes()
    ui.notify(`PPTX の解析が完了しました（${result.slide_count}スライド）。ナレーションを生成しています...`)

    pollNarrationJob(result.job_id)
  } catch (e) {
    ui.notifyError('PPTX からのシナリオ生成に失敗しました: ' + e.message)
  }
}

const finalize = async () => {
  emit('finalized')
}

onBeforeUnmount(() => {
  stopPolling()
})
</script>
