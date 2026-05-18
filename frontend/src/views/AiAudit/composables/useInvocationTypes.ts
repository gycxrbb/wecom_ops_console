export interface InvocationListItem {
  call_id: string
  session_id: string | null
  crm_customer_id: number | null
  crm_customer_name: string
  local_user_id: number | null
  local_user_name: string
  execution_mode: string
  scene_key: string | null
  status: string
  error_stage: string | null
  error_code: string | null
  error_message: string | null
  primary_model: string | null
  total_tokens: number
  latency_ms: number
  step_count: number
  user_message_preview: string | null
  started_at: string | null
  finished_at: string | null
}

export interface InvocationStepItem {
  step_index: number
  parent_step_index: number | null
  kind: string
  name: string | null
  status: string
  error_code: string | null
  error_message: string | null
  latency_ms: number
  model: string | null
  prompt_tokens: number
  completion_tokens: number
  cached_tokens: number
  tool_name: string | null
  started_at: string | null
  finished_at: string | null
}

export interface InvocationDetail extends InvocationListItem {
  user_message_id: string | null
  assistant_message_id: string | null
  crm_admin_id: number | null
  crm_customer_name: string
  local_user_name: string
  prompt_version: string | null
  error_detail: string | null
  rag_status: string | null
  rag_hit_count: number
  primary_provider: string | null
  first_token_ms: number
  prepare_ms: number
  steps: InvocationStepItem[]
  user_message: {
    message_id: string
    content: string | null
    request_params: any
    created_at: string | null
  } | null
  assistant_message: {
    message_id: string
    content: string | null
    model: string | null
    token_usage: { prompt_tokens: number; completion_tokens: number } | null
    safety_result: any
    requires_medical_review: boolean
    created_at: string | null
  } | null
  rag_logs: {
    query_text: string | null
    hit_json: any
    latency_ms: number
    created_at: string | null
  }[]
}

export interface InvocationStats {
  total: number
  success_count: number
  error_count: number
  error_rate: number
  avg_latency_ms: number
  total_tokens: number
  errors_by_code: { code: string; count: number }[]
}

export interface TrendItem {
  date: string
  total: number
  success_count: number
  error_count: number
  avg_latency_ms: number
  total_tokens: number
}

export interface BreakdownItem {
  key: string
  total: number
  success_count: number
  error_count: number
  avg_latency_ms: number
  total_tokens: number
}

export const STATUS_LABEL: Record<string, string> = {
  pending: '进行中',
  success: '成功',
  partial: '部分成功',
  error: '失败',
  blocked: '被拦截',
}

export const STATUS_TAG_TYPE: Record<string, string> = {
  pending: 'warning',
  success: 'success',
  partial: 'warning',
  error: 'danger',
  blocked: 'info',
}

export const ERROR_CODE_LABEL: Record<string, string> = {
  model_timeout: '模型超时',
  model_connection_failed: '连接失败',
  model_upstream_error: '上游错误',
  model_not_configured: '未配置',
  model_response_invalid: '响应异常',
  prepare_profile_cache_unready: '档案未就绪',
  prepare_profile_load_failed: '档案加载失败',
  prepare_prompt_assembly_failed: 'Prompt 组装失败',
  prepare_attachment_resolution_failed: '附件解析失败',
  rag_retrieval_failed: 'RAG 检索失败',
  rag_retrieval_timeout: 'RAG 超时',
  stream_cancelled: '请求取消',
  stream_interrupted: '流中断',
  safety_gate_blocked: '安全拦截',
  auth_permission_denied: '权限不足',
  system_unknown: '未知错误',
  system_db_write_failed: '写入失败',
}

export const SCENE_LABEL: Record<string, string> = {
  qa_support: '问答支持',
  health_analysis: '健康分析',
  daily_checkin: '打卡解读',
  plan_review: '方案复盘',
}

export function formatTime(t: string | null): string {
  if (!t) return '-'
  return t.replace('T', ' ').substring(0, 19)
}
