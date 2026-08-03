import { api, longApi } from './index'

export const styleApi = {
  // 背景モチーフ・装飾スタイル・組版・切替・フォントの選択肢。
  // 画面側に選択肢を直書きすると必ずバックエンドと食い違うため、必ずここから取得する。
  listOptions: () =>
    api.get('/style-options'),

  listTemplates: () =>
    api.get('/style-templates'),

  getVideoStyle: (videoId) =>
    api.get(`/videos/${videoId}/style`),

  updateVideoStyle: (videoId, payload) =>
    api.patch(`/videos/${videoId}/style`, payload),

  // テンプレートの適用はサーバー側で丸ごと写す（項目のコピー漏れを防ぐため）
  applyTemplate: (videoId, templateId) =>
    api.post(`/videos/${videoId}/style/apply-template/${templateId}`),

  applyPrompt: (videoId, prompt) =>
    longApi.post(`/videos/${videoId}/style/apply-prompt`, { prompt }),

  // --- BGM ---
  uploadBgm: (videoId, file) => {
    const fd = new FormData()
    fd.append('file', file)
    return longApi.post(`/videos/${videoId}/bgm`, fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },

  deleteBgm: (videoId) =>
    api.delete(`/videos/${videoId}/bgm`),
}
