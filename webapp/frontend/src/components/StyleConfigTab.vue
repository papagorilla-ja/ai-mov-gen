<template>
  <v-container fluid class="pa-0">
    <v-row>
      <!-- 左カラム: スタイル設定フォーム -->
      <v-col cols="12" md="6" class="pa-4 style-config-container overflow-y-auto" style="max-height: calc(100vh - 120px);">

        <div class="d-flex align-center justify-space-between mb-3">
          <span class="text-subtitle-1 font-weight-bold">🎨 スタイル設定</span>
          <!-- 自動保存の状態表示。保存ボタンを廃止したため、ここが唯一の手がかりになる -->
          <span class="text-caption d-flex align-center" :class="saveStateColor">
            <v-icon size="16" class="mr-1">{{ saveStateIcon }}</v-icon>{{ saveStateLabel }}
          </span>
        </div>

        <!-- ── スタイルプリセット ── -->
        <div class="mb-4">
          <div class="text-body-2 font-weight-medium mb-2">スタイルプリセット</div>
          <v-row dense>
            <v-col v-for="tpl in styleStore.templates" :key="tpl.id" cols="6" sm="4">
              <v-card
                :class="['choice-card pa-2', { 'is-selected': styleForm.template_id === tpl.id }]"
                variant="outlined"
                @click="selectTemplate(tpl)"
              >
                <!-- プリセットの縮小見本。配色だけでなく背景モチーフと質感も再現する -->
                <div class="thumb" :style="thumbVarsOf(tpl)">
                  <div class="thumb-motif" :class="`is-${tpl.background_motif}`"></div>
                  <div class="thumb-card" :class="`is-${tpl.decor_style}`"></div>
                </div>
                <div class="text-caption font-weight-bold text-truncate mt-1">{{ tpl.name }}</div>
              </v-card>
            </v-col>
          </v-row>
        </div>

        <!-- ── 画面サイズ (アスペクト比) ── -->
        <v-card class="mb-4 glass-card border-thin" variant="outlined">
          <v-card-title class="text-body-2 font-weight-bold pa-3 pb-0">画面サイズ (アスペクト比)</v-card-title>
          <v-card-text class="pa-3">
            <v-btn-toggle :model-value="aspectPreset" mandatory density="comfortable" color="primary" variant="outlined" @update:model-value="onAspectChange">
              <v-btn value="16:9" size="small">16:9 (1920 × 1080)</v-btn>
              <v-btn value="4:3" size="small">4:3 (1440 × 1080)</v-btn>
            </v-btn-toggle>
          </v-card-text>
        </v-card>

        <!-- ── カラー設定 ── -->
        <v-card class="mb-4 glass-card border-thin" variant="outlined">
          <v-card-title class="text-body-2 font-weight-bold pa-3 pb-0">カラー設定</v-card-title>
          <v-card-text class="pa-3">
            <v-row dense>
              <v-col cols="6" sm="4" v-for="colorItem in colorsList" :key="colorItem.key">
                <div class="d-flex align-center gap-2 mb-2">
                  <div class="color-picker-wrapper">
                    <input type="color" v-model="styleForm[colorItem.key]" class="color-picker-input cursor-pointer" />
                    <span class="color-swatch-preview" :style="{ backgroundColor: styleForm[colorItem.key] }"></span>
                  </div>
                  <v-text-field
                    v-model="styleForm[colorItem.key]"
                    :label="colorItem.label"
                    density="compact"
                    hide-details
                    variant="outlined"
                    class="glass-field text-caption"
                  />
                </div>
              </v-col>
            </v-row>
            <!-- 背景色と文字色のコントラスト不足はレンダリング時に自動補正されるため、
                 その旨をここで明示しておく（黙って色が変わると混乱するため） -->
            <v-alert v-if="lowContrast" type="warning" variant="tonal" density="compact" class="text-caption mt-1">
              背景色と文字色のコントラストが不足しています。動画では読みやすい文字色に自動補正されます。
            </v-alert>
          </v-card-text>
        </v-card>

        <!-- ── フォント設定 ── -->
        <v-card class="mb-4 glass-card border-thin" variant="outlined">
          <v-card-title class="text-body-2 font-weight-bold pa-3 pb-0">フォント設定</v-card-title>
          <v-card-text class="pa-3">
            <v-row dense>
              <v-col cols="12" sm="6">
                <v-select
                  v-model="styleForm.font_heading"
                  :items="fontItems"
                  item-title="label"
                  item-value="value"
                  label="見出しフォント"
                  density="compact" variant="outlined" hide-details class="glass-card mb-2"
                >
                  <!-- 選択肢はその書体自身で描く。名前だけでは印象が判断できないため -->
                  <template #item="{ props: itemProps, item }">
                    <v-list-item v-bind="itemProps" :style="{ fontFamily: item.raw.stack }" :subtitle="item.raw.description" />
                  </template>
                </v-select>
              </v-col>
              <v-col cols="12" sm="6">
                <v-select
                  v-model="styleForm.font_body"
                  :items="fontItems"
                  item-title="label"
                  item-value="value"
                  label="本文フォント"
                  density="compact" variant="outlined" hide-details class="glass-card"
                >
                  <template #item="{ props: itemProps, item }">
                    <v-list-item v-bind="itemProps" :style="{ fontFamily: item.raw.stack }" :subtitle="item.raw.description" />
                  </template>
                </v-select>
              </v-col>
            </v-row>
          </v-card-text>
        </v-card>

        <!-- ── 背景モチーフ ── -->
        <v-card class="mb-4 glass-card border-thin" variant="outlined">
          <v-card-title class="text-body-2 font-weight-bold pa-3 pb-0">背景モチーフ</v-card-title>
          <v-card-text class="pa-3">
            <v-row dense>
              <v-col v-for="opt in options?.background_motifs || []" :key="opt.value" cols="4" sm="4">
                <v-card
                  :class="['choice-card pa-2', { 'is-selected': styleForm.background_motif === opt.value }]"
                  variant="outlined"
                  @click="styleForm.background_motif = opt.value"
                >
                  <div class="thumb" :style="thumbVars">
                    <div class="thumb-motif" :class="`is-${opt.value}`"></div>
                  </div>
                  <div class="text-caption font-weight-bold mt-1">{{ opt.label }}</div>
                  <div class="text-caption text-medium-emphasis choice-desc">{{ opt.description }}</div>
                </v-card>
              </v-col>
            </v-row>
          </v-card-text>
        </v-card>

        <!-- ── 装飾スタイル ── -->
        <v-card class="mb-4 glass-card border-thin" variant="outlined">
          <v-card-title class="text-body-2 font-weight-bold pa-3 pb-0">装飾スタイル（カードの質感）</v-card-title>
          <v-card-text class="pa-3">
            <v-row dense>
              <v-col v-for="opt in options?.decor_styles || []" :key="opt.value" cols="6" sm="3">
                <v-card
                  :class="['choice-card pa-2', { 'is-selected': styleForm.decor_style === opt.value }]"
                  variant="outlined"
                  @click="styleForm.decor_style = opt.value"
                >
                  <div class="thumb" :style="thumbVars">
                    <div class="thumb-motif" :class="`is-${styleForm.background_motif}`"></div>
                    <div class="thumb-card" :class="`is-${opt.value}`"></div>
                  </div>
                  <div class="text-caption font-weight-bold mt-1">{{ opt.label }}</div>
                  <div class="text-caption text-medium-emphasis choice-desc">{{ opt.description }}</div>
                </v-card>
              </v-col>
            </v-row>
          </v-card-text>
        </v-card>

        <!-- ── 組版（タイポグラフィスケール） ── -->
        <v-card class="mb-4 glass-card border-thin" variant="outlined">
          <v-card-title class="text-body-2 font-weight-bold pa-3 pb-0">組版（文字の大きさと余白）</v-card-title>
          <v-card-text class="pa-3">
            <v-row dense>
              <v-col v-for="opt in options?.type_scales || []" :key="opt.value" cols="4">
                <v-card
                  :class="['choice-card pa-2', { 'is-selected': styleForm.type_scale === opt.value }]"
                  variant="outlined"
                  @click="styleForm.type_scale = opt.value"
                >
                  <div class="thumb" :style="thumbVars">
                    <div class="thumb-type" :class="`is-${opt.value}`">
                      <span class="line line-title"></span>
                      <span class="line"></span>
                      <span class="line"></span>
                    </div>
                  </div>
                  <div class="text-caption font-weight-bold mt-1">{{ opt.label }}</div>
                  <div class="text-caption text-medium-emphasis choice-desc">{{ opt.description }}</div>
                </v-card>
              </v-col>
            </v-row>
          </v-card-text>
        </v-card>

        <!-- ── シーン切替 ── -->
        <v-card class="mb-4 glass-card border-thin" variant="outlined">
          <v-card-title class="text-body-2 font-weight-bold pa-3 pb-0">シーン切替の演出</v-card-title>
          <v-card-text class="pa-3">
            <v-row dense>
              <v-col v-for="opt in options?.transitions || []" :key="opt.value" cols="4" sm="4">
                <v-card
                  :class="['choice-card pa-2', { 'is-selected': styleForm.transition === opt.value }]"
                  variant="outlined"
                  @click="styleForm.transition = opt.value"
                >
                  <!-- 動きは静止画では伝わらないため、実際の演出をループ再生して見せる -->
                  <div class="thumb" :style="thumbVars">
                    <div class="thumb-motif" :class="`is-${styleForm.background_motif}`"></div>
                    <div class="thumb-trans" :class="`is-${opt.value}`"></div>
                  </div>
                  <div class="text-caption font-weight-bold mt-1">{{ opt.label }}</div>
                  <div class="text-caption text-medium-emphasis choice-desc">{{ opt.description }}</div>
                </v-card>
              </v-col>
            </v-row>
            <div class="text-caption text-medium-emphasis mt-2">
              シーン同士は重ねずに切り替わります。切替の瞬間は背景モチーフが見えます。
            </div>
          </v-card-text>
        </v-card>

        <!-- ── スタイルプロンプト ── -->
        <v-card class="mb-4 glass-card border-thin" variant="outlined">
          <v-card-title class="text-body-2 font-weight-bold pa-3 pb-0">AI にデザインを任せる</v-card-title>
          <v-card-text class="pa-3">
            <div class="d-flex gap-2 align-center">
              <v-text-field
                v-model="promptText"
                placeholder="例: 落ち着いた和風の研修動画にして"
                density="compact" variant="outlined" hide-details
                class="glass-card flex-grow-1"
              />
              <v-btn
                color="secondary" variant="outlined"
                :loading="applyingPrompt"
                class="text-caption px-3" height="40px"
                @click="applyAiPrompt"
              >
                AI で生成
              </v-btn>
            </div>
            <div class="text-caption text-medium-emphasis mt-2">
              配色・フォントに加え、背景モチーフ・装飾スタイル・組版・切替演出も一括で提案します。
            </div>
          </v-card-text>
        </v-card>

        <!-- ── BGM 設定 ── -->
        <v-card class="mb-4 glass-card border-thin" variant="outlined">
          <v-card-title class="text-body-2 font-weight-bold pa-3 pb-0">BGM トラック</v-card-title>
          <v-card-text class="pa-3">
            <div v-if="currentBgmName" class="d-flex align-center mb-3 pa-2 rounded" style="background: rgba(255,255,255,0.05);">
              <v-icon class="mr-2" size="20">mdi-music</v-icon>
              <span class="text-body-2 flex-grow-1 text-truncate">{{ currentBgmName }}</span>
              <v-btn icon="mdi-delete-outline" color="error" variant="text" size="small" :loading="bgmDeleting" @click="handleDeleteBgm" />
            </div>
            <div v-else class="text-caption text-medium-emphasis mb-3">BGM が設定されていません</div>

            <v-file-input
              v-model="bgmFile"
              label="BGM ファイルを選択 (MP3 / WAV / M4A / FLAC)"
              accept=".mp3,.wav,.m4a,.flac"
              prepend-icon="mdi-music-note"
              variant="outlined" density="compact" hide-details class="mb-3"
            />
            <v-btn :disabled="!bgmFile" :loading="bgmUploading" color="secondary" size="small" prepend-icon="mdi-upload" @click="handleUploadBgm">
              アップロード
            </v-btn>

            <div class="mt-4">
              <div class="d-flex align-center justify-space-between mb-1">
                <span class="text-caption">BGM ボリューム</span>
                <span class="text-caption font-weight-bold">{{ Math.round((styleForm.bgm_volume ?? 0.3) * 100) }}%</span>
              </div>
              <v-slider v-model="styleForm.bgm_volume" :min="0.05" :max="1.0" :step="0.05" thumb-label color="secondary" density="compact" hide-details />
            </div>
          </v-card-text>
        </v-card>

        <!-- ── カスタム CSS ── -->
        <div class="mb-4">
          <div class="text-body-2 font-weight-medium mb-1">カスタム CSS (上級者向け)</div>
          <v-textarea
            v-model="styleForm.custom_css"
            placeholder="/* 追加のスタイルルールを記述できます */"
            rows="4" density="compact" variant="outlined" hide-details
            class="glass-card font-mono"
          />
        </div>
      </v-col>

      <!-- 右カラム: リアルタイムプレビュー -->
      <v-col cols="12" md="6" class="pa-4 d-flex flex-column" style="height: calc(100vh - 120px);">
        <div class="d-flex align-center justify-space-between mb-3">
          <span class="text-subtitle-1 font-weight-bold">📺 リアルタイムプレビュー</span>
          <v-btn size="small" color="primary" variant="outlined" prepend-icon="mdi-refresh" :loading="previewLoading" @click="refreshPreview">
            プレビュー再生成
          </v-btn>
        </div>
        <v-card class="flex-grow-1 pa-0 bg-black position-relative" variant="outlined" style="overflow: hidden; min-height: 300px;">
          <iframe
            v-if="previewUrl"
            ref="previewFrame"
            :src="previewUrl"
            style="width: 100%; height: 100%; border: none;"
            title="リアルタイムスタイルプレビュー"
            @load="onPreviewLoaded"
          />
          <div v-else class="d-flex flex-column align-center justify-center fill-height text-medium-emphasis">
            <v-icon size="48" class="mb-2">mdi-monitor-eye</v-icon>
            <span class="text-body-2">プレビューの読込準備中...</span>
          </div>
        </v-card>
      </v-col>
    </v-row>
  </v-container>
