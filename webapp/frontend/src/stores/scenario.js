import { defineStore } from 'pinia'
import { scenarioApi } from '@/api/scenario'

export const useScenarioStore = defineStore('scenario', {
  state: () => ({
    scenario: null,          // ScenarioRead | null
    chatMessages: [],        // [{ role, content }]
    lastProposal: null,      // ScenarioProposal | null
    loading: false,
    error: null,
  }),
  actions: {
    async fetchScenario(videoId) {
      this.loading = true
      this.error = null
      try {
        const { data } = await scenarioApi.get(videoId)
        this.scenario = data
        if (data && data.chat_messages) {
          this.chatMessages = JSON.parse(data.chat_messages)
          // 履歴の最後の assistant 返答から proposal の抽出を試みて lastProposal に保持する
          const assistantMsgs = this.chatMessages.filter(m => m.role === 'assistant')
          if (assistantMsgs.length > 0) {
            const lastReply = assistantMsgs[assistantMsgs.length - 1].content
            this.extractLastProposal(lastReply)
          }
        } else {
          this.chatMessages = []
          this.lastProposal = null
        }
      } catch (e) {
        this.error = e.response?.data?.detail || e.message
        throw e;
      } finally {
        this.loading = false
      }
    },

    async fromPptx(videoId, file) {
      this.loading = true
      this.error = null
      try {
        // レスポンスは PptxImportResult { scenario, job_id, slide_count, scene_count, visual_count, warnings }
        // ナレーション生成は非同期ジョブなので、シーン構成自体はこの時点で確定している
        const { data } = await scenarioApi.fromPptx(videoId, file)
        this.scenario = data.scenario
        this.chatMessages = []
        this.lastProposal = null
        return data
      } catch (e) {
        this.error = e.response?.data?.detail || e.message
        throw e
      } finally {
        this.loading = false
      }
    },

    async fromText(videoId, text) {
      this.loading = true
      this.error = null
      try {
        const { data } = await scenarioApi.fromText(videoId, text)
        this.scenario = data
        this.chatMessages = []
        this.lastProposal = null
        return data
      } catch (e) {
        this.error = e.response?.data?.detail || e.message
        throw e
      } finally {
        this.loading = false
      }
    },

    async sendChatMessage(videoId, message) {
      this.loading = true
      this.error = null
      try {
        // 先行してローカル状態に user メッセージを積む (対話レスポンスの向上)
        this.chatMessages.push({ role: 'user', content: message })
        
        const { data } = await scenarioApi.chat(videoId, message)
        
        // ローカル状態を同期 (システムメッセージ等も含めて再同期されるようにする)
        if (this.scenario) {
          const messages = JSON.parse(this.scenario.chat_messages || '[]')
        }
        
        // ストアメッセージを更新
        this.chatMessages.push({ role: 'assistant', content: data.reply })
        this.lastProposal = data.proposal // { scenes: [...] } or null
        
        return data
      } catch (e) {
        // エラー時は追加した user メッセージを削除する等のロールバック
        this.chatMessages.pop()
        this.error = e.response?.data?.detail || e.message
        throw e
      } finally {
        this.loading = false
      }
    },

    async finalizeScenario(videoId, scenes) {
      this.loading = true
      this.error = null
      try {
        const { data } = await scenarioApi.finalize(videoId, scenes)
        this.scenario = data
        this.lastProposal = null
        return data
      } catch (e) {
        this.error = e.response?.data?.detail || e.message
        throw e
      } finally {
        this.loading = false
      }
    },

    extractLastProposal(text) {
      try {
        const match = text.match(/```(?:json)?\s*(\{.*?\})\s*```/s)
        let jsonStr = ''
        if (match) {
          jsonStr = match[1]
        } else {
          const matchRaw = text.match(/(\{.*\})/s)
          if (matchRaw) {
            jsonStr = matchRaw[1]
          }
        }
        if (jsonStr) {
          const parsed = JSON.parse(jsonStr)
          if (parsed && parsed.scenes) {
            this.lastProposal = parsed
          }
        }
      } catch (e) {
        this.lastProposal = null
      }
    }
  }
})
