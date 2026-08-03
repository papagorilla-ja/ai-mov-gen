import { api, longApi } from './index'

export const speakerApi = {
  list: () => api.get('/speakers'),

  get: (id) => api.get(`/speakers/${id}`),

  create: (payload) => api.post('/speakers', payload),

  update: (id, payload) => api.patch(`/speakers/${id}`, payload),

  delete: (id) => api.delete(`/speakers/${id}`),

  uploadReference: (speakerId, file) => {
    const form = new FormData()
    form.append('speaker_id', speakerId)
    form.append('file', file)
    // multipart を明示しないと、axios の既定 Content-Type(application/json) により
    // FormData が JSON へ変換されてしまい、サーバ側で 422 になる
    return api.post('/speakers/upload-reference', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },

  // ─── 音声収集セッション ───
  // 固定コーパスから出題するため待ち時間は発生しない（通常の api で十分）
  sessionModes: () => api.get('/speakers/collection-session/modes'),

  sessionStart: (mode = 'script', itemCount = 5) =>
    api.post('/speakers/collection-session/start', { mode, item_count: itemCount }),

  sessionRecord: (sessionId, sentenceIndex, audioBlob, fileName = 'take') => {
    const form = new FormData()
    form.append('sentence_index', sentenceIndex)
    // 実際の形式はブラウザ依存（Chrome:webm / Safari:mp4）。拡張子は使わずサーバ側で判定させる
    form.append('file', audioBlob, fileName)
    // multipart を明示（既定の application/json のままだと FormData が JSON 化され 422 になる）
    return longApi.post(`/speakers/collection-session/${sessionId}/record`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },

  // 収録完了 → 収録音声ライブラリへ名前付きで保存（話者はここでは作らない）
  sessionFinalize: (sessionId, payload) =>
    longApi.post(`/speakers/collection-session/${sessionId}/finalize`, payload),

  // ─── 収録音声ライブラリ ───
  listRecordings: () => api.get('/speakers/recordings'),

  renameRecording: (recordingId, name) =>
    api.patch(`/speakers/recordings/${recordingId}`, { name }),

  deleteRecording: (recordingId) =>
    api.delete(`/speakers/recordings/${recordingId}`),

  // 収録音声を話者の参照音声として採用する
  useRecording: (speakerId, recordingId) =>
    api.post('/speakers/use-recording', { speaker_id: speakerId, recording_id: recordingId }),
}
