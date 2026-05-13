import { computed, ref } from 'vue'
import request from '#/utils/request'
import { ElMessage } from 'element-plus'
import { streamSse, createSessionId, normalizeHealthWindowDays } from './sseStream'

// Re-export types for backward compatibility
export type {
  RagSource, AiAttachment, RagRecommendedAsset, AiChatMessage,
  SceneOption, ProfileNote, AiSessionSummary, AiSessionMessage,
} from './aiCoachTypes'
import type {
  AiChatMessage, AiAttachment, SceneOption, ProfileNote,
  AiSessionSummary, AiSessionMessage,
} from './aiCoachTypes'

export function useAiCoach() {
  const loading = ref(false)
  const chatHistory = ref<AiChatMessage[]>([])
  const error = ref('')
  const lastTokenUsage = ref<{ total_tokens: number } | null>(null)
  const sessionId = ref<string | null>(null)

  const scenes = ref<SceneOption[]>([])
  const styles = ref<SceneOption[]>([])
  const expansionOptions = ref<Record<string, string>>({})
  const selectedExpansions = ref<string[]>([])
  const currentScene = ref('qa_support')
  const outputStyle = ref('coach_brief')
  const availableModels = ref<string[]>([])
  const selectedModel = ref('')
  const profileNote = ref<ProfileNote | null>(null)
  const sessionHistory = ref<AiSessionSummary[]>([])
  const sessionHistoryLoading = ref(false)
  const profileNoteSaving = ref(false)
  const configLoaded = ref(false)
  const answerAbortController = ref<AbortController | null>(null)
  const thinkingAbortController = ref<AbortController | null>(null)
  const restoredSessionMeta = ref<{ sceneKey: string; outputStyle: string; promptVersion: string } | null>(null)
  const quotedMessage = ref<Extract<AiChatMessage, { role: 'assistant' }> | null>(null)

  const tokenDisplay = computed(() => {
    if (!lastTokenUsage.value) return ''
    return `最近一次消耗 ${lastTokenUsage.value.total_tokens} tokens`
  })

  const setQuote = (msg: Extract<AiChatMessage, { role: 'assistant' }>) => {
    quotedMessage.value = msg
  }
  const clearQuote = () => {
    quotedMessage.value = null
  }

  // --- Config & Profile Notes ---

  const loadAiConfig = async (customerId: number) => {
    try {
      const res: any = await request.get(`/v1/crm-customers/${customerId}/ai/config`)
      scenes.value = res.scenes || []
      styles.value = res.styles || []
      if (styles.value.length) {
        if (!styles.value.some(s => s.key === outputStyle.value)) {
          outputStyle.value = styles.value[0].key
        }
      } else {
        outputStyle.value = ''
      }
      expansionOptions.value = res.expansion_options || {}
      // Default: select all expansion options so AI sees full detail
      if (!selectedExpansions.value.length && Object.keys(expansionOptions.value).length) {
        selectedExpansions.value = Object.keys(expansionOptions.value)
      }
      availableModels.value = res.available_models?.length
        ? res.available_models
        : ['deepseek-v4-pro','gpt-5.5','gpt-5.4','gpt-4o-mini','deepseek-v4-flash','deepseek-v3.2-fast','claude-opus-4-7','kimi-k2.6','glm-5.1','gemini-3.1-pro-preview','xiaomi-mimo-v2.5','doubao-seed-2-0-pro']
      if (!availableModels.value.includes(selectedModel.value)) {
        selectedModel.value = availableModels.value[0]
      }
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

  // --- Session History ---

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
        requestParams: (item as any).request_params || undefined,
        thinkingVisible: false,
        thinkingDone: true,
        streaming: false,
        feedback: item.feedback ? { rating: item.feedback.rating as 'like' | 'dislike', feedbackId: item.feedback.feedback_id } : null,
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

  // --- Core Chat ---

  const sendChat = async (
    customerId: number,
    message: string,
    options?: {
      entryScene?: string
      selectedExpansions?: string[]
      healthWindowDays?: number
      attachmentIds?: string[]
      attachments?: AiAttachment[]
    },
  ) => {
    loading.value = true
    error.value = ''
    const messageText = message.trim()
    const _reqParams = {
      healthWindowDays: options?.healthWindowDays ?? 7,
      attachmentIds: options?.attachmentIds,
      quotedMessageId: quotedMessage.value?.messageId,
      selectedExpansions: selectedExpansions.value,
      model: selectedModel.value || undefined,
    }
    chatHistory.value.push({
      role: 'user', messageType: 'user', content: messageText,
      attachments: options?.attachments,
      requestParams: _reqParams,
    })

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
      attachment_ids: options?.attachmentIds?.length ? options.attachmentIds : undefined,
      quoted_message_id: quotedMessage.value?.messageId || undefined,
      model: selectedModel.value || undefined,
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

        if (event === 'analyzing') {
          assistantMessage.loadingStage = 'prepare'
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
          const err = new Error(payload?.message || payload?.delta || 'AI 服务异常')
          ;(err as any).code = payload?.code || 'unknown'
          throw err
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
      clearQuote()
      await loadSessionHistory(customerId, { silent: true })
      return {
        session_id: sessionId.value,
        message_id: assistantMessage.messageId,
      }
    } catch (e: any) {
      const msg = e?.message || 'AI 服务异常'
      const code = e?.code || 'unknown'
      answerAbortController.value?.abort()
      thinkingAbortController.value?.abort()
      error.value = msg
      assistantMessage.streaming = false
      assistantMessage.thinkingVisible = false
      assistantMessage.errorCode = code
      assistantMessage.errorMessage = msg
      if (!assistantMessage.content) {
        assistantMessage.content = ''
      }
      return null
    } finally {
      loading.value = false
      answerAbortController.value = null
      thinkingAbortController.value = null
    }
  }

  // --- Medical Review & Feedback ---

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

  const submitFeedback = async (
    customerId: number,
    messageId: string,
    body: { rating: 'like' | 'dislike'; reason_category?: string; reason_text?: string; expected_answer?: string },
  ) => {
    const res: any = await request.post(
      `/v1/crm-customers/${customerId}/ai/messages/${messageId}/feedback`,
      body,
    )
    // Update local chatHistory
    const msg = chatHistory.value.find(m => 'messageId' in m && m.messageId === messageId)
    if (msg && 'feedback' in msg) {
      msg.feedback = { rating: body.rating, feedbackId: res.feedback_id }
    }
    return res
  }

  const getMessageFeedback = async (customerId: number, messageId: string) => {
    const res: any = await request.get(
      `/v1/crm-customers/${customerId}/ai/messages/${messageId}/feedback`,
    )
    return res.feedback as { rating: string; feedback_id: string } | null
  }

  // --- Session Management ---

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
    outputStyle.value = 'coach_brief'
    clearQuote()
  }

  const retryLast = async (customerId: number) => {
    // Find the last user message and remove the failed assistant message(s) after it
    let lastUserIdx = -1
    for (let i = chatHistory.value.length - 1; i >= 0; i--) {
      if (chatHistory.value[i].role === 'user') {
        lastUserIdx = i
        break
      }
    }
    if (lastUserIdx < 0) return null
    const userMsg = chatHistory.value[lastUserIdx] as Extract<AiChatMessage, { role: 'user' }>
    const rp = userMsg.requestParams
    // Remove everything after the user message (failed assistant + references)
    chatHistory.value.splice(lastUserIdx)
    error.value = ''
    return sendChat(customerId, userMsg.content, {
      healthWindowDays: rp?.healthWindowDays,
      attachmentIds: rp?.attachmentIds,
      attachments: rp?.attachmentIds ? undefined : undefined,
    })
  }

  // --- Regenerate ---

  const regenerate = async (customerId: number, messageId: string) => {
    if (loading.value) return null
    loading.value = true
    error.value = ''

    const assistantIdx = chatHistory.value.length
    chatHistory.value.push({
      role: 'assistant', messageType: 'assistant_answer',
      content: '',
      safetyNotes: [],
      thinkingContent: '',
      thinkingVisible: false,
      thinkingDone: false,
      streaming: true,
    })
    type AssistantMsg = Extract<AiChatMessage, { role: 'assistant' }>
    const assistantMessage = chatHistory.value[assistantIdx] as AssistantMsg

    const controller = new AbortController()
    answerAbortController.value = controller

    try {
      await streamSse(
        `/v1/crm-customers/${customerId}/ai/messages/${messageId}/regenerate`,
        {},
        controller.signal,
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
          if (event === 'delta' && payload.delta) {
            assistantMessage.content += payload.delta
            return
          }
          if (event === 'done') {
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
            return
          }
          if (event === 'error') {
            const err = new Error(payload?.message || '重新生成失败')
            ;(err as any).code = payload?.code || 'unknown'
            throw err
          }
        },
      )
      await loadSessionHistory(customerId, { silent: true })
      return { session_id: sessionId.value, message_id: assistantMessage.messageId }
    } catch (e: any) {
      const msg = e?.message || '重新生成失败'
      assistantMessage.streaming = false
      assistantMessage.thinkingVisible = false
      assistantMessage.errorCode = e?.code || 'unknown'
      assistantMessage.errorMessage = msg
      if (!assistantMessage.content) {
        assistantMessage.content = ''
      }
      error.value = msg
      return null
    } finally {
      loading.value = false
      answerAbortController.value = null
    }
  }

  // --- Upload ---

  const uploadAttachment = async (customerId: number, file: File, onProgress?: (pct: number) => void): Promise<AiAttachment> => {
    const formData = new FormData()
    formData.append('file', file)
    const res: any = await request.post(
      `/v1/crm-customers/${customerId}/ai/upload-attachment`,
      formData,
      {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 120_000,
        onUploadProgress: (e: any) => {
          if (e.total && onProgress) onProgress(Math.round(e.loaded / e.total * 100))
        },
      },
    )
    return res
  }

  const uploadAttachmentDirect = async (
    customerId: number,
    file: File,
    onProgress?: (pct: number) => void,
    contentHash?: string,
  ): Promise<AiAttachment> => {
    // 1. Get upload credentials from backend
    const cred: any = await request.post(
      `/v1/crm-customers/${customerId}/ai/prepare-upload`,
      { filename: file.name, mime_type: file.type, file_size: file.size, content_hash: contentHash || undefined },
    )

    if (cred.mode === 'existing' && cred.attachment) {
      return cred.attachment
    }

    if (cred.mode === 'qiniu' && cred.upload_url && cred.token) {
      // 2. Direct upload to Qiniu
      const form = new FormData()
      form.append('token', cred.token)
      form.append('key', cred.object_key)
      form.append('file', file)

      const resp = await fetch(cred.upload_url, {
        method: 'POST',
        body: form,
        signal: AbortSignal.timeout(120_000),
      })
      if (!resp.ok) throw new Error('直传云存储失败')

      // 3. Confirm upload with backend
      const att: any = await request.post(
        `/v1/crm-customers/${customerId}/ai/confirm-upload`,
        {
          object_key: cred.object_key,
          public_url: cred.public_url,
          filename: file.name,
          mime_type: file.type,
          file_size: file.size,
          content_hash: contentHash || undefined,
        },
      )
      return att
    }

    // Fallback: server relay
    return uploadAttachment(customerId, file, onProgress)
  }

  return {
    loading, chatHistory, error, tokenDisplay, sessionId, sendChat, clearSession, retryLast,
    markMedicalReview, uploadAttachment, uploadAttachmentDirect,
    submitFeedback, getMessageFeedback,
    regenerate, quotedMessage, setQuote, clearQuote,
    scenes, styles, currentScene, outputStyle, profileNote, profileNoteSaving, configLoaded,
    sessionHistory, sessionHistoryLoading, loadSessionHistory, openHistorySession,
    loadAiConfig, saveProfileNote, restoredSessionMeta,
    expansionOptions, selectedExpansions,
    availableModels, selectedModel,
  }
}
