import { computed, ref } from 'vue'
import request from '#/utils/request'
import { ElMessage } from 'element-plus'

export type RagSource = {
  resource_id: number
  source_type: string
  title: string
  snippet: string
  score: number
  content_kind: string
  safety_level: string
}

export type RagRecommendedAsset = {
  material_id: number
  title: string
  material_type: string
  preview_url: string | null
  download_url: string | null
  public_url: string | null
  reason: string
}

export type AiChatMessage =
  | { role: 'user'; messageType: 'user'; content: string }
  | {
      role: 'assistant'; messageType: 'assistant_answer'; content: string
      messageId?: string
      safetyNotes?: string[]
      safetyResult?: { level: string; reason_codes: string[]; notes: string[] }
      requiresMedicalReview?: boolean
      tokenUsage?: { prompt_tokens: number; completion_tokens: number; total_tokens: number }
      thinkingContent?: string
      loadingStage?: 'prepare' | 'model_call'
      thinkingVisible?: boolean
      thinkingDone?: boolean
      streaming?: boolean
    }
  | {
      role: 'reference'; messageType: 'rag_reference'
      resource_id: number; title: string; snippet: string
      score: number; source_type: string; content_kind: string
    }
  | {
      role: 'reference'; messageType: 'rag_attachment'
      title: string; asset: RagRecommendedAsset
    }

export type SceneOption = { key: string; label: string }

export type ProfileNote = {
  crm_customer_id: number
  status?: string
  communication_style_note?: string | null
  current_focus_note?: string | null
  execution_barrier_note?: string | null
  lifestyle_background_note?: string | null
  coach_strategy_note?: string | null
  preferred_scene_hint?: string | null
  updated_at?: string | null
}

export type AiSessionSummary = {
  session_id: string
  entry_scene?: string | null
  scene_key?: string | null
  started_at?: string | null
  last_message_at?: string | null
  message_count: number
  last_message_preview: string
}

export type AiSessionMessage = {
  message_id: string
  role: 'user' | 'assistant'
  content: string
  created_at?: string | null
  requires_medical_review?: boolean
  token_usage?: { prompt_tokens: number; completion_tokens: number; total_tokens: number }
}

type StreamPayload = {
  session_id?: string
  message_id?: string
  delta?: string
  message?: string
  stage?: string
  token_usage?: { prompt_tokens: number; completion_tokens: number; total_tokens: number }
  requires_medical_review?: boolean
  safety_notes?: string[]
  missing_data_notes?: string[]
  safety_result?: { level: string; reason_codes: string[]; notes: string[] }
  sources?: RagSource[]
  recommended_assets?: RagRecommendedAsset[]
  rag_status?: string
}

function buildAuthHeaders() {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  }
  const token = localStorage.getItem('access_token')
  if (token) {
    headers.Authorization = `Bearer ${token}`
  }
  return headers
}

async function streamSse(
  url: string,
  body: Record<string, any>,
  signal: AbortSignal,
  onEvent: (event: string, payload: StreamPayload) => void,
) {
  let response: Response
  try {
    response = await fetch(`/api${url}`, {
      method: 'POST',
      headers: buildAuthHeaders(),
      credentials: 'include',
      body: JSON.stringify(body),
      signal,
    })
  } catch (e: any) {
    if (e?.name === 'AbortError') return
    throw e
  }

  if (!response.ok) {
    const text = await response.text()
    throw new Error(text || `请求失败 (${response.status})`)
  }
  if (!response.body) {
    throw new Error('流式响应不可用')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''

  try {
    while (true) {
      const { value, done } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, '\n')

      const chunks = buffer.split('\n\n')
      buffer = chunks.pop() || ''

      for (const chunk of chunks) {
        let event = 'message'
        const dataLines: string[] = []

        for (const line of chunk.split('\n')) {
          const trimmed = line.trim()
          if (!trimmed) continue
          if (trimmed.startsWith(':')) continue
          if (trimmed.startsWith('event:')) {
            event = trimmed.slice(6).trim()
          } else if (trimmed.startsWith('data:')) {
            dataLines.push(trimmed.slice(5).trim())
          }
        }

        if (!dataLines.length) continue
        const payload = JSON.parse(dataLines.join('\n'))
        onEvent(event, payload)
      }
    }
  } catch (e: any) {
    if (e?.name === 'AbortError') return
    throw e
  }

  if (buffer.trim()) {
    let event = 'message'
    const dataLines: string[] = []
    for (const line of buffer.split('\n')) {
      const trimmed = line.trim()
      if (!trimmed) continue
      if (trimmed.startsWith(':')) continue
      if (trimmed.startsWith('event:')) {
        event = trimmed.slice(6).trim()
      } else if (trimmed.startsWith('data:')) {
        dataLines.push(trimmed.slice(5).trim())
      }
    }
    if (dataLines.length) {
      const payload = JSON.parse(dataLines.join('\n'))
      onEvent(event, payload)
    }
  }
}

