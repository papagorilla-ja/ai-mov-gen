<template>
  <div v-if="typeDef">
    <template v-for="field in typeDef.fields" :key="field.name">
      <!-- ── 1 行入力 ─────────────────────────────── -->
      <v-text-field
        v-if="field.kind === 'text'"
        v-model="content[field.name]"
        :label="field.label"
        :hint="hintFor(field)"
        :counter="field.max_chars || undefined"
        persistent-hint
        class="mb-4"
      />

      <!-- ── 複数行入力 ───────────────────────────── -->
      <v-textarea
        v-else-if="field.kind === 'textarea'"
        v-model="content[field.name]"
        :label="field.label"
        :hint="hintFor(field)"
        :counter="field.max_chars || undefined"
        rows="3"
        persistent-hint
        class="mb-4"
      />

      <!-- ── 選択肢 ───────────────────────────────── -->
      <v-select
        v-else-if="field.kind === 'choice'"
        v-model="content[field.name]"
        :items="field.options"
        :label="field.label"
        :hint="hintFor(field)"
        persistent-hint
        class="mb-4"
      />

      <!-- ── 入れ子オブジェクト ───────────────────── -->
      <v-card v-else-if="field.kind === 'group'" variant="outlined" class="pa-3 mb-4">
        <div class="text-subtitle-2 font-weight-bold mb-2">{{ field.label }}</div>
        <component
          :is="child.kind === 'textarea' ? 'v-textarea' : 'v-text-field'"
          v-for="child in field.children"
          :key="child.name"
          v-model="groupValue(field.name)[child.name]"
          :label="child.label"
          :hint="child.hint"
          :counter="child.max_chars || undefined"
          :rows="child.kind === 'textarea' ? 2 : undefined"
          density="compact"
          class="mb-2"
        />
      </v-card>

      <!-- ── 繰り返し項目 ─────────────────────────── -->
      <div v-else-if="field.kind === 'items'" class="mb-4">
        <div class="d-flex align-center mb-2">
          <span class="text-subtitle-2 font-weight-bold">{{ field.label }}</span>
          <v-chip size="x-small" variant="tonal" class="ml-2">{{ listValue(field.name).length }} 件</v-chip>
          <v-spacer />
          <v-btn
            v-if="!field.fixed_count"
            size="small" variant="outlined" color="primary" prepend-icon="mdi-plus"
            @click="addItem(field)"
          >追加</v-btn>
        </div>
        <div v-if="hintFor(field)" class="text-caption text-medium-emphasis mb-2">{{ hintFor(field) }}</div>

        <v-card
          v-for="(item, idx) in listValue(field.name)" :key="idx"
          variant="outlined" class="pa-3 mb-2"
        >
          <div class="d-flex align-center mb-2">
            <v-chip size="x-small" variant="tonal" color="primary">{{ idx + 1 }}</v-chip>
            <v-spacer />
            <template v-if="!field.fixed_count">
              <v-btn icon="mdi-arrow-up" size="x-small" variant="text" :disabled="idx === 0"
                     @click="moveItem(field.name, idx, -1)" />
              <v-btn icon="mdi-arrow-down" size="x-small" variant="text"
                     :disabled="idx === listValue(field.name).length - 1"
                     @click="moveItem(field.name, idx, 1)" />
              <v-btn icon="mdi-delete-outline" size="x-small" variant="text" color="error"
                     @click="listValue(field.name).splice(idx, 1)" />
            </template>
          </div>
          <template v-for="child in field.children" :key="child.name">
            <v-select
              v-if="child.kind === 'choice'"
              v-model="item[child.name]" :items="child.options" :label="child.label"
              density="compact" hide-details class="mb-2"
            />
            <v-textarea
              v-else-if="child.kind === 'textarea'"
              v-model="item[child.name]" :label="child.label" :hint="child.hint"
              :counter="child.max_chars || undefined" rows="2" density="compact" class="mb-2"
            />
            <v-text-field
              v-else
              v-model="item[child.name]" :label="child.label" :hint="child.hint"
              :counter="child.max_chars || undefined" density="compact" class="mb-2"
            />
          </template>
        </v-card>

        <div v-if="!listValue(field.name).length"
             class="text-center py-4 text-caption text-medium-emphasis border border-dashed rounded">
          項目がありません。「追加」から入力するか、「AI でシーン内容を生成」を実行してください。
        </div>
      </div>

      <!-- ── 階層（専用エディタ） ─────────────────── -->
      <div v-else-if="field.kind === 'tree'" class="mb-4">
        <div class="text-subtitle-2 font-weight-bold mb-1">{{ field.label }}</div>
        <div v-if="hintFor(field)" class="text-caption text-medium-emphasis mb-2">{{ hintFor(field) }}</div>
        <LayoutTreeField v-model="content[field.name]" />
      </div>

      <!-- ── 表（専用エディタ） ───────────────────── -->
      <div v-else-if="field.kind === 'table'" class="mb-4">
        <div class="text-subtitle-2 font-weight-bold mb-1">{{ field.label }}</div>
        <div v-if="hintFor(field)" class="text-caption text-medium-emphasis mb-2">{{ hintFor(field) }}</div>
        <v-text-field
          :model-value="(content.headers || []).join(', ')"
          label="見出し行（カンマ区切り）" density="compact" class="mb-2"
          @update:model-value="setHeaders"
        />
        <v-textarea
          :model-value="rowsText"
          label="データ行（1行 = 1レコード / カンマ区切り）" rows="5" density="compact"
          @update:model-value="setRows"
        />
        <div class="text-caption text-medium-emphasis">
          ※ 各行の項目数は見出し行に自動で揃えられます（足りない分は空欄、多い分は切り捨て）。
        </div>
      </div>

      <!-- ── グラフ（専用エディタ） ───────────────── -->
      <div v-else-if="field.kind === 'chart'" class="mb-4">
        <div class="text-subtitle-2 font-weight-bold mb-2">{{ field.label }}</div>
        <v-select
          v-model="chart.type" :items="chartTypes" label="グラフ種別" density="compact" class="mb-2"
        />
        <v-text-field
          :model-value="(chart.labels || []).join(', ')" label="ラベル（カンマ区切り）"
          density="compact" class="mb-2" @update:model-value="v => chart.labels = splitCsv(v)"
        />
        <v-text-field
          :model-value="(chart.values || []).join(', ')" label="数値（カンマ区切り）"
          density="compact" class="mb-2" @update:model-value="v => chart.values = splitCsv(v).map(Number)"
        />
        <v-text-field v-model="chart.unit" label="単位・凡例" density="compact" />
        <div class="text-caption text-medium-emphasis">※ ラベルと数値は同じ個数にしてください。</div>
      </div>

      <!-- ── 画像 ─────────────────────────────────
           取り込みは下の「素材スロット」に一本化している。
           以前はここにもファイル選択欄があり、同じ素材スロットを
           2 か所から触れる状態だったため、どちらが正か画面から分からなかった。
           枚数はレイアウトの capacity が決めるので「枠を追加」も置かない。 -->
      <div v-else-if="field.kind === 'images'" class="mb-4">
        <div class="text-subtitle-2 font-weight-bold mb-1">{{ field.label }}</div>
        <div v-if="hintFor(field)" class="text-caption text-medium-emphasis mb-2">{{ hintFor(field) }}</div>
        <v-alert type="info" variant="tonal" density="compact" class="text-caption">
          画像の取り込みとキャプションは、下の「素材スロット」で行います。
        </v-alert>
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import LayoutTreeField from './LayoutTreeField.vue'

