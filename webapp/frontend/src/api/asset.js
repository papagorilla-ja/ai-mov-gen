import { api } from './index'

export const assetApi = {
  list: (sceneId) =>
    api.get(`/scenes/${sceneId}/assets`),

  upload: (sceneId, slot, file, assetType = 'image') => {
    const form = new FormData()
    if (file) form.append('file', file)
    form.append('asset_type', assetType)
    return api.post(`/scenes/${sceneId}/assets/${slot}`, form, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
  },

  uploadSvg: (sceneId, slot, svgContent) => {
    const form = new FormData()
    form.append('asset_type', 'svg')
    form.append('svg_content', svgContent)
    return api.post(`/scenes/${sceneId}/assets/${slot}`, form, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
  },

  updateConfig: (sceneId, slot, config) =>
    api.patch(`/scenes/${sceneId}/assets/${slot}`, config),

  delete: (sceneId, slot) =>
    api.delete(`/scenes/${sceneId}/assets/${slot}`),
}