</template>

<script setup>
import { ref, reactive, onMounted, onBeforeUnmount, watch, computed } from 'vue'
import { useStyleStore } from '@/stores/style'
import { useUiStore } from '@/stores/ui'
import { styleApi } from '@/api/style.js'
import { api } from '@/api/index.js'

const props = defineProps({
  videoId: { type: String, required: true }
})

const styleStore = useStyleStore()
const ui = useUiStore()

const previewUrl = ref('')
const previewFrame = ref(null)
const previewLoading = ref(false)
const promptText = ref('')
const applyingPrompt = ref(false)

// 'idle' | 'saving' | 'saved' | 'error'
const saveState = ref('idle')
// フォームへプログラムから値を流し込んでいる間は自動保存を止める
const suppressAutoSave = ref(true)

// 選択肢とその既定値はサーバー (design_tokens.py) が唯一の正。
const options = computed(() => styleStore.options)

// 画面サイズ以外の既定値はサーバーから取得したものを使う。
// 画面サイズだけはサーバー側でも列の既定値を持つためここで定義する。
const LOCAL_DEFAULTS = { bgm_volume: 0.3, canvas_width: 1920, canvas_height: 1080, custom_css: '', template_id: null }

// 変更するとコンポジションの構造（HTML）が変わるため、サーバーでの再生成が要る項目。
// これ以外は iframe に CSS を流し込むだけで反映できる。
const STRUCTURAL_FIELDS = ['canvas_width', 'canvas_height', 'transition']

