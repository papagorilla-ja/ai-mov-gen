<template>
  <div class="assets-slot-container pa-4 border border-thin rounded glass-card">
    <div class="d-flex align-center justify-space-between mb-3 flex-wrap ga-2">
      <div class="text-subtitle-2 font-weight-bold">
        素材スロット
        <span class="text-caption text-medium-emphasis font-weight-regular ms-1">{{ slotHint }}</span>
      </div>
      <span class="text-caption text-medium-emphasis d-flex align-center">
        <v-icon icon="mdi-content-paste" size="x-small" class="me-1" />
        画像をコピーして {{ pasteKeyLabel }} で貼り付けできます
      </span>
    </div>

    <v-row dense>
      <v-col v-for="slotNum in visibleSlots" :key="slotNum" :cols="slotCols">
        <div
          class="slot-wrapper d-flex flex-column align-center pa-2 border border-thin rounded glass-card position-relative"
          :class="{ 'is-unused': slotNum > effectiveSlotCount }"
        >
          <div class="text-caption font-weight-medium mb-1 text-medium-emphasis">
            スロット {{ slotNum }}
            <span v-if="slotNum > effectiveSlotCount" class="text-warning">・未使用</span>
          </div>

          <div
            class="upload-area d-flex flex-column align-center justify-center cursor-pointer rounded overflow-hidden"
            :class="{ 'has-file': getAsset(slotNum), 'dragover': dragOverSlot === slotNum }"
            style="width: 100%; height: 100px; position: relative;"
            @dragover.prevent="onDragOver(slotNum)"
            @dragleave.prevent="onDragLeave()"
            @drop.prevent="onDrop($event, slotNum)"
            @click="triggerFileInput(slotNum)"
          >
            <v-overlay :model-value="uploadingSlot === slotNum" contained persistent
                       class="align-center justify-center">
              <v-progress-circular indeterminate size="28" color="primary" />
            </v-overlay>
            <!-- 既存素材あり -->
            <template v-if="getAsset(slotNum)">
              <div v-if="getAsset(slotNum).asset_type === 'svg'" class="svg-preview d-flex flex-column align-center justify-center h-100 w-100">
                <v-icon icon="mdi-xml" color="primary" size="large" />
                <span class="text-xxs">SVG Code</span>
              </div>
              <div v-else-if="getAsset(slotNum).asset_type === 'video'" class="video-preview d-flex flex-column align-center justify-center h-100 w-100">
                <v-icon icon="mdi-video" color="primary" size="large" />
                <span class="text-xxs">Video File</span>
              </div>
              <div v-else class="img-preview h-100 w-100" :style="{ backgroundImage: `url(${getPreviewUrl(getAsset(slotNum))})` }">
              </div>
            </template>
            
            <!-- 新規追加 -->
            <template v-else>
              <v-icon icon="mdi-cloud-upload-outline" color="medium-emphasis" />
              <span class="text-xxs text-medium-emphasis text-center">Drop / Click</span>
            </template>
          </div>

          <input
            type="file"
            :ref="el => { if (el) fileInputs[slotNum] = el }"
            style="display: none;"
            accept="image/*,video/*,.svg"
            @change="onFileSelected($event, slotNum)"
          />

          <!-- スロット操作ボタン -->
          <div class="d-flex w-100 justify-space-between mt-2">
            <template v-if="getAsset(slotNum)">
              <!-- 設定 -->
              <v-btn
                icon="mdi-cog"
                size="x-small"
                variant="text"
                color="secondary"
                @click.stop="openSettings(slotNum)"
              />
              <!-- 削除 -->
              <v-btn
                icon="mdi-trash-can-outline"
                size="x-small"
                variant="text"
                color="error"
                @click.stop="deleteAsset(slotNum)"
              />
            </template>
            <template v-else>
              <!-- SVG 直接入力 -->
              <v-btn
                prepend-icon="mdi-xml"
                size="x-small"
                variant="text"
                color="primary"
                block
                @click.stop="openSvgInput(slotNum)"
              >
                SVG
              </v-btn>
            </template>
          </div>

          <!-- キャプションはレイアウトが画像を内容として受け取るときだけ。
               画像そのものはスロットが正、キャプションはスライド内容が正で、
               サーバー側はスロット N とキャプション N を突き合わせて描画する。 -->
          <v-text-field
            v-if="showCaptions && slotNum <= effectiveSlotCount"
            :model-value="captionFor(slotNum)"
            @update:model-value="value => setCaption(slotNum, value)"
            label="キャプション"
            density="compact"
            variant="outlined"
            hide-details
            class="mt-2 w-100 caption-field"
          />
        </div>
      </v-col>
    </v-row>

    <!-- ── アセット設定編集モーダル ── -->
    <v-dialog v-model="settingsDialog" max-width="450px" persistent>
      <v-card class="glass-card pa-3 border-thin" variant="flat">
        <v-card-title class="text-subtitle-1 font-weight-bold">スロット {{ activeSlot }} 素材設定</v-card-title>
        <v-card-text>
          <v-row dense>
            <v-col cols="6">
              <v-text-field
                v-model.number="configForm.offset_sec"
                label="表示オフセット (秒)"
                type="number"
                step="0.1"
                density="compact"
                variant="outlined"
              />
            </v-col>
            <v-col cols="6">
              <v-text-field
                v-model.number="configForm.duration_sec"
                label="表示秒数 (空で末尾まで)"
                type="number"
                step="0.1"
                density="compact"
                variant="outlined"
              />
            </v-col>
            <v-col cols="6">
              <v-select
                v-model="configForm.x"
                :items="['left', 'center', 'right', 'custom']"
                label="X位置 (横)"
                density="compact"
                variant="outlined"
              />
            </v-col>
            <v-col cols="6">
              <v-select
                v-model="configForm.y"
                :items="['top', 'center', 'bottom', 'custom']"
                label="Y位置 (縦)"
                density="compact"
                variant="outlined"
              />
            </v-col>
            <v-col cols="6" v-if="configForm.x === 'custom'">
              <v-text-field
                v-model="configForm.custom_x"
                label="カスタムX (例: 50px, 10%)"
                density="compact"
                variant="outlined"
              />
            </v-col>
            <v-col cols="6" v-if="configForm.y === 'custom'">
              <v-text-field
                v-model="configForm.custom_y"
                label="カスタムY (例: 100px, 20%)"
                density="compact"
                variant="outlined"
              />
            </v-col>
            <v-col cols="12">
              <v-text-field
                v-model="configForm.max_width"
                label="最大幅 (max-width)"
                density="compact"
                variant="outlined"
              />
            </v-col>
            <v-col cols="12">
              <v-text-field
                v-model="configForm.max_height"
                label="最大高さ (max-height)"
                density="compact"
                variant="outlined"
              />
            </v-col>
            <v-col cols="12">
              <v-text-field
                v-model="configForm.border_radius"
                label="角丸 (border-radius)"
                density="compact"
                variant="outlined"
              />
            </v-col>
          </v-row>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" color="medium-emphasis" @click="settingsDialog = false">キャンセル</v-btn>
          <v-btn color="primary" @click="saveConfig">設定を保存</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- ── SVGテキスト入力モーダル ── -->
    <v-dialog v-model="svgDialog" max-width="500px" persistent>
      <v-card class="glass-card pa-3 border-thin" variant="flat">
        <v-card-title class="text-subtitle-1 font-weight-bold">スロット {{ activeSlot }} SVG コード入力</v-card-title>
        <v-card-text>
          <v-textarea
            v-model="svgText"
            placeholder="<svg ...>...</svg>"
            rows="10"
            variant="outlined"
            label="SVGコード"
          />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" color="medium-emphasis" @click="svgDialog = false">キャンセル</v-btn>
          <v-btn color="primary" :disabled="!svgText.trim()" @click="saveSvg">保存する</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </div>
