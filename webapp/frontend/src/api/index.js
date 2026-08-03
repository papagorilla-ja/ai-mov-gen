/**
 * axios ベース API クライアント
 *
 * ベースURL: /api/v1  (Nginx が http://api:8000 にプロキシ)
 * 全エンドポイントのモジュールをここから re-export する
 */
import axios from 'axios'

export const DEFAULT_TIMEOUT = 30_000
export const LONG_TIMEOUT = 300_000

export const api = axios.create({
  baseURL: '/api/v1',
  headers: { 'Content-Type': 'application/json' },
  timeout: DEFAULT_TIMEOUT,
})

// LLM / TTS など長時間処理用（サーバ側 300s・nginx 300s に整合）
export const longApi = axios.create({
  baseURL: '/api/v1',
  headers: { 'Content-Type': 'application/json' },
  timeout: LONG_TIMEOUT,
})

/**
 * FastAPI のエラー detail を人が読める1行の文字列に変換する。
 *
 * detail は形が3通りある:
 *   - 文字列                     … HTTPException(detail="...")
 *   - オブジェクトの配列          … 422 バリデーションエラー [{loc, msg, type}, ...]
 *   - その他のオブジェクト
 * 配列やオブジェクトをそのまま new Error() に渡すと "[object Object]" になり
 * 原因が分からなくなるため、ここで整形する。
 */
const formatDetail = (detail, fallback) => {
  if (typeof detail === 'string' && detail) return detail
  if (Array.isArray(detail)) {
    const parts = detail.map((d) => {
      if (typeof d === 'string') return d
      // loc の先頭は body/query などの位置種別なので落として項目名だけ見せる
      const field = Array.isArray(d?.loc) ? d.loc.slice(1).join('.') : ''
      const msg = d?.msg || JSON.stringify(d)
      return field ? `${field}: ${msg}` : msg
    })
    return parts.join(' / ')
  }
  if (detail && typeof detail === 'object') {
    return detail.msg || JSON.stringify(detail)
  }
  return fallback || '不明なエラー'
}

const errorHandler = async (err) => {
  if (err.response?.data instanceof Blob) {
    try {
      const text = await err.response.data.text()
      const json = JSON.parse(text)
      return Promise.reject(new Error(formatDetail(json.detail, text)))
    } catch {
      return Promise.reject(new Error(err.message ?? '不明なエラー'))
    }
  }
  return Promise.reject(new Error(formatDetail(err.response?.data?.detail, err.message)))
}

api.interceptors.response.use((res) => res, errorHandler)
longApi.interceptors.response.use((res) => res, errorHandler)
