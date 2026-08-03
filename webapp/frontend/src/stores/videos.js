import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '@/api/index.js'
import { useUiStore } from './ui'

export const useVideosStore = defineStore('videos', () => {
  const videos = ref([])
  const currentVideo = ref(null)
  const loading = ref(false)
  const ui = useUiStore()

  async function fetchAll(projectId) {
    loading.value = true
    try {
      const { data } = await api.get(`/projects/${projectId}/videos`)
      videos.value = data
    } catch (e) {
      ui.notifyError(e.message)
    } finally {
      loading.value = false
    }
  }

  async function fetchOne(videoId) {
    loading.value = true
    try {
      const { data } = await api.get(`/videos/${videoId}`)
      currentVideo.value = data
      return data
    } catch (e) {
      ui.notifyError(e.message)
    } finally {
      loading.value = false
    }
  }

  async function create(projectId, payload) {
    loading.value = true
    try {
      const { data } = await api.post(`/projects/${projectId}/videos`, payload)
      videos.value.push(data)
      ui.notify('動画を作成しました')
      return data
    } catch (e) {
      ui.notifyError(e.message)
      throw e
    } finally {
      loading.value = false
    }
  }

  async function update(videoId, payload) {
    loading.value = true
    try {
      const { data } = await api.patch(`/videos/${videoId}`, payload)
      if (currentVideo.value && currentVideo.value.id === videoId) {
        currentVideo.value = data
      }
      videos.value = videos.value.map(v => v.id === videoId ? data : v)
      ui.notify('動画設定を更新しました')
      return data
    } catch (e) {
      ui.notifyError(e.message)
      throw e
    } finally {
      loading.value = false
    }
  }

  async function remove(videoId) {
    loading.value = true
    try {
      await api.delete(`/videos/${videoId}`)
      videos.value = videos.value.filter(v => v.id !== videoId)
      ui.notify('動画を削除しました')
    } catch (e) {
      ui.notifyError(e.message)
    } finally {
      loading.value = false
    }
  }

  async function duplicate(videoId) {
    loading.value = true
    try {
      const { data } = await api.post(`/videos/${videoId}/duplicate`)
      videos.value.push(data)
      ui.notify('動画を複製しました')
      return data
    } catch (e) {
      ui.notifyError(e.message)
      throw e
    } finally {
      loading.value = false
    }
  }

  const currentStyle = ref(null)

  async function fetchStyle(videoId) {
    try {
      const { data } = await api.get(`/videos/${videoId}/style`)
      currentStyle.value = data
      return data
    } catch (e) {
      ui.notifyError(e.message)
    }
  }

  async function updateStyle(videoId, payload) {
    try {
      const { data } = await api.patch(`/videos/${videoId}/style`, payload)
      currentStyle.value = data
      ui.notify('スタイルを更新しました')
      return data
    } catch (e) {
      ui.notifyError(e.message)
      throw e
    }
  }

  return { videos, currentVideo, currentStyle, loading, fetchAll, fetchOne, create, update, remove, duplicate, fetchStyle, updateStyle }
})
