<template>
  <div class="tree-level">
    <div v-for="(node, idx) in nodes" :key="idx" class="tree-node">
      <div class="d-flex align-center gap-2 mb-1">
        <v-icon size="14" class="text-medium-emphasis">mdi-subdirectory-arrow-right</v-icon>
        <v-text-field
          v-model="node.label" label="見出し" density="compact" hide-details variant="outlined"
        />
        <v-btn icon="mdi-arrow-up" size="x-small" variant="text" :disabled="idx === 0" @click="move(idx, -1)" />
        <v-btn icon="mdi-arrow-down" size="x-small" variant="text" :disabled="idx === nodes.length - 1" @click="move(idx, 1)" />
        <v-btn
          v-if="depth < 2" icon="mdi-plus" size="x-small" variant="text"
          title="下の階層を追加" @click="addChild(node)"
        />
        <v-btn icon="mdi-delete-outline" size="x-small" variant="text" color="error" @click="nodes.splice(idx, 1)" />
      </div>
      <v-text-field
        v-model="node.text" label="説明" density="compact" hide-details variant="outlined" class="mb-2"
      />
      <!-- 階層は最大 3 段。これ以上深くすると図として読めなくなるため、
           UI 側でも追加ボタンを出さない -->
      <LayoutTreeField
        v-if="node.children && node.children.length"
        v-model="node.children" :depth="depth + 1"
      />
    </div>
    <v-btn
      size="small" variant="text" prepend-icon="mdi-plus" class="mt-1"
      @click="nodes.push({ label: '', text: '', children: [] })"
    >
      {{ depth === 0 ? '項目を追加' : 'この階層に追加' }}
    </v-btn>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  modelValue: { type: Array, default: () => [] },
  depth: { type: Number, default: 0 },
})
const emit = defineEmits(['update:modelValue'])

const nodes = computed({
  get: () => props.modelValue || [],
  set: (v) => emit('update:modelValue', v),
})

function move(idx, dir) {
  const list = nodes.value
  const to = idx + dir
  if (to < 0 || to >= list.length) return
  ;[list[idx], list[to]] = [list[to], list[idx]]
}
function addChild(node) {
  if (!node.children) node.children = []
  node.children.push({ label: '', text: '', children: [] })
}
</script>

<style scoped>
.tree-level { padding-left: 10px; border-left: 2px solid rgba(255, 255, 255, 0.08); }
.tree-node { margin-bottom: 10px; }
</style>
