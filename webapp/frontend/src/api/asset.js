import { api } from './index'

export const assetApi = {
  list: (sceneId) =>
    api.get(`/scenes/${sceneId}/assets`),

  /**
   * 素材をスロットへアップロードする。
   *
   * filename を渡せるようにしているのは、クリップボードから貼り付けた画像のため。
   * ブラウザが渡してくる File は名前が空のことがあり、サーバー側は
   * 拡張子で形式を判定しているため、そのままだと 400 で弾かれる。
   */
  upload: (sceneId, slot, file, assetType = 'image', filename = null) => {
    const form = new FormData()
    if (file) form.append('file', file, filename || file.name || 'upload')
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
