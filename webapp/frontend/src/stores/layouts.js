import { defineStore } from 'pinia'
import { layoutApi } from '@/api/layout'

/**
 * レイアウトカタログのストア。
 *
 * 中身はアプリの実行中に変わらないので一度だけ取得して保持する。
 * サムネイルは重い（1 件 30KB 程度の HTML 文書）ため、開いたものだけ取りに行く。
 */
export const useLayoutsStore = defineStore('layouts', {
  state: () => ({
    types: [],            // [{ id, label, description, fields: [...] }]
    catalog: [],          // [{ type, label, layouts: [...] }]
    breadthLevels: [],    // [{ value, label, description, types: [...] }]
    defaultBreadth: 'standard',
    dedicatedKinds: [],   // 専用エディタが要る kind（tree / table / chart / images）
    samples: {},          // { [layoutId]: HTML 文書 }
    loaded: false,
    loading: false,
    error: null,
  }),

  getters: {
    // レイアウト ID から定義を引く
    byId: (state) => {
      const map = {}
      state.catalog.forEach((group) => {
        group.layouts.forEach((l) => { map[l.id] = { ...l, type: group.type } })
      })
      return map
    },
    // 型 ID から定義（フィールド一覧を含む）を引く
    typeById: (state) => {
      const map = {}
      state.types.forEach((t) => { map[t.id] = t })
      return map
    },
  },

  actions: {
    async fetchCatalog(force = false) {
      if (this.loaded && !force) return
      this.loading = true
      this.error = null
      try {
        const { data } = await layoutApi.catalog()
        this.types = data.types
        this.catalog = data.catalog
        this.breadthLevels = data.breadth_levels
        this.defaultBreadth = data.default_breadth
        this.dedicatedKinds = data.dedicated_kinds
        this.loaded = true
      } catch (e) {
        this.error = e
      } finally {
        this.loading = false
      }
    },

    async fetchSample(layoutId, videoId) {
      const key = `${layoutId}:${videoId || ''}`
      if (this.samples[key]) return this.samples[key]
      const { data } = await layoutApi.sample(layoutId, videoId)
      this.samples[key] = data.document
      return data.document
    },

    // テーマを変えるとサムネイルの見た目も変わるので、保持しているものを捨てる
    clearSamples() {
      this.samples = {}
    },

    /** そのレイアウトが、いまの件数でそのまま使えるか */
    fitsCount(layoutId, count) {
      const l = this.byId[layoutId]
      if (!l) return true
      if (l.any_count) return true
      return count >= l.min && count <= l.max
    },
  },
})