function createSessionId() {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  return `crm-ai-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

const normalizeHealthWindowDays = (value: unknown) => {
  const parsed = Number(value)
  return [7, 14, 30].includes(parsed) ? parsed : 7
}

export function useAiCoach() {
  const loading = ref(false)
  const chatHistory = ref<AiChatMessage[]>([])
  const error = ref('')
  const lastTokenUsage = ref<{ total_tokens: number } | null>(null)
  const sessionId = ref<string | null>(null)

  const scenes = ref<SceneOption[]>([])
  const expansionOptions = ref<Record<string, string>>({})
  const selectedExpansions = ref<string[]>([])
  const currentScene = ref('qa_support')
  const outputStyle = ref('coach_brief')
  const profileNote = ref<ProfileNote | null>(null)
  const sessionHistory = ref<AiSessionSummary[]>([])
  const sessionHistoryLoading = ref(false)
  const profileNoteSaving = ref(false)
  const configLoaded = ref(false)
  const answerAbortController = ref<AbortController | null>(null)
  const thinkingAbortController = ref<AbortController | null>(null)
  const restoredSessionMeta = ref<{ sceneKey: string; outputStyle: string; promptVersion: string } | null>(null)

  const tokenDisplay = computed(() => {
    if (!lastTokenUsage.value) return ''
    return `最近一次消耗 ${lastTokenUsage.value.total_tokens} tokens`
  })

  const loadAiConfig = async (customerId: number) => {
    try {
      const res: any = await request.get(`/v1/crm-customers/${customerId}/ai/config`)
      scenes.value = res.scenes || []
      expansionOptions.value = res.expansion_options || {}
      profileNote.value = res.profile_note || { crm_customer_id: customerId }
      if (res.profile_note?.preferred_scene_hint) {
        currentScene.value = res.profile_note.preferred_scene_hint
      }
      configLoaded.value = true
    } catch (e: any) {
      console.warn('Failed to load AI config', e)
    }
  }

  const saveProfileNote = async (customerId: number, note: Partial<ProfileNote>) => {
    profileNoteSaving.value = true
    try {
      const res: any = await request.put(
        `/v1/crm-customers/${customerId}/ai/profile-note`,
        note,
      )
      profileNote.value = res
      ElMessage.success('客户专属补充信息已保存')
    } catch (e: any) {
      ElMessage.error(e?.response?.data?.detail || '保存失败')
    } finally {
      profileNoteSaving.value = false
    }
  }

  const loadSessionHistory = async (
    customerId: number,
    options?: { limit?: number; silent?: boolean },
  ) => {
    if (!options?.silent) {
      sessionHistoryLoading.value = true
    }
    try {
      const res: any = await request.get(`/v1/crm-customers/${customerId}/ai/sessions`, {
        params: { limit: options?.limit || 20 },
      })
      sessionHistory.value = res.items || []
      return sessionHistory.value
    } catch (e) {
      console.warn('Failed to load AI session history', e)
      return []
    } finally {
      if (!options?.silent) {
        sessionHistoryLoading.value = false
      }
    }
  }

  const openHistorySession = async (customerId: number, targetSessionId: string) => {
    if (loading.value) return false
    sessionHistoryLoading.value = true
    try {
      const res: any = await request.get(`/v1/crm-customers/${customerId}/ai/sessions/${targetSessionId}`)
      answerAbortController.value?.abort()
      thinkingAbortController.value?.abort()
      answerAbortController.value = null
      thinkingAbortController.value = null
      loading.value = false
      error.value = ''
      sessionId.value = res.session?.session_id || targetSessionId
      chatHistory.value = (res.messages || []).map((item: AiSessionMessage) => ({
        role: item.role as 'user' | 'assistant',
        messageType: item.role === 'user' ? 'user' as const : 'assistant_answer' as const,
        content: item.content || '',
        messageId: item.message_id,
        requiresMedicalReview: item.requires_medical_review,
        tokenUsage: item.token_usage,
        thinkingVisible: false,
        thinkingDone: true,
        streaming: false,
      }))

      // Restore session strategy from audit trail
      if (res.scene_key) currentScene.value = res.scene_key
      if (res.output_style) outputStyle.value = res.output_style
      restoredSessionMeta.value = {
        sceneKey: res.scene_key || currentScene.value,
        outputStyle: res.output_style || outputStyle.value,
        promptVersion: res.prompt_version || '',
      }

      type AsstMsg = Extract<AiChatMessage, { role: 'assistant' }>
      const lastAssistant = [...chatHistory.value].reverse().find((msg): msg is AsstMsg => msg.role === 'assistant' && 'tokenUsage' in msg && !!msg.tokenUsage)
      lastTokenUsage.value = lastAssistant?.tokenUsage || null
      return true
    } catch (e) {
      console.warn('Failed to open AI session history', e)
      ElMessage.error('历史对话加载失败')
      return false
    } finally {
      sessionHistoryLoading.value = false
    }
  }

  const sendChat = async (
    customerId: number,
    message: string,
    options?: { entryScene?: string; selectedExpansions?: string[]; healthWindowDays?: number },
  ) => {
    loading.value = true
    error.value = ''
    const messageText = message.trim()
    chatHistory.value.push({ role: 'user', messageType: 'user', content: messageText })

    const nextSessionId = sessionId.value || createSessionId()
    sessionId.value = nextSessionId

    const assistantIdx = chatHistory.value.length
    chatHistory.value.push({
      role: 'assistant', messageType: 'assistant_answer',
      content: '',
      safetyNotes: [],
      thinkingContent: '',
      thinkingVisible: true,
      thinkingDone: false,
      streaming: true,
    })
    // Use reactive reference from the array so mutations trigger Vue reactivity
    type AssistantMsg = Extract<AiChatMessage, { role: 'assistant' }>
    const assistantMessage = chatHistory.value[assistantIdx] as AssistantMsg

    const answerController = new AbortController()
    const thinkingController = new AbortController()
    answerAbortController.value = answerController
    thinkingAbortController.value = thinkingController

    const requestBody = {
      message: messageText,
      session_id: nextSessionId,
      scene_key: currentScene.value,
      output_style: outputStyle.value,
      entry_scene: options?.entryScene || 'customer_profile',
      selected_expansions: selectedExpansions.value.length ? selectedExpansions.value : undefined,
      health_window_days: normalizeHealthWindowDays(options?.healthWindowDays),
    }

    let answerCompleted = false

    const answerPromise = streamSse(
      `/v1/crm-customers/${customerId}/ai/chat-stream`,
      requestBody,
      answerController.signal,
      (event, payload) => {
        if (event === 'meta') {
          if (payload.session_id) sessionId.value = payload.session_id
          if (payload.message_id) assistantMessage.messageId = payload.message_id
          return
        }

        if (event === 'loading') {
          assistantMessage.loadingStage = payload.stage as 'prepare' | 'model_call'
          return
        }

        if (event === 'rag') {
          const ragSources = payload.sources || []
          const ragAssets = payload.recommended_assets || []
          // Insert reference messages before the assistant message in chatHistory
          const refMessages: AiChatMessage[] = []
          for (const src of ragSources) {
            refMessages.push({
              role: 'reference', messageType: 'rag_reference',
              resource_id: src.resource_id, title: src.title,
              snippet: src.snippet || '', score: src.score,
              source_type: src.source_type, content_kind: src.content_kind,
            })
          }
          for (const asset of ragAssets) {
            refMessages.push({
              role: 'reference', messageType: 'rag_attachment',
              title: asset.title, asset,
            })
          }
          if (refMessages.length) {
            // Insert before the current assistant message
            chatHistory.value.splice(assistantIdx, 0, ...refMessages)
            // Adjust assistantIdx since we inserted before it
            // (assistantMessage ref is still valid via Vue reactivity)
          }
          return
        }

        if (event === 'delta' && payload.delta) {
          assistantMessage.content += payload.delta
          return
        }

        if (event === 'done') {
          answerCompleted = true
          assistantMessage.streaming = false
          assistantMessage.loadingStage = undefined
          assistantMessage.tokenUsage = payload.token_usage
          assistantMessage.safetyNotes = payload.safety_notes || []
          assistantMessage.safetyResult = payload.safety_result || undefined
          assistantMessage.requiresMedicalReview = payload.requires_medical_review
          assistantMessage.thinkingVisible = false
          assistantMessage.thinkingDone = true
          if (payload.token_usage) {
            lastTokenUsage.value = payload.token_usage
          }
          setTimeout(() => thinkingAbortController.value?.abort(), 200)
          return
        }

        if (event === 'error') {
          throw new Error(payload?.message || payload?.delta || 'AI 服务异常')
        }
      },
    )

    const thinkingPromise = streamSse(
      `/v1/crm-customers/${customerId}/ai/thinking-stream`,
      requestBody,
      thinkingController.signal,
      (event, payload) => {
        if (!assistantMessage.thinkingVisible) return

        if (event === 'meta') {
          if (payload.session_id && !sessionId.value) {
            sessionId.value = payload.session_id
          }
          return
        }

        if (event === 'loading') {
          assistantMessage.loadingStage = payload.stage as 'prepare' | 'model_call'
          return
        }

        if (event === 'delta' && payload.delta && !answerCompleted) {
          assistantMessage.loadingStage = undefined
          assistantMessage.thinkingContent = (assistantMessage.thinkingContent || '') + payload.delta
          return
        }

        if (event === 'done') {
          assistantMessage.thinkingDone = true
          assistantMessage.loadingStage = undefined
        }
      },
    ).catch((err: any) => {
      if (err?.name !== 'AbortError') {
        console.warn('Thinking stream failed', err)
      }
    })

    try {
      void thinkingPromise
      await answerPromise
      await loadSessionHistory(customerId, { silent: true })
      return {
        session_id: sessionId.value,
        message_id: assistantMessage.messageId,
      }
    } catch (e: any) {
      const msg = e?.message || 'AI 服务异常'
      answerAbortController.value?.abort()
      thinkingAbortController.value?.abort()
      error.value = msg
      assistantMessage.streaming = false
      assistantMessage.thinkingVisible = false
      assistantMessage.content = assistantMessage.content || `[错误] ${msg}`
      return null
    } finally {
      loading.value = false
      answerAbortController.value = null
      thinkingAbortController.value = null
    }
  }

  const markMedicalReview = async (customerId: number, messageId: string) => {
    try {
      await request.patch(`/v1/crm-customers/${customerId}/ai/messages/${messageId}/review`)
      const msg = chatHistory.value.find(m => 'messageId' in m && m.messageId === messageId)
      if (msg && 'requiresMedicalReview' in msg) {
        msg.requiresMedicalReview = true
      }
      return true
    } catch {
      return false
    }
  }

  const clearSession = () => {
    answerAbortController.value?.abort()
    thinkingAbortController.value?.abort()
    answerAbortController.value = null
    thinkingAbortController.value = null
    sessionId.value = null
    chatHistory.value = []
    error.value = ''
    lastTokenUsage.value = null
    loading.value = false
    restoredSessionMeta.value = null
  }

  return {
    loading, chatHistory, error, tokenDisplay, sessionId, sendChat, clearSession,
    markMedicalReview,
    scenes, currentScene, outputStyle, profileNote, profileNoteSaving, configLoaded,
    sessionHistory, sessionHistoryLoading, loadSessionHistory, openHistorySession,
    loadAiConfig, saveProfileNote, restoredSessionMeta,
    expansionOptions, selectedExpansions,
  }
}