</template>

<script setup>
import { computed, ref, reactive, onMounted, onBeforeUnmount, watch } from 'vue'
import { assetApi } from '@/api/asset'
import { useUiStore } from '@/stores/ui'

// 画像を内容として受け取らないレイアウトでは、素材は「添え物」として
// 絶対配置で重ねられる。その用途の既定枠数。
const DEFAULT_SLOT_COUNT = 3

// 貼り付けた File は名前が空のことがある。サーバーは拡張子で形式を判定するため、
// MIME から補ってやらないと 400 で弾かれる。
const PASTE_EXTENSIONS = {
  'image/png': '.png',
  'image/jpeg': '.jpg',
  'image/webp': '.webp',
  'image/gif': '.gif',
  'image/svg+xml': '.svg',
}

const props = defineProps({
  sceneId: {
    type: String,
    required: true
  },
  // レイアウトが必要とする画像の枚数。media 型なら capacity.max、それ以外は既定値。
  slotCount: {
    type: Number,
    default: DEFAULT_SLOT_COUNT
  },
  // レイアウトが画像を内容として受け取る（media 型）ときだけキャプション欄を出す。
  showCaptions: {
    type: Boolean,
    default: false
  },
  // スロット順のキャプション。captions[0] がスロット 1 に対応する。
  captions: {
    type: Array,
    default: () => []
  }
})

