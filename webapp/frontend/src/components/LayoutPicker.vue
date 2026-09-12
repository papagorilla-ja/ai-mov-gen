<template>
  <v-dialog v-model="open" max-width="1280" scrollable>
    <v-card>
      <v-card-title class="d-flex align-center pa-4">
        <v-icon class="mr-2">mdi-view-dashboard-variant-outline</v-icon>
        レイアウトを選ぶ
        <v-spacer />
        <v-btn icon="mdi-close" variant="text" @click="open = false" />
      </v-card-title>
      <v-divider />

      <v-card-text class="pa-0" style="height: 70vh;">
        <div class="d-flex" style="height: 100%;">
          <!-- 左: 情報の型 -->
          <v-list density="compact" class="picker-side py-2" nav>
            <v-list-subheader class="text-caption">情報の型</v-list-subheader>
            <v-list-item
              v-for="group in groups"
              :key="group.type"
              :active="group.type === activeType"
              rounded="lg"
              @click="activeType = group.type"
            >
              <v-list-item-title class="text-body-2">{{ group.label }}</v-list-item-title>
              <v-list-item-subtitle class="text-caption">
                {{ group.layouts.length }} 種
              </v-list-item-subtitle>
              <template #append>
                <v-icon v-if="group.type === currentType" size="14" color="primary">mdi-circle-medium</v-icon>
              </template>
            </v-list-item>
          </v-list>

          <v-divider vertical />

          <!-- 右: 見せ方のギャラリー -->
          <div class="flex-grow-1 pa-4 overflow-y-auto">
            <p class="text-caption text-medium-emphasis mb-4">{{ activeGroup?.description }}</p>

            <v-alert
              v-if="activeType !== currentType"
              type="info" variant="tonal" density="compact"
              class="mb-4 text-caption" icon="mdi-swap-horizontal"
            >
              いまと違う型です。選ぶと内容を「{{ activeGroup?.label }}」の形に移し替えます。
            </v-alert>

            <v-row dense>
              <v-col v-for="layout in activeGroup?.layouts || []" :key="layout.id" cols="12" sm="6" md="4">
                <v-card
                  :variant="layout.id === modelValue ? 'tonal' : 'outlined'"
                  :color="layout.id === modelValue ? 'primary' : undefined"
                  class="h-100 d-flex flex-column"
                  @click="choose(layout)"
                >
                  <!-- サムネイルは画像ではなく実物。iframe で CSS を隔離する
                       （スライドの CSS は :root や #stage を書き換えるため、
                       直接埋め込むと編集画面の見た目を壊す）。

                       sandbox は付けない。この文書は
                         - サーバーがレジストリのサンプル内容から生成したもので、
                           ユーザーの入力を含まない
                         - 原寸 1920px を枠幅に合わせて縮小するスクリプトを含む
                           （CSS だけでは倍率を計算できない）
                         - 同梱フォントを /template-assets から読む（別オリジン扱いだと
                           CORS で書体が落ちる）
                       の 3 点による。pointer-events も切ってあるので操作はできない。 -->
                  <div class="picker-thumb">
                    <iframe
                      v-if="samples[layout.id]"
                      :srcdoc="samples[layout.id]"
                      loading="lazy"
                      title=""
                    />
                    <v-progress-circular v-else indeterminate size="22" width="2" color="primary" />
                  </div>
                  <v-card-item class="pb-2">
                    <v-card-title class="text-body-2 font-weight-bold">{{ layout.label }}</v-card-title>
                    <v-card-subtitle class="text-caption">{{ capacityText(layout) }}</v-card-subtitle>
                  </v-card-item>
                  <v-card-text class="pt-0 text-caption text-medium-emphasis flex-grow-1">
                    {{ layout.when_to_use }}
                  </v-card-text>
                  <v-card-actions class="pt-0">
                    <v-chip
                      v-if="fits(layout)"
                      size="x-small" color="success" variant="tonal" prepend-icon="mdi-check"
                    >いまの内容で使える</v-chip>
                    <v-chip
                      v-else
                      size="x-small" color="warning" variant="tonal" prepend-icon="mdi-alert-outline"
                    >{{ fitWarning(layout) }}</v-chip>
                  </v-card-actions>
                </v-card>
              </v-col>
            </v-row>
          </div>
        </div>
      </v-card-text>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useLayoutsStore } from '@/stores/layouts'

const props = defineProps({
  modelValue: { type: String, default: 'text_only' },  // 選択中のレイアウト ID
  itemCount: { type: Number, default: 0 },             // いまの内容の件数
  videoId: { type: String, default: null },            // サムネイルをこの動画のテーマで描く
})
const emit = defineEmits(['update:modelValue', 'select'])

const layoutsStore = useLayoutsStore()
const open = defineModel('open', { type: Boolean, default: false })

const activeType = ref(null)
const samples = ref({})

const groups = computed(() => layoutsStore.catalog.filter(g => g.layouts.length > 0))
const currentType = computed(() => layoutsStore.byId[props.modelValue]?.type || null)
const activeGroup = computed(() => groups.value.find(g => g.type === activeType.value) || groups.value[0])

function capacityText(layout) {
  if (layout.any_count) return '件数の制限なし'
  if (layout.min === layout.max) return `${layout.min} 件`
  return `${layout.min}〜${layout.max} 件`
}
function fits(layout) {
  if (layout.any_count) return true
  return props.itemCount >= layout.min && props.itemCount <= layout.max
}
function fitWarning(layout) {
  if (props.itemCount > layout.max) return `${layout.max} 件までに収まるよう調整されます`
  return `${layout.min} 件以上が必要です`
}

function choose(layout) {
  emit('update:modelValue', layout.id)
  emit('select', layout)
  open.value = false
}

// ダイアログを開いたとき、いまの型のタブを選び、その型のサムネイルだけ取りに行く。
// 40 種ぶんを一度に読むと重いため、表示する分だけ遅延で取得する。
watch(open, async (v) => {
  if (!v) return
  await layoutsStore.fetchCatalog()
  activeType.value = currentType.value || groups.value[0]?.type
  loadSamples()
})
watch(activeType, loadSamples)

async function loadSamples() {
  const group = activeGroup.value
  if (!group) return
  for (const layout of group.layouts) {
    if (samples.value[layout.id]) continue
    try {
      samples.value[layout.id] = await layoutsStore.fetchSample(layout.id, props.videoId)
    } catch {
      samples.value[layout.id] = '<p style="color:#888;font:12px sans-serif">プレビューを取得できませんでした</p>'
    }
  }
}
</script>

<style scoped>
.picker-side { width: 170px; flex: none; overflow-y: auto; }
/* サムネイルは 16:9 の枠に原寸のスライドを縮小して収める */
.picker-thumb {
  aspect-ratio: 16 / 9;
  background: #0b0b14;
  display: flex; align-items: center; justify-content: center;
  overflow: hidden;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}
.picker-thumb iframe { width: 100%; height: 100%; border: 0; display: block; pointer-events: none; }
</style>
