import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '@/api/index.js'
import { useUiStore } from './ui'

export const useSpeakersStore = defineStore('speakers', () => {
  const speakers = ref([])
  const loading = ref(false)
  const ui = useUiStore()

  async function fetchAll() {
    loading.value = true
    try {
      const { data } = await api.get('/speakers')
      speakers.value = data
    } catch (e) {
      ui.notifyError(e.message)
    } finally {
      loading.value = false
    }
  }

  return { speakers, loading, fetchAll }
})
