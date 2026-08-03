import { api, longApi } from './index'  // 既存の axios インスタンス

export const scenarioApi = {
  get: (videoId) =>
    api.get(`/videos/${videoId}/scenario`),

  fromPptx: (videoId, file) => {
    const form = new FormData()
    form.append('file', file)
    return longApi.post(`/videos/${videoId}/scenario/from-pptx`, form, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    })
  },

  getPptxImportStatus: (videoId, jobId) =>
    api.get(`/videos/${videoId}/scenario/from-pptx/status/${jobId}`),

  fromText: (videoId, text) =>
    longApi.post(`/videos/${videoId}/scenario/from-text`, { text }),

  chat: (videoId, message) =>
    longApi.post(`/videos/${videoId}/scenario/chat`, { message }),

  finalize: (videoId, scenes) =>
    api.post(`/videos/${videoId}/scenario/finalize`, { scenes }),

  generateNarration: (sceneId) =>
    longApi.post(`/scenes/${sceneId}/generate-narration`, {}),

  generateSceneContent: (sceneId) =>
    longApi.post(`/scenes/${sceneId}/generate-content`, {}),

  startGenerateAllContent: (videoId, onlyEmpty = true) =>
    longApi.post(`/videos/${videoId}/scenes/generate-content-all/start?only_empty=${onlyEmpty}`, {}),

  getGenerateAllContentStatus: (jobId) =>
    api.get(`/scenes/generate-content-all/status/${jobId}`),

  generateImagePrompt: (sceneId) =>
    longApi.post(`/scenes/${sceneId}/generate-image-prompt`, {}),
}