/**
 * 型のスキーマから編集フォームを組み立てる。
 *
 * 画面側にレイアウト別の分岐は書かない。項目の定義は /api/v1/layouts が配る。
 * 新しいレイアウトを既存の型に足しても、このファイルは変更不要。
 */
const props = defineProps({
  modelValue: { type: Object, required: true },   // 正規化済みの slide_content_json
  typeDef: { type: Object, default: null },       // /api/v1/layouts の types の 1 件
  // そのレイアウトでしか起きない挙動の注記 { フィールド名: 説明 }。
  // レイアウトの spec.py が field_notes として宣言する。
  fieldNotes: { type: Object, default: () => ({}) },
})

const content = computed(() => props.modelValue)

/**
 * 項目の下に出す説明文。
 *
 * 型の hint（同じ型のレイアウト全部に共通）に、レイアウト固有の注記を足す。
 * 「数字を入れるとカウントアップする」のような、そのレイアウトでしか
 * 起きない挙動は言われないと気づけないため、入力欄のすぐ下に置く。
 */
function hintFor(field) {
  const note = props.fieldNotes?.[field.name]
  if (!note) return field.hint || ''
  return field.hint ? `${field.hint}　※ ${note}` : `※ ${note}`
}

const chartTypes = [
  { title: '棒グラフ（項目の比較）', value: 'bar' },
  { title: '折れ線（推移）', value: 'line' },
  { title: '円グラフ（構成比）', value: 'pie' },
]

/** 配列フィールドを必ず配列として返す（未生成のシーンでは undefined のことがある） */
function listValue(name) {
  if (!Array.isArray(content.value[name])) content.value[name] = []
  return content.value[name]
}
/** 入れ子オブジェクトを必ずオブジェクトとして返す */
function groupValue(name) {
  if (typeof content.value[name] !== 'object' || content.value[name] === null) {
    content.value[name] = {}
  }
  return content.value[name]
}

const chart = computed(() => {
  if (typeof content.value.chart !== 'object' || content.value.chart === null) {
    content.value.chart = { type: 'bar', labels: [], values: [], unit: '' }
  }
  return content.value.chart
})

function addItem(field) {
  const blank = {}
  field.children.forEach((c) => { blank[c.name] = c.kind === 'choice' ? (c.options[0] || '') : '' })
  listValue(field.name).push(blank)
}
function moveItem(name, idx, dir) {
  const list = listValue(name)
  const to = idx + dir
  if (to < 0 || to >= list.length) return
  ;[list[idx], list[to]] = [list[to], list[idx]]
}

function splitCsv(v) {
  return String(v || '').split(',').map(s => s.trim()).filter(Boolean)
}
function setHeaders(v) {
  content.value.headers = splitCsv(v)
}
const rowsText = computed(() =>
  (content.value.rows || []).map(r => (Array.isArray(r) ? r.join(', ') : String(r))).join('\n')
)
function setRows(v) {
  content.value.rows = String(v || '')
    .split('\n').map(line => line.trim()).filter(Boolean)
    .map(line => line.split(',').map(c => c.trim()))
}
</script>
