<template>
  <div class="assets-slot-container pa-4 border border-thin rounded glass-card">
    <div class="text-subtitle-2 font-weight-bold mb-3">素材スロット (最大 3 スロット)</div>

    <v-row dense>
      <v-col v-for="slotNum in [1, 2, 3]" :key="slotNum" cols="4">
        <div class="slot-wrapper d-flex flex-column align-center pa-2 border border-thin rounded glass-card position-relative">
          <div class="text-caption font-weight-medium mb-1 text-medium-emphasis">スロット {{ slotNum }}</div>
          
          <div
            class="upload-area d-flex flex-column align-center justify-center cursor-pointer rounded overflow-hidden"
            :class="{ 'has-file': getAsset(slotNum), 'dragover': isDragOver[slotNum] }"
            style="width: 100%; height: 100px; position: relative;"
            @dragover.prevent="onDragOver(slotNum)"
            @dragleave.prevent="onDragLeave(slotNum)"
            @drop.prevent="onDrop($event, slotNum)"
            @click="triggerFileInput(slotNum)"
          >
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
import { ref, reactive, onMounted, watch } from 'vue'
import { assetApi } from '@/api/asset'
import { useUiStore } from '@/stores/ui'

const props = defineProps({
  sceneId: {
    type: String,
    required: true
  }
})

const emit = defineEmits(['change'])
const ui = useUiStore()

const assets = ref([])
const fileInputs = ref({})
const isDragOver = reactive({ 1: false, 2: false, 3: false })

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

onMounted(async () => {
  await fetchAssets()
})

watch(() => props.sceneId, async () => {
  await fetchAssets()
})

async function fetchAssets() {
  if (!props.sceneId) return
  try {
    const { data } = await assetApi.list(props.sceneId)
    assets.value = data
    emit('change', data)
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

async function uploadFile(file, slot) {
  const ext = file.name.split('.').pop().toLowerCase()
  let assetType = 'image'
  if (ext === 'svg') {
    assetType = 'svg'
  } else if (ext === 'mp4' || ext === 'webm') {
    assetType = 'video'
  }

  try {
    if (assetType === 'svg') {
      const reader = new FileReader()
      reader.onload = async (e) => {
        const svgContent = e.target.result
        await assetApi.uploadSvg(props.sceneId, slot, svgContent)
        ui.notify('SVG を登録しました')
        await fetchAssets()
      }
      reader.readAsText(file)
    } else {
      await assetApi.upload(props.sceneId, slot, file, assetType)
      ui.notify('素材をアップロードしました')
      await fetchAssets()
    }
  } catch (e) {
    ui.notifyError('アップロードに失敗しました: ' + (e.response?.data?.detail || e.message))
  }
}

function onDragOver(slot) {
  isDragOver[slot] = true
}

function onDragLeave(slot) {
  isDragOver[slot] = false
}

async function onDrop(event, slot) {
  isDragOver[slot] = false
  const file = event.dataTransfer.files[0]
  if (!file) return
  await uploadFile(file, slot)
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
  height: 155px;
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
