import { ref } from 'vue'
import request from '#/utils/request'

export interface ResolveResult {
  ok: boolean
  platform: string
  doc_type: string
  source_doc_token: string
  canonical_url: string
  open_url: string
  title_hint: string
  needs_manual_title: boolean
  warnings: string[]
}

export interface TermItem {
  id: number
  dimension: string
  code: string
  label: string
  scope_type: string
  sort_order: number
  is_active: boolean
}

export interface WorkspaceItem {
  id: number
  name: string
  workspace_type: string
}

export interface QuickAddFormData {
  url: string
  title: string
  workspace_id: number | null
  primary_stage_term_id: number | null
  deliverable_term_id: number | null
  relation_role: string
  summary: string
  remark: string
  open_after_save: boolean
}

export function useQuickAdd() {
  const resolving = ref(false)
  const resolved = ref<ResolveResult | null>(null)
  const saving = ref(false)
  const workspaces = ref<WorkspaceItem[]>([])
  const stageTerms = ref<TermItem[]>([])
  const deliverableTerms = ref<TermItem[]>([])

  const resolveLink = async (url: string) => {
    if (!url.trim()) return
    resolving.value = true
    try {
      resolved.value = await request.post('/v1/external-docs/resources/resolve-link', { url })
    } catch (e) {
      console.error(e)
    } finally {
      resolving.value = false
    }
  }

  const save = async (formData: QuickAddFormData) => {
    saving.value = true
    try {
      const res = await request.post('/v1/external-docs/quick-add', {
        resource: {
          title: formData.title,
          canonical_url: resolved.value?.canonical_url || formData.url,
          open_url: resolved.value?.open_url || formData.url,
          source_platform: resolved.value?.platform || 'unknown',
          source_doc_token: resolved.value?.source_doc_token || null,
          doc_type: resolved.value?.doc_type || 'unknown',
          summary: formData.summary,
        },
        binding: {
          workspace_id: formData.workspace_id,
          primary_stage_term_id: formData.primary_stage_term_id,
          deliverable_term_id: formData.deliverable_term_id,
          relation_role: formData.relation_role,
          is_primary: formData.relation_role === 'official',
          remark: formData.remark,
        },
        open_after_save: formData.open_after_save,
      })
      return res
    } finally {
      saving.value = false
    }
  }

  const fetchOptions = async () => {
    try {
      const [ws, terms] = await Promise.all([
        request.get('/v1/external-docs/workspaces'),
        request.get('/v1/external-docs/terms'),
      ])
      workspaces.value = (ws || []) as WorkspaceItem[]
      const allTerms = (terms || []) as TermItem[]
      stageTerms.value = allTerms.filter(t => t.dimension === 'stage')
      deliverableTerms.value = allTerms.filter(t => t.dimension === 'deliverable_type')
    } catch (e) {
      console.error(e)
    }
  }

  const reset = () => {
    resolved.value = null
  }

  return {
    resolving, resolved, saving,
    workspaces, stageTerms, deliverableTerms,
    resolveLink, save, fetchOptions, reset,
  }
}