const emit = defineEmits(['update:captions'])
const ui = useUiStore()

const assets = ref([])
const fileInputs = ref({})
const dragOverSlot = ref(0)
const uploadingSlot = ref(0)

const settingsDialog = ref(false)
const svgDialog = ref(false)
const activeSlot = ref(1)
const svgText = ref('')

const configForm = reactive({
  offset_sec: 0.5,
  duration_sec: null,
  x: 'center',
  y: 'center',
  custom_x: '50px',
  custom_y: '50px',
  max_width: '600px',
  max_height: '500px',
  border_radius: '16px'
})

// レイアウトが要求する枚数。0 や負値が来ても 1 枠は必ず出す。
const effectiveSlotCount = computed(() => Math.max(1, props.slotCount || DEFAULT_SLOT_COUNT))

// 表示するスロット番号。
// 要求枚数より多く登録済みの素材があるときは、そこまで並べて「未使用」と添える。
// 隠してしまうと、レイアウトを絞った瞬間に画面から削除できない素材が生まれる。
const visibleSlots = computed(() => {
  const highest = assets.value.reduce((max, a) => Math.max(max, a.slot || 0), 0)
  const count = Math.max(effectiveSlotCount.value, highest)
  return Array.from({ length: count }, (_, i) => i + 1)
})

// 4 枠以上は 1 行に収まるよう狭くする。3 枠までは従来と同じ大きさ。
const slotCols = computed(() => (visibleSlots.value.length > 3 ? 3 : 4))

const slotHint = computed(() =>
  props.showCaptions
    ? `（このレイアウトは画像 ${effectiveSlotCount.value} 枚を使います）`
    : `（最大 ${effectiveSlotCount.value} スロット／スライドに重ねて表示）`
)

// Mac と Windows で案内する修飾キーを変える
const pasteKeyLabel = computed(() =>
  /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent) ? 'Cmd + V' : 'Ctrl + V'
)

onMounted(async () => {
  await fetchAssets()
  window.addEventListener('paste', onPaste)
})

onBeforeUnmount(() => {
  window.removeEventListener('paste', onPaste)
})

watch(() => props.sceneId, async () => {
  await fetchAssets()
})

async function fetchAssets() {
  if (!props.sceneId) return
  try {
    const { data } = await assetApi.list(props.sceneId)
    assets.value = data
  } catch (e) {
    console.error(e)
  }
}

function getAsset(slot) {
  return assets.value.find(a => a.slot === slot)
}