const styleForm = reactive({
  template_id: null,
  color_primary: '#6366f1',
  color_secondary: '#8b5cf6',
  color_accent: '#22d3ee',
  color_bg: '#0f0f1a',
  color_text_primary: '#f8fafc',
  font_heading: 'BIZ UDPGothic',
  font_body: 'BIZ UDPGothic',
  background_motif: 'grid',
  decor_style: 'glass',
  type_scale: 'normal',
  transition: 'none',
  custom_css: '',
  bgm_volume: 0.3,
  canvas_width: 1920,
  canvas_height: 1080,
})

const colorsList = [
  { key: 'color_primary', label: 'メインカラー' },
  { key: 'color_secondary', label: 'サブカラー' },
  { key: 'color_accent', label: 'アクセント' },
  { key: 'color_bg', label: '背景色' },
  { key: 'color_text_primary', label: '文字色' },
]

const fontItems = computed(() => options.value?.fonts || [])

const aspectPreset = computed(() => (styleForm.canvas_width === 1440 ? '4:3' : '16:9'))

const saveStateLabel = computed(() => ({
  idle: '', saving: '保存中...', saved: '保存済み', error: '保存に失敗',
}[saveState.value]))
const saveStateIcon = computed(() => ({
  idle: '', saving: 'mdi-progress-clock', saved: 'mdi-check-circle-outline', error: 'mdi-alert-circle-outline',
}[saveState.value]))
const saveStateColor = computed(() => ({
  idle: '', saving: 'text-medium-emphasis', saved: 'text-success', error: 'text-error',
}[saveState.value]))

