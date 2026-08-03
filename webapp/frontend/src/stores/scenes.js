import { defineStore } from 'pinia'
import { ref, reactive } from 'vue'
import { api, longApi } from '@/api/index.js'
import { scenarioApi } from '@/api/scenario.js'
import { useUiStore } from './ui'

export const useScenesStore = defineStore('scenes', () => {
  const scenes = ref([])
  const loading = ref(false)
  const previewAudioUrl = ref('')
  const ui = useUiStore()

  async function fetchAll(videoId) {
    loading.value = true
    try {
      const { data } = await api.get(`/videos/${videoId}/scenes`)
      scenes.value = data
    } catch (e) {
      ui.notifyError(e.message)
    } finally {
      loading.value = false
    }
  }

  async function create(videoId, payload) {
    loading.value = true
    try {
      const { data } = await api.post(`/videos/${videoId}/scenes`, payload)
      scenes.value.push(data)
      ui.notify('シーンを追加しました')
      return data
    } catch (e) {
      ui.notifyError(e.message)
      throw e
    } finally {
      loading.value = false
    }
  }

  async function update(sceneId, payload) {
    loading.value = true
    try {
      const { data } = await api.patch(`/scenes/${sceneId}`, payload)
      scenes.value = scenes.value.map(s => s.id === sceneId ? data : s)
      return data
    } catch (e) {
      ui.notifyError(e.message)
      throw e
    } finally {
      loading.value = false
    }
  }

  async function remove(sceneId) {
    loading.value = true
    try {
      await api.delete(`/scenes/${sceneId}`)
      scenes.value = scenes.value.filter(s => s.id !== sceneId)
      ui.notify('シーンを削除しました')
    } catch (e) {
      ui.notifyError(e.message)
    } finally {
      loading.value = false
    }
  }

  async function reorder(sceneId, newIndex) {
    loading.value = true
    try {
      const { data } = await api.post(`/scenes/${sceneId}/reorder`, { new_index: newIndex })
      scenes.value = data
    } catch (e) {
      ui.notifyError(e.message)
    } finally {
      loading.value = false
    }
  }

  async function applyDesignAdjust(sceneId, instruction) {
    const { data } = await longApi.post(`/scenes/${sceneId}/ai-design-adjust`, { instruction })
    const idx = scenes.value.findIndex(s => s.id === sceneId)
    if (idx !== -1) scenes.value[idx] = data
    return data
  }

  async function fetchEffectiveCode(sceneId) {
    const { data } = await api.get(`/scenes/${sceneId}/effective-html`)
    return data  // { html, css, is_custom }
  }

  // 音声合成はバックグラウンドジョブとして実行される（処理に数十秒〜数分かかる場合があるため）。
  // start でジョブを開始し、status を軽量ポーリングして完了を待ち、最後に audio を取得する。
  async function playPreview(sceneId, onStatusUpdate) {
    const { data: startData } = await api.post(`/scenes/${sceneId}/preview-audio/start`)
    const jobId = startData.job_id

    const pollIntervalMs = 1500
    const maxWaitMs = 6 * 60 * 1000 // バックエンド側のTTSタイムアウト(300秒)より余裕を持たせる
    const startedAt = Date.now()

    while (true) {
      const { data: statusData } = await api.get(`/scenes/preview-audio/${jobId}/status`)
      if (statusData.status === 'done') break
      if (statusData.status === 'error') {
        throw new Error(statusData.error || '音声合成に失敗しました')
      }
      if (Date.now() - startedAt > maxWaitMs) {
        throw new Error('音声合成がタイムアウトしました（6分経過）。TTSサーバーの状態を確認してください。')
      }
      if (onStatusUpdate) {
        onStatusUpdate(Math.round((Date.now() - startedAt) / 1000))
      }
      await new Promise((resolve) => setTimeout(resolve, pollIntervalMs))
    }

    const { data: audioBlob } = await api.get(`/scenes/preview-audio/${jobId}/audio`, { responseType: 'blob' })
    
    if (previewAudioUrl.value) {
      URL.revokeObjectURL(previewAudioUrl.value)
    }
    previewAudioUrl.value = URL.createObjectURL(audioBlob)

    const audio = new Audio(previewAudioUrl.value)
    await audio.play()
    return previewAudioUrl.value
  }

  const bulkGenLoading = ref(false)
  const bulkGenProgress = reactive({ done: 0, total: 0, currentTitle: '' })

  async function generateAllContent(videoId, onlyEmpty = true, onProgress) {
    bulkGenLoading.value = true
    try {
      const { data: startData } = await scenarioApi.startGenerateAllContent(videoId, onlyEmpty)
      const jobId = startData.job_id
      const pollIntervalMs = 2000

      while (true) {
        const { data: statusData } = await scenarioApi.getGenerateAllContentStatus(jobId)
        bulkGenProgress.done = statusData.done || 0
        bulkGenProgress.total = statusData.total || 0
        bulkGenProgress.currentTitle = statusData.current_title || ''

        if (onProgress) onProgress(statusData)

        if (statusData.status === 'completed') break
        if (statusData.status === 'error') {
          throw new Error(statusData.error || '一括生成に失敗しました')
        }
        await new Promise((resolve) => setTimeout(resolve, pollIntervalMs))
      }

      await fetchAll(videoId)
      ui.notify('全シーンの AI 内容生成が完了しました。')
    } catch (e) {
      ui.notifyError(e.message)
      throw e
    } finally {
      bulkGenLoading.value = false
    }
  }

  return {
    scenes,
    loading,
    previewAudioUrl,
    bulkGenLoading,
    bulkGenProgress,
    fetchAll,
    create,
    update,
    remove,
    reorder,
    applyDesignAdjust,
    fetchEffectiveCode,
    playPreview,
    generateAllContent
  }
})
