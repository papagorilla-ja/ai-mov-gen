import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '@/api/index.js'
import { useUiStore } from './ui'

export const useProjectsStore = defineStore('projects', () => {
  const projects = ref([])
  const currentProject = ref(null)
  const loading = ref(false)
  const ui = useUiStore()

  async function fetchAll() {
    loading.value = true
    try {
      const { data } = await api.get('/projects')
      projects.value = data
    } catch (e) {
      ui.notifyError(e.message)
    } finally {
      loading.value = false
    }
  }

  async function fetchOne(id) {
    loading.value = true
    try {
      const { data } = await api.get(`/projects/${id}`)
      currentProject.value = data
      return data
    } catch (e) {
      ui.notifyError(e.message)
    } finally {
      loading.value = false
    }
  }

  async function create(payload) {
    loading.value = true
    try {
      const { data } = await api.post('/projects', payload)
      projects.value.push(data)
      ui.notify('プロジェクトを作成しました')
      return data
    } catch (e) {
      ui.notifyError(e.message)
      throw e
    } finally {
      loading.value = false
    }
  }

  async function remove(id) {
    loading.value = true
    try {
      await api.delete(`/projects/${id}`)
      projects.value = projects.value.filter(p => p.id !== id)
      ui.notify('削除しました')
    } catch (e) {
      ui.notifyError(e.message)
    } finally {
      loading.value = false
    }
  }

  return { projects, currentProject, loading, fetchAll, fetchOne, create, remove }
})