// サムネイルへ現在の配色を流し込むための CSS 変数
const thumbVars = computed(() => thumbVarsOf(styleForm))
function thumbVarsOf(src) {
  return {
    '--t-primary': src.color_primary,
    '--t-secondary': src.color_secondary,
    '--t-accent': src.color_accent,
    '--t-bg': src.color_bg,
    '--t-text': src.color_text_primary,
  }
}

/** WCAG 相対輝度。コントラスト不足の警告表示にだけ使う（実際の補正はサーバー側）。 */
function luminance(hex) {
  const m = /^#?([0-9a-f]{6})$/i.exec(String(hex || ''))
  if (!m) return 0
  const n = parseInt(m[1], 16)
  const ch = [(n >> 16) & 255, (n >> 8) & 255, n & 255].map((c) => {
    const s = c / 255
    return s <= 0.04045 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4)
  })
  return 0.2126 * ch[0] + 0.7152 * ch[1] + 0.0722 * ch[2]
}
const lowContrast = computed(() => {
  const a = luminance(styleForm.color_bg)
  const b = luminance(styleForm.color_text_primary)
  const ratio = (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05)
  return ratio < 3.0
})

// ==========================================================================
// プレビュー
// ==========================================================================

function previewDoc() {
  // プレビューは同一オリジン (/projects/...) で配信されるため中身を触れる
  try {
    return previewFrame.value?.contentDocument || null
  } catch {
    return null
  }
}

