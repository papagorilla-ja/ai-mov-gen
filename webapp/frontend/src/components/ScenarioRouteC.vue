<template>
  <div class="pa-4 glass-panel d-flex flex-column" style="height: 100%; min-height: 500px;">
    <div class="d-flex align-center justify-between gap-4 mb-4 flex-wrap">
      <h3 class="text-subtitle-1 font-weight-bold">💬 AI チャットで作成</h3>
    </div>

    <!-- チャット履歴表示エリア -->
    <div
      ref="chatContainer"
      class="flex-grow-1 overflow-y-auto mb-4 pa-3 bg-black-20 rounded border border-thin"
      style="max-height: 350px; min-height: 250px;"
    >
      <div v-if="filteredMessages.length === 0" class="text-center py-8 text-medium-emphasis text-caption">
        AI に「〇〇の動画の構成を作って」などと話しかけてください。
      </div>
      <div
        v-for="(msg, index) in filteredMessages"
        :key="index"
        :class="['d-flex mb-3', msg.role === 'user' ? 'justify-end' : 'justify-start']"
      >
        <v-card
          :color="msg.role === 'user' ? 'primary' : 'rgba(255,255,255,0.08)'"
          variant="flat"
          class="glass-card max-width-70 border-thin"
          style="border-radius: 12px; max-width: 80%;"
        >
          <v-card-text class="pa-3 text-body-2 white-space-pre-wrap">
            {{ formatMessageContent(msg.content) }}
          </v-card-text>
        </v-card>
      </div>

      <!-- 送信中のローディング表示 -->
      <div v-if="scenarioStore.loading" class="d-flex justify-start mb-3">
        <v-card color="rgba(255,255,255,0.08)" variant="flat" class="glass-card">
          <v-card-text class="pa-3 d-flex align-center">
            <v-progress-circular indeterminate size="16" width="2" color="primary" class="mr-2" />
            <span class="text-caption text-medium-emphasis">AIが入力内容を考えています...</span>
          </v-card-text>
        </v-card>
      </div>
    </div>

    <!-- AI提案シナリオの検知 & 確定表示 -->
    <v-expand-transition>
      <div v-if="scenarioStore.lastProposal" class="mb-4 pa-3 border border-success rounded bg-success-20 glass-card">
        <div class="d-flex align-center mb-2">
          <v-icon color="success" icon="mdi-check-decagram" class="mr-2" />
          <span class="text-subtitle-2 font-weight-bold text-success">AI からシナリオ構成案が届きました！</span>
        </div>
        
        <div class="text-caption text-medium-emphasis max-height-150 overflow-y-auto mb-3 pl-1">
          <div v-for="item in scenarioStore.lastProposal.scenes" :key="item.index" class="mb-2">
            <strong>シーン {{ item.index }}: {{ item.title }}</strong>
            <v-chip size="x-small" variant="tonal" class="ml-1">{{ item.layout_type }}</v-chip>
            <div class="text-medium-emphasis pl-2 mt-1" style="border-left: 2px solid rgba(255,255,255,0.2);">
              {{ item.summary || item.narration_text || item.slide_content_json?.body || 'あらすじ未設定' }}
            </div>
          </div>
        </div>

        <v-btn
          color="success"
          block
          size="small"
          :loading="finalizing"
          @click="finalize"
        >
          この構成でシーンを作成（内容は各シーンで作り込みます）
        </v-btn>
      </div>
    </v-expand-transition>

    <!-- 入力フォームエリア -->
    <div class="d-flex gap-2 align-center">
      <v-text-field
        v-model="inputMsg"
        placeholder="メッセージを入力してください..."
        hint="Ctrl+Enter で送信"
        persistent-hint
        density="comfortable"
        class="glass-card"
        :disabled="scenarioStore.loading"
        @keyup.ctrl.enter="sendMessage"
      />
      <v-btn
        color="primary"
        icon="mdi-send"
        :disabled="!inputMsg.trim() || scenarioStore.loading"
        @click="sendMessage"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed, watch, nextTick } from 'vue'
import { useScenarioStore } from '@/stores/scenario'
import { useUiStore } from '@/stores/ui'

const props = defineProps({
  videoId: {
    type: String,
    required: true
  }
})

const emit = defineEmits(['finalized'])

const scenarioStore = useScenarioStore()
const ui = useUiStore()

const inputMsg = ref('')
const finalizing = ref(false)
const chatContainer = ref(null)

const filteredMessages = computed(() => {
  return scenarioStore.chatMessages.filter(m => m.role !== 'system')
})

onMounted(() => {
  scrollToBottom()
})

watch(() => filteredMessages.value.length, () => {
  scrollToBottom()
})

const sendMessage = async () => {
  if (!inputMsg.value.trim() || scenarioStore.loading) return
  const msg = inputMsg.value
  inputMsg.value = ''
  try {
    await scenarioStore.sendChatMessage(props.videoId, msg)
  } catch (e) {
    ui.notifyError('AI チャット送信に失敗しました: ' + e.message)
  }
}

const finalize = async () => {
  if (!scenarioStore.lastProposal || !scenarioStore.lastProposal.scenes) return
  finalizing.value = true
  try {
    await scenarioStore.finalizeScenario(props.videoId, scenarioStore.lastProposal.scenes)
    ui.notify('チャットからシナリオを確定し、シーンを作成しました。')
    emit('finalized')
  } catch (e) {
    ui.notifyError('シナリオの確定に失敗しました: ' + e.message)
  } finally {
    finalizing.value = false
  }
}

const formatMessageContent = (text) => {
  return text.replace(/```(?:json)?\s*\{.*?\}\s*```/gs, '(シナリオ構成案を生成しました。下部のボタンから確定できます。)').trim()
}

const scrollToBottom = () => {
  nextTick(() => {
    if (chatContainer.value) {
      chatContainer.value.scrollTop = chatContainer.value.scrollHeight
    }
  })
}
</script>

<style scoped>
.max-height-150 {
  max-height: 150px;
}
.white-space-pre-wrap {
  white-space: pre-wrap;
}
.bg-black-20 {
  background-color: rgba(0, 0, 0, 0.2);
}
.bg-success-20 {
  background-color: rgba(76, 175, 80, 0.08);
}
.gap-2 {
  gap: 8px;
}
.gap-4 {
  gap: 16px;
}
</style>