function getPreviewUrl(asset) {
  if (!asset || !asset.url) return ''
  const apiBase = (import.meta.env.VITE_API_BASE_URL || '').replace('/api/v1', '')
  return `${apiBase}${asset.url}`
}

function triggerFileInput(slot) {
  if (getAsset(slot)) return
  if (fileInputs.value[slot]) {
    fileInputs.value[slot].click()
  }
}

async function onFileSelected(event, slot) {
  const file = event.target.files[0]
  if (!file) return
  await uploadFile(file, slot)
}

/**
 * 1 ファイルをスロットへ登録する。
 *
 * filename は貼り付け経路のためにある。クリップボード由来の File は
 * 名前が空のことがあり、そのままでは拡張子が取れない。
 */
async function uploadFile(file, slot, filename = null) {
  const name = filename || file.name || ''
  const ext = name.includes('.') ? name.split('.').pop().toLowerCase() : ''
  let assetType = 'image'
  if (ext === 'svg') {
    assetType = 'svg'
  } else if (ext === 'mp4' || ext === 'webm') {
    assetType = 'video'
  }

  uploadingSlot.value = slot
  try {
    if (assetType === 'svg') {
      const svgContent = await file.text()
      await assetApi.uploadSvg(props.sceneId, slot, svgContent)
      ui.notify(`スロット ${slot} に SVG を登録しました`)
    } else {
      await assetApi.upload(props.sceneId, slot, file, assetType, name || undefined)
      ui.notify(`スロット ${slot} に素材を登録しました`)
    }
    await fetchAssets()
  } catch (e) {
    ui.notifyError('アップロードに失敗しました: ' + (e.response?.data?.detail || e.message))
  } finally {
    uploadingSlot.value = 0
  }
}

function onDragOver(slot) {
  dragOverSlot.value = slot
}

function onDragLeave() {
  dragOverSlot.value = 0
}

async function onDrop(event, slot) {
  dragOverSlot.value = 0
  const file = event.dataTransfer.files[0]
  if (!file) return
  await uploadFile(file, slot)
}

// ---- クリップボードからの貼り付け ----
//
// 画像生成 AI の画面で画像をコピーして、この画面で貼り付けるだけで取り込める。
// 「ダウンロード → ファイル選択 → アップロード」の 3 手が消える。

/** レイアウトが使う範囲での最初の空きスロット。無ければ 0。 */
function firstEmptySlot() {
  for (let slot = 1; slot <= effectiveSlotCount.value; slot += 1) {
    if (!getAsset(slot)) return slot
  }
  return 0
}

async function onPaste(event) {
  // 入力欄にフォーカスがあるときは、その欄への貼り付けを優先する。
  // Web ページから画像をコピーすると text/html も一緒に入るため、
  // ここで譲らないとキャプション欄に貼れなくなる。
  const active = document.activeElement
  if (active && (active.tagName === 'INPUT' || active.tagName === 'TEXTAREA' || active.isContentEditable)) {
    return
  }

  // 画像が入っているときだけ横取りする。文字の貼り付けは邪魔しない。
  const items = Array.from(event.clipboardData?.items || [])
  const imageItem = items.find((i) => i.type.startsWith('image/'))
  if (!imageItem) return

  const file = imageItem.getAsFile()
  if (!file) return
  event.preventDefault()

  const slot = firstEmptySlot()
  if (!slot) {
    ui.notifyError('空きスロットがありません。入れ替えたいスロットの素材を削除してください。')
    return
  }
  await uploadFile(file, slot, `pasted${PASTE_EXTENSIONS[imageItem.type] || '.png'}`)
}

// ---- キャプション ----
//
// 画像そのものはスロットが正、キャプションはスライド内容が正。
// 親（VideoEditorView）が slideContent.images[] に書き戻す。

function captionFor(slot) {
  return props.captions[slot - 1] || ''
}

function setCaption(slot, value) {
  const next = []
  for (let s = 1; s <= effectiveSlotCount.value; s += 1) {
    next.push(s === slot ? value : (props.captions[s - 1] || ''))
  }
  emit('update:captions', next)
}