/**
 * ユーザーが直接指定した値だけを iframe に即時反映する。
 * 派生色（文字副色・境界線・影など）はサーバーが計算するため、ここでは扱わない。
 */
function patchPreviewInstant() {
  const doc = previewDoc()
  if (!doc) return
  const root = doc.documentElement
  root.style.setProperty('--color-primary', styleForm.color_primary)
  root.style.setProperty('--color-secondary', styleForm.color_secondary)
  root.style.setProperty('--color-accent', styleForm.color_accent)
  root.style.setProperty('--bg-main', styleForm.color_bg)
  root.style.setProperty('--text-primary', styleForm.color_text_primary)

  const fonts = options.value?.fonts || []
  const stackOf = (name) => fonts.find((f) => f.value === name)?.stack
  const heading = stackOf(styleForm.font_heading)
  const body = stackOf(styleForm.font_body)
  if (heading) root.style.setProperty('--font-heading', heading)
  if (body) root.style.setProperty('--font-body', body)

  applyStageClasses(`motif-${styleForm.background_motif} decor-${styleForm.decor_style} type-${styleForm.type_scale}`)
}

function applyStageClasses(classes) {
  const stage = previewDoc()?.getElementById('stage')
  if (stage && classes) stage.className = classes
}

/**
 * サーバーが算出した :root（派生色を含む完全なテーマ）を iframe に流し込む。
 * head の末尾に足すことで、style.css の :root より確実に後勝ちさせる。
 */
function injectThemeCss(css) {
  const doc = previewDoc()
  if (!doc || !css) return
  let el = doc.getElementById('live-theme-override')
  if (!el) {
    el = doc.createElement('style')
    el.id = 'live-theme-override'
    doc.head.appendChild(el)
  }
  el.textContent = css
}

/** カスタム CSS も再生成せずに反映する（テーマの後ろに置く） */
function injectCustomCss(css) {
  const doc = previewDoc()
  if (!doc) return
  let el = doc.getElementById('live-custom-css')
  if (!el) {
    el = doc.createElement('style')
    el.id = 'live-custom-css'
    doc.head.appendChild(el)
  }
  el.textContent = css || ''
}

function onPreviewLoaded() {
  // 再読込のたびにインラインの上書きが消えるため、現在のフォーム内容を貼り直す
  patchPreviewInstant()
  injectThemeCss(styleStore.videoStyle?.theme_css)
  injectCustomCss(styleForm.custom_css)
}

