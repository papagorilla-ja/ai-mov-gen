import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '@/api/index.js'
import { useUiStore } from './ui'

export const useGenerationStore = defineStore('generation', () => {
  const histories = ref([])
  const currentProgress = ref(null)
  const loading = ref(false)
  const ui = useUiStore()
  let ws = null

  async function fetchHistories(videoId) {
    loading.value = true
    try {
      const { data } = await api.get(`/videos/${videoId}/generations`)
      histories.value = data
    } catch (e) {
      ui.notifyError(e.message)
    } finally {
      loading.value = false
    }
  }

  // regenerateAudio=true で既存のナレーション音声を削除してから合成し直す
  // （話者の変更や参照音声の録り直しを確実に反映させるため）
  async function generate(videoId, regenerateAudio = false) {
    loading.value = true
    try {
      const { data } = await api.post(
        `/videos/${videoId}/generate?regenerate_audio=${regenerateAudio}`
      )
      ui.notify(
        regenerateAudio
          ? '音声を再作成して動画生成を開始しました'
          : '動画生成プロセスを開始しました'
      )
      connectWebSocket(videoId)
      return data
    } catch (e) {
      ui.notifyError(e.message)
      throw e
    } finally {
      loading.value = false
    }
  }

  function connectWebSocket(videoId) {
    if (ws) {
      ws.close()
    }
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${protocol}//${window.location.host}/ws/videos/${videoId}/generation-progress`
    
    ws = new WebSocket(wsUrl)
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        currentProgress.value = data
        if (data.step === 'failed' || data.error) {
          const errMsg = data.error || data.message || '生成に失敗しました'
          ui.notifyError('動画生成エラー: ' + errMsg)
          fetchHistories(videoId)
          ws.close()
        } else if (data.step === 'rendering' && data.progress === 1.0) {
          ui.notify('動画生成が完了しました！')
          fetchHistories(videoId)
          ws.close()
        }
      } catch (e) {
        console.error('WS Parse Error', e)
      }
    }
    ws.onclose = () => {
      console.log('WS Connection Closed')
    }
  }

  function disconnectWebSocket() {
    if (ws) {
      ws.close()
      ws = null
    }
  }

  async function fetchGenerationStatus(videoId) {
    try {
      const { data } = await api.get(`/videos/${videoId}/generation-status`)
      if (data) {
        if (data.status === 'running') {
          currentProgress.value = {
            step: 'generating',
            progress: 0.1,
            message: '動画を生成中...'
          }
          connectWebSocket(videoId)
        } else if (data.status === 'completed') {
          currentProgress.value = {
            step: 'rendering',
            progress: 1.0,
            message: '生成完了'
          }
        } else if (data.status === 'failed') {
          currentProgress.value = {
            step: 'failed',
            progress: 1.0,
            message: '生成失敗',
            error: data.error_message
          }
        }
      }
    } catch (e) {
      console.warn('fetchGenerationStatus error', e)
    }
  }

  async function remove(generationId) {
    loading.value = true
    try {
      await api.delete(`/generations/${generationId}`)
      histories.value = histories.value.filter(h => h.id !== generationId)
      ui.notify('生成履歴を削除しました')
    } catch (e) {
      ui.notifyError(e.message)
    } finally {
      loading.value = false
    }
  }

  async function resetStatus(videoId) {
    loading.value = true
    try {
      await api.post(`/videos/${videoId}/reset-status`)
      currentProgress.value = null
      disconnectWebSocket()
      await fetchHistories(videoId)
      ui.notify('生成ステータスを強制リセットしました')
    } catch (e) {
      ui.notifyError(e.message)
    } finally {
      loading.value = false
    }
  }

  function downloadUrl(generationId) {
    return `${api.defaults.baseURL}/generations/${generationId}/download`
  }

  function playUrl(generationId) {
    return `${api.defaults.baseURL}/generations/${generationId}/play`
  }

  return { histories, currentProgress, loading, fetchHistories, fetchGenerationStatus, generate, resetStatus, remove, connectWebSocket, disconnectWebSocket, downloadUrl, playUrl }
})