async function deleteAsset(slot) {
  if (!confirm(`スロット ${slot} の素材を削除してよろしいですか？`)) return
  try {
    await assetApi.delete(props.sceneId, slot)
    ui.notify('素材を削除しました')
    await fetchAssets()
  } catch (e) {
    ui.notifyError('削除に失敗しました: ' + e.message)
  }
}

function openSettings(slot) {
  const asset = getAsset(slot)
  if (!asset) return
  activeSlot.value = slot
  
  let cfg = {}
  try {
    cfg = JSON.parse(asset.display_config_json || '{}')
  } catch (e) {
    console.error(e)
  }

  configForm.offset_sec = cfg.offset_sec !== undefined ? cfg.offset_sec : 0.5
  configForm.duration_sec = cfg.duration_sec !== undefined ? cfg.duration_sec : null
  
  const xVal = cfg.x || 'center'
  if (['left', 'center', 'right'].includes(xVal)) {
    configForm.x = xVal
    configForm.custom_x = ''
  } else {
    configForm.x = 'custom'
    configForm.custom_x = xVal
  }

  const yVal = cfg.y || 'center'
  if (['top', 'center', 'bottom'].includes(yVal)) {
    configForm.y = yVal
    configForm.custom_y = ''
  } else {
    configForm.y = 'custom'
    configForm.custom_y = yVal
  }

  configForm.max_width = cfg.max_width || '600px'
  configForm.max_height = cfg.max_height || '500px'
  configForm.border_radius = cfg.border_radius || '16px'

  settingsDialog.value = true
}

async function saveConfig() {
  const payload = {
    offset_sec: configForm.offset_sec,
    duration_sec: configForm.duration_sec,
    x: configForm.x === 'custom' ? configForm.custom_x : configForm.x,
    y: configForm.y === 'custom' ? configForm.custom_y : configForm.y,
    max_width: configForm.max_width,
    max_height: configForm.max_height,
    border_radius: configForm.border_radius,
  }

  try {
    await assetApi.updateConfig(props.sceneId, activeSlot.value, payload)
    ui.notify('配置設定を保存しました')
    settingsDialog.value = false
    await fetchAssets()
  } catch (e) {
    ui.notifyError('設定の保存に失敗しました: ' + e.message)
  }
}

function openSvgInput(slot) {
  activeSlot.value = slot
  svgText.value = ''
  svgDialog.value = true
}

async function saveSvg() {
  try {
    await assetApi.uploadSvg(props.sceneId, activeSlot.value, svgText.value)
    ui.notify('SVG を登録しました')
    svgDialog.value = false
    await fetchAssets()
  } catch (e) {
    ui.notifyError('SVG の登録に失敗しました: ' + e.message)
  }
}
</script>

<style scoped>
.slot-wrapper {
  background: rgba(255, 255, 255, 0.03);
  /* キャプション欄の有無で高さが変わるため、固定値ではなく下限だけ決める */
  min-height: 155px;
}
/* レイアウトが使わないスロット。触れなくはしない（削除できなくなるため）が、
   見た目で「これは映らない」と分かるようにする。 */
.slot-wrapper.is-unused {
  opacity: 0.45;
}
.caption-field :deep(input) {
  font-size: 0.75rem;
}
.upload-area {
  background: rgba(255, 255, 255, 0.05);
  border: 1px dashed rgba(255, 255, 255, 0.2);
  transition: all 0.3s ease;
}
.upload-area:hover {
  background: rgba(255, 255, 255, 0.08);
  border-color: rgba(255, 255, 255, 0.4);
}
.upload-area.dragover {
  background: rgba(var(--v-theme-primary), 0.1);
  border-color: rgb(var(--v-theme-primary));
}
.upload-area.has-file {
  border-style: solid;
}
.img-preview {
  background-size: contain;
  background-position: center;
  background-repeat: no-repeat;
}
.text-xxs {
  font-size: 0.65rem;
}
</style>