async function refreshPreview() {
  previewLoading.value = true
  try {
    const { data } = await api.post(`/videos/${props.videoId}/preview`)
    // preview_url にはプレビュー用フラグとキャッシュ回避のクエリが含まれているため、そのまま使う
    previewUrl.value = data.preview_url
  } catch (e) {
    ui.notifyError('プレビューの更新に失敗しました: ' + e.message)
  } finally {
    previewLoading.value = false
  }
}

// ==========================================================================
// 読み込みと自動保存
// ==========================================================================

/**
 * サーバーの値をフォームへ流し込む。
 * null のカラム（新規動画は全カラム NULL）で既定値を潰さないことが重要。
 * 以前はここで null をそのまま代入していたため、色ピッカーが空になり
 * 「保存されていない」ように見えていた。
 */
function applyStyleToForm(data) {
  if (!data) return
  const serverDefaults = options.value?.defaults || {}
  suppressAutoSave.value = true
  for (const key of Object.keys(styleForm)) {
    const value = data[key]
    if (value === null || value === undefined) {
      if (key in serverDefaults) styleForm[key] = serverDefaults[key]
      else if (key in LOCAL_DEFAULTS) styleForm[key] = LOCAL_DEFAULTS[key]
    } else {
      styleForm[key] = value
    }
  }
  // 反映が終わってから監視を再開する（流し込み自体で保存が走らないように）
  requestAnimationFrame(() => { suppressAutoSave.value = false })
}

function buildPayload() {
  return { ...styleForm }
}

let saveTimer = null
let needsRegenerate = false

async function commitSave() {
  saveState.value = 'saving'
  try {
    const data = await styleStore.updateVideoStyle(props.videoId, buildPayload())
    injectThemeCss(data.theme_css)
    applyStageClasses(data.stage_classes)
    injectCustomCss(styleForm.custom_css)
    saveState.value = 'saved'
    if (needsRegenerate) {
      needsRegenerate = false
      await refreshPreview()
    }
  } catch (e) {
    saveState.value = 'error'
    ui.notifyError('スタイルの保存に失敗しました: ' + e.message)
  }
}

// フォームのどれかが変われば自動保存する。
// 色のドラッグ等で連射されるため、最後の変更から 500ms 待ってから 1 回だけ送る。
watch(
  () => ({ ...styleForm }),
  (next, prev) => {
    if (suppressAutoSave.value) return
    if (STRUCTURAL_FIELDS.some((f) => next[f] !== prev[f])) needsRegenerate = true

    // 個別に手を入れた時点でプリセットとは別物になる。
    // 選択中の表示を残すと「見た目と選択状態が食い違う」ため解除する。
    const changed = Object.keys(next).filter((k) => next[k] !== prev[k])
    if (next.template_id && !changed.includes('template_id')) {
      styleForm.template_id = null
    }

    patchPreviewInstant()
    injectCustomCss(next.custom_css)
    saveState.value = 'saving'
    clearTimeout(saveTimer)
    saveTimer = setTimeout(commitSave, 500)
  }
)

onMounted(async () => {
  try {
    await Promise.all([styleStore.fetchOptions(), styleStore.fetchTemplates()])
    applyStyleToForm(await styleStore.fetchVideoStyle(props.videoId))
    promptText.value = styleStore.videoStyle?.style_prompt || ''
    await refreshPreview()
  } catch (e) {
    suppressAutoSave.value = false
    ui.notifyError('スタイル情報の取得に失敗しました: ' + e.message)
  }
})

onBeforeUnmount(() => {
  // 画面を離れる直前の変更を取りこぼさない
  clearTimeout(saveTimer)
  if (saveState.value === 'saving') commitSave()
})

async function onAspectChange(val) {
  styleForm.canvas_width = val === '4:3' ? 1440 : 1920
  styleForm.canvas_height = 1080
}

async function selectTemplate(tpl) {
  try {
    // 項目のコピー漏れを防ぐため、テンプレートの適用はサーバー側で行う
    const data = await styleStore.applyTemplate(props.videoId, tpl.id)
    applyStyleToForm(data)
    injectThemeCss(data.theme_css)
    applyStageClasses(data.stage_classes)
    saveState.value = 'saved'
    // トランジションが変わる可能性があるためコンポジションを作り直す
    await refreshPreview()
  } catch (e) {
    ui.notifyError('テンプレートの適用に失敗しました: ' + e.message)
  }
}

