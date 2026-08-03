import { defineStore } from 'pinia'
import { styleApi } from '@/api/style'

export const useStyleStore = defineStore('style', {
  state: () => ({
    templates: [],
    // 選択肢はバックエンドの design_tokens.py が唯一の正。起動時に取得して保持する。
    options: null,
    videoStyle: null,
    loading: false,
    error: null,
  }),
  actions: {
    async fetchOptions() {
      if (this.options) return this.options
      const { data } = await styleApi.listOptions()
      this.options = data
      return data
    },
    async applyTemplate(videoId, templateId) {
      const { data } = await styleApi.applyTemplate(videoId, templateId)
      this.videoStyle = data
      return data
    },
    async fetchTemplates() {
      this.loading = true
      this.error = null
      try {
        const { data } = await styleApi.listTemplates()
        this.templates = data
      } catch (e) {
        this.error = e.message
        throw e
      } finally {
        this.loading = false
      }
    },
    async fetchVideoStyle(videoId) {
      this.loading = true
      this.error = null
      try {
        const { data } = await styleApi.getVideoStyle(videoId)
        this.videoStyle = data
        return data
      } catch (e) {
        this.error = e.message
        throw e
      } finally {
        this.loading = false
      }
    },
    async updateVideoStyle(videoId, payload) {
      this.loading = true
      this.error = null
      try {
        const { data } = await styleApi.updateVideoStyle(videoId, payload)
        this.videoStyle = data
        return data
      } catch (e) {
        this.error = e.message
        throw e
      } finally {
        this.loading = false
      }
    },
    async applyPrompt(videoId, prompt) {
      this.loading = true
      this.error = null
      try {
        const { data } = await styleApi.applyPrompt(videoId, prompt)
        this.videoStyle = data
        return data
      } catch (e) {
        this.error = e.message
        throw e
      } finally {
        this.loading = false
      }
    },
  }
})
