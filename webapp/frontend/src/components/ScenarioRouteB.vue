<template>
  <div class="pa-4 glass-panel">
    <h3 class="text-subtitle-1 font-weight-bold mb-3">📝 テキスト貼り付け</h3>

    <!-- テキストエリア入力 -->
    <v-textarea
      v-model="text"
      label="シナリオテキストを貼り付けてください"
      rows="10"
      placeholder="スライドごとに分割したいナレーション原稿や、プレゼンテーションの構成をここに貼り付けます。&#10;AI が自動でスライド構成とナレーションをシーンに分割・生成します。"
      class="mb-2 glass-card"
      hide-details
    />

    <!-- 押してから何も分からないまま待たされるのを避けるため、
         貼った時点で分量と待ち時間の目安を出す。 -->
    <div class="d-flex align-center justify-space-between mb-4 text-caption">
      <span :class="tooLong ? 'text-error' : 'text-medium-emphasis'">
        {{ charCount.toLocaleString() }} 文字
        <template v-if="limits.max_chars"> / 上限 {{ limits.max_chars.toLocaleString() }} 文字</template>
      </span>
      <span v-if="charCount > 0 && !tooLong" class="text-medium-emphasis">
        解析に {{ estimateLabel }} ほどかかります
      </span>
    </div>

    <v-alert v-if="tooLong" type="error" variant="tonal" density="compact" class="mb-4 text-caption">
      テキストが長すぎます。{{ limits.max_chars.toLocaleString() }} 文字以下に分けてから実行してください。
    </v-alert>

    <v-btn
      color="primary"
      :disabled="!text.trim() || tooLong"
      :loading="scenarioStore.loading"
      block
      class="mb-4"
      @click="generateFromText"
    >
      シーンを解析して分割する
    </v-btn>

    <!-- 進捗バー -->
    <div v-if="scenarioStore.loading" class="mb-4">
      <div class="text-caption text-medium-emphasis mb-1">テキストを解析してシナリオを作成中...</div>
      <v-progress-linear color="primary" indeterminate height="6" rounded />
    </div>

    <!-- 生成結果プレビュー -->
    <div v-if="previewScenes.length > 0" class="mt-4">
      <div class="text-subtitle-2 font-weight-bold mb-2">分割結果プレビュー</div>
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
          <div class="text-caption text-medium-emphasis mb-1">ナレーション: {{ scene.narration_draft }}</div>
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
import { computed, onMounted, ref } from 'vue'
import { useScenarioStore } from '@/stores/scenario'
import { useUiStore } from '@/stores/ui'
import { api } from '@/api/index.js'

const props = defineProps({
  videoId: {
    type: String,
    required: true
  }
})

const emit = defineEmits(['finalized'])

const scenarioStore = useScenarioStore()
const ui = useUiStore()

const text = ref('')
const previewScenes = ref([])

// 上限と見積もりの係数はサーバーが持つ（/scenario/paste-limits）。
// 画面に数値を直書きすると必ずサーバーとずれるため取りに行く。
// 取得に失敗しても入力は妨げない（上限チェックはサーバー側でも行う）。
const limits = ref({ max_chars: 0, tokens_per_char: 0.6, prompt_tokens_per_sec: 1190 })

onMounted(async () => {
  try {
    const { data } = await api.get('/scenario/paste-limits')
    limits.value = data
  } catch (e) {
    console.warn('貼り付けの上限を取得できませんでした', e)
  }
})

const charCount = computed(() => text.value.length)
const tooLong = computed(() => limits.value.max_chars > 0 && charCount.value > limits.value.max_chars)

const estimateLabel = computed(() => {
  const sec = charCount.value * limits.value.tokens_per_char / limits.value.prompt_tokens_per_sec
  if (sec < 5) return '数秒'
  if (sec < 60) return `${Math.round(sec / 5) * 5} 秒`
  return `${Math.round(sec / 60)} 分`
})

const generateFromText = async () => {
  if (!text.value.trim()) return
  try {
    await scenarioStore.fromText(props.videoId, text.value)
    
    // DB から最新のシーンを取得して previewScenes にセットする
    const { data: scenes } = await api.get(`/videos/${props.videoId}/scenes`)
    previewScenes.value = scenes.map(s => {
      let keyPoints = []
      let layoutHint = s.layout_type
      try {
        const content = JSON.parse(s.slide_content_json || '{}')
        if (Array.isArray(content.bullet_points)) keyPoints = content.bullet_points
        else if (typeof content.bullet_points === 'string') keyPoints = content.bullet_points.split('\n').filter(Boolean)
        else if (content.left_text || content.right_text) keyPoints = [content.left_text, content.right_text].filter(Boolean)
        else if (Array.isArray(content.lines)) keyPoints = content.lines.map(l => `${l.speaker}: ${l.text}`)
        else if (content.body) keyPoints = String(content.body).split('\n').filter(Boolean)
      } catch (e) {
        console.error(e)
      }
      return {
        index: s.index,
        title: s.title || '無題のシーン',
        narration_draft: s.narration_text || '',
        layout_hint: layoutHint,
        key_points: keyPoints
      }
    })
    
    ui.notify('テキストの解析が完了しました。プレビューを確認して確定してください。')
  } catch (e) {
    ui.notifyError('テキストからのシナリオ生成に失敗しました: ' + e.message)
  }
}

const finalize = async () => {
  emit('finalized')
}
</script>