async function applyAiPrompt() {
  if (!promptText.value.trim()) return
  applyingPrompt.value = true
  try {
    const updated = await styleStore.applyPrompt(props.videoId, promptText.value)
    applyStyleToForm(updated)
    injectThemeCss(updated.theme_css)
    applyStageClasses(updated.stage_classes)
    saveState.value = 'saved'
    ui.notify('AI の提案スタイルを適用しました')
    await refreshPreview()
  } catch (e) {
    ui.notifyError('AIスタイル適用に失敗しました: ' + e.message)
  } finally {
    applyingPrompt.value = false
  }
}

// ==========================================================================
// BGM
// ==========================================================================
const bgmFile = ref(null)
const bgmUploading = ref(false)
const bgmDeleting = ref(false)

const currentBgmName = computed(() => {
  const path = styleStore.videoStyle?.bgm_path
  return path ? path.split('/').pop() : null
})

async function handleUploadBgm() {
  if (!bgmFile.value) return
  bgmUploading.value = true
  try {
    const file = Array.isArray(bgmFile.value) ? bgmFile.value[0] : bgmFile.value
    const { data } = await styleApi.uploadBgm(props.videoId, file)
    styleStore.videoStyle = data
    bgmFile.value = null
    ui.notify('BGM をアップロードしました')
  } catch (e) {
    ui.notifyError('BGM のアップロードに失敗しました: ' + e.message)
  } finally {
    bgmUploading.value = false
  }
}

async function handleDeleteBgm() {
  bgmDeleting.value = true
  try {
    const { data } = await styleApi.deleteBgm(props.videoId)
    styleStore.videoStyle = data
    ui.notify('BGM を削除しました')
  } catch (e) {
    ui.notifyError('BGM の削除に失敗しました: ' + e.message)
  } finally {
    bgmDeleting.value = false
  }
}
</script>

<style scoped>
.style-config-container {
  max-width: 900px;
  margin: 0 auto;
}

/* ==========================================================================
   選択肢カード

   サムネイルは画像ファイルではなく CSS で描く。
   現在の配色 (--t-*) を流し込むため、色を変えると見本も一緒に変わる。
   ========================================================================== */
