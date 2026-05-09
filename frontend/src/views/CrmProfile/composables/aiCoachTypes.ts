/** Type definitions for AI coach feature. */

export type RagSource = {
  resource_id: number
  source_type: string
  title: string
  snippet: string
  score: number
  content_kind: string
  safety_level: string
}

export type AiAttachment = {
  attachment_id: string
  filename: string
  mime_type: string
  file_size: number
  content_hash?: string | null
  url?: string
  deduped?: boolean
  uploading?: boolean
  progress?: number  // 0-100
}

export type RagRecommendedAsset = {
  material_id: number
  title: string
  material_type: string
  source_filename: string
  preview_url: string | null
  download_url: string | null
  public_url: string | null
  reason: string
  visibility: string
  safety_level: string
  customer_sendable: boolean
  resource_id: number
}

export type AiChatMessage =
  | { role: 'user'; messageType: 'user'; content: string; attachments?: AiAttachment[]; requestParams?: Record<string, any> }
  | {
      role: 'assistant'; messageType: 'assistant_answer'; content: string
      messageId?: string
      safetyNotes?: string[]
      safetyResult?: { level: string; reason_codes: string[]; notes: string[] }
      requiresMedicalReview?: boolean
      tokenUsage?: { prompt_tokens: number; completion_tokens: number; total_tokens: number; cached_tokens?: number }
      thinkingContent?: string
      loadingStage?: 'prepare' | 'model_call'
      thinkingVisible?: boolean
      thinkingDone?: boolean
      streaming?: boolean
      errorCode?: string
      errorMessage?: string
      feedback?: { rating: 'like' | 'dislike'; feedbackId: string } | null
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
  token_usage?: { prompt_tokens: number; completion_tokens: number; total_tokens: number; cached_tokens?: number }
  feedback?: { rating: string; feedback_id: string } | null
}

export type StreamPayload = {
  session_id?: string
  message_id?: string
  delta?: string
  message?: string
  code?: string
  stage?: string
  status?: string
  token_usage?: { prompt_tokens: number; completion_tokens: number; total_tokens: number; cached_tokens?: number }
  requires_medical_review?: boolean
  safety_notes?: string[]
  missing_data_notes?: string[]
  safety_result?: { level: string; reason_codes: string[]; notes: string[] }
  sources?: RagSource[]
  recommended_assets?: RagRecommendedAsset[]
  rag_status?: string
}
