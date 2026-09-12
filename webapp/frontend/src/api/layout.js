import { api } from './index'

export const layoutApi = {
  // 型・レイアウト・編集フォームの項目定義をまとめて取得する。
  // 画面側に選択肢やフィールドを直書きすると必ずバックエンドと食い違うため、
  // 必ずここから取得する（style.js の listOptions と同じ方針）。
  catalog: () => api.get('/layouts'),

  // ギャラリーのサムネイル。iframe の srcdoc に入れる完結した HTML 文書が返る。
  sample: (layoutId, videoId) =>
    api.get(`/layouts/${layoutId}/sample`, { params: videoId ? { video_id: videoId } : {} }),

  // レイアウトを変えたときの内容の移し替え。
  // lost_count が 0 より大きければ、その件数ぶん表示されなくなる。
  convert: (fromLayout, toLayout, content) =>
    api.post('/layouts/convert', {
      from_layout: fromLayout,
      to_layout: toLayout,
      content,
    }),
}
