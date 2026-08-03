import { defineStore } from 'pinia'
import { reactive } from 'vue'

/**
 * グローバル UI 状態ストア
 * スナックバー通知など画面横断的な状態を管理する
 */
export const useUiStore = defineStore('ui', () => {
  const snackbar = reactive({
    show: false,
    message: '',
    color: 'success',
    timeout: 3000,
  })

  function notify(message, color = 'success', timeout = 3000) {
    snackbar.message = message
    snackbar.color = color
    snackbar.timeout = timeout
    snackbar.show = true
  }

  function notifyError(message) {
    notify(message, 'error', 5000)
  }

  return { snackbar, notify, notifyError }
})