.choice-card {
  cursor: pointer;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  opacity: 0.75;
  height: 100%;
}
.choice-card:hover { opacity: 1; }
.choice-card.is-selected {
  opacity: 1;
  border-color: rgb(var(--v-theme-primary));
  box-shadow: 0 0 0 2px rgb(var(--v-theme-primary));
}
.choice-desc {
  line-height: 1.3;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.thumb {
  position: relative;
  height: 56px;
  border-radius: 6px;
  overflow: hidden;
  background: var(--t-bg);
  display: flex;
  align-items: center;
  justify-content: center;
}

/* ---- 背景モチーフの見本（本番の style.css と同じ考え方で縮小再現） ---- */
.thumb-motif { position: absolute; inset: 0; }
.thumb-motif.is-grid {
  background-image:
    linear-gradient(to right, var(--t-text) 1px, transparent 1px),
    linear-gradient(to bottom, var(--t-text) 1px, transparent 1px);
  background-size: 9px 9px;
  opacity: 0.18;
}
.thumb-motif.is-mesh {
  background:
    radial-gradient(ellipse at 20% 20%, var(--t-primary) 0%, transparent 60%),
    radial-gradient(ellipse at 85% 30%, var(--t-accent) 0%, transparent 60%),
    radial-gradient(ellipse at 60% 95%, var(--t-secondary) 0%, transparent 60%);
  filter: blur(6px);
  opacity: 0.75;
}
.thumb-motif.is-dots {
  background-image: radial-gradient(circle, var(--t-primary) 1px, transparent 1px);
  background-size: 8px 8px;
  opacity: 0.55;
}
.thumb-motif.is-waves {
  background-image: repeating-linear-gradient(-32deg, var(--t-primary) 0 2px, transparent 2px 10px);
  opacity: 0.4;
}
.thumb-motif.is-noise {
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='120' height='120'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.75' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='120' height='120' filter='url(%23n)'/%3E%3C/svg%3E");
  opacity: 0.35;
}
.thumb-motif.is-plain { background: none; }

/* ---- 装飾スタイルの見本 ---- */
.thumb-card {
  position: relative;
  width: 62%;
  height: 46%;
  border-radius: 5px;
}
.thumb-card.is-glass {
  background: color-mix(in srgb, var(--t-text) 14%, transparent);
  border: 1px solid color-mix(in srgb, var(--t-text) 30%, transparent);
  backdrop-filter: blur(3px);
}
.thumb-card.is-flat {
  background: color-mix(in srgb, var(--t-text) 12%, var(--t-bg));
  border: none;
}
.thumb-card.is-outline {
  background: transparent;
  border: 2px solid color-mix(in srgb, var(--t-text) 45%, transparent);
}
.thumb-card.is-solid {
  background: color-mix(in srgb, var(--t-text) 22%, var(--t-bg));
  border: none;
  box-shadow: 0 4px 10px -2px rgba(0, 0, 0, 0.5);
}

/* ---- 組版の見本: 見出しと本文の相対的な大きさ・間隔を示す ---- */
.thumb-type {
  position: relative;
  width: 68%;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
}
.thumb-type .line {
  display: block;
  width: 100%;
  background: var(--t-text);
  opacity: 0.55;
  border-radius: 1px;
}
.thumb-type .line-title { background: var(--t-primary); opacity: 1; }
.thumb-type.is-compact { gap: 3px; }
.thumb-type.is-compact .line { height: 3px; }
.thumb-type.is-compact .line-title { height: 5px; width: 70%; }
.thumb-type.is-normal { gap: 5px; }
.thumb-type.is-normal .line { height: 4px; }
.thumb-type.is-normal .line-title { height: 7px; width: 70%; }
.thumb-type.is-relaxed { gap: 8px; }
.thumb-type.is-relaxed .line { height: 5px; }
.thumb-type.is-relaxed .line-title { height: 9px; width: 70%; }

/* ---- シーン切替の見本: 実際の演出をループ再生する ---- */
.thumb-trans {
  position: relative;
  width: 58%;
  height: 44%;
  border-radius: 4px;
  background: var(--t-primary);
  animation-duration: 2.4s;
  animation-iteration-count: infinite;
  animation-timing-function: ease-in-out;
}
.thumb-trans.is-none { animation-name: trans-none; }
.thumb-trans.is-fade { animation-name: trans-fade; }
.thumb-trans.is-slide { animation-name: trans-slide; }
.thumb-trans.is-zoom { animation-name: trans-zoom; }
.thumb-trans.is-wipe { animation-name: trans-wipe; }

@keyframes trans-none {
  0%, 45% { opacity: 1; }
  46%, 55% { opacity: 0; }
  56%, 100% { opacity: 1; }
}
@keyframes trans-fade {
  0%, 35% { opacity: 1; }
  50% { opacity: 0; }
  65%, 100% { opacity: 1; }
}
@keyframes trans-slide {
  0%, 30% { opacity: 1; transform: translateX(0); }
  50% { opacity: 0; transform: translateX(-40%); }
  51% { opacity: 0; transform: translateX(40%); }
  70%, 100% { opacity: 1; transform: translateX(0); }
}
@keyframes trans-zoom {
  0%, 30% { opacity: 1; transform: scale(1); }
  50% { opacity: 0; transform: scale(0.85); }
  51% { opacity: 0; transform: scale(1.15); }
  70%, 100% { opacity: 1; transform: scale(1); }
}
@keyframes trans-wipe {
  0%, 30% { opacity: 1; clip-path: inset(0 0 0 0); }
  50% { opacity: 0.4; clip-path: inset(0 0 100% 0); }
  51% { opacity: 0.4; clip-path: inset(100% 0 0 0); }
  70%, 100% { opacity: 1; clip-path: inset(0 0 0 0); }
}

/* ==========================================================================
   カラーピッカー
   ========================================================================== */
.color-picker-wrapper {
  position: relative;
  width: 32px;
  height: 32px;
  flex-shrink: 0;
}
.color-picker-input {
  position: absolute;
  inset: 0;
  opacity: 0;
  width: 100%;
  height: 100%;
}
.color-swatch-preview {
  display: block;
  width: 100%;
  height: 100%;
  border-radius: 6px;
  border: 1px solid rgba(255, 255, 255, 0.2);
  pointer-events: none;
}

.font-mono :deep(textarea) {
  font-family: 'SFMono-Regular', Consolas, monospace;
  font-size: 0.8rem;
}
</style>
