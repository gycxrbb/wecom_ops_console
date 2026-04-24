import { ref, onMounted } from 'vue'
import request from '@/utils/request'

export interface WorkspaceItem {
  id: number
  name: string
  workspace_type: string
  status: string
  owner_user_id: number | null
  owner_name: string
  created_by: number | null
  current_stage_term_id: number | null
  current_stage_label: string
  doc_count: number
  description: string
  created_at: string | null
  updated_at: string | null
}

export interface ResourceItem {
  id: number
  title: string
  doc_type: string
  status: string
  verification_status: string
  open_url: string
  summary: string
  owner_user_id: number | null
  updated_at: string | null
  last_opened_at: string | null
  workspace_name: string
  workspace_id: number | null
  stage_label: string
  relation_role: string
}

export interface CurrentStageDoc {
  resource_id: number
  title: string
  doc_type: string
  open_url: string
  workspace_id: number
  workspace_name: string
  stage_label: string
  relation_role: string
}

export interface GovernanceSummary {
  needs_sorting: any[]
  needs_verification: any[]
  duplicate_primary_docs: any[]
  missing_official_docs: any[]
}

export function useSopDocsHome() {
  const myWorkspaces = ref<WorkspaceItem[]>([])
  const recentDocs = ref<ResourceItem[]>([])
  const currentStageDocs = ref<CurrentStageDoc[]>([])
  const governanceSummary = ref<GovernanceSummary | null>(null)
  const loading = ref(false)

  const fetchHome = async () => {
    loading.value = true
    try {
      const data = await request.get('/v1/external-docs/home/summary')
      myWorkspaces.value = (data?.my_workspaces || []) as WorkspaceItem[]
      recentDocs.value = (data?.recent_docs || []) as ResourceItem[]
      currentStageDocs.value = (data?.current_stage_docs || []) as CurrentStageDoc[]
      governanceSummary.value = (data?.governance || null) as GovernanceSummary
    } catch (e) {
      console.error(e)
    } finally {
      loading.value = false
    }
  }

  const openResource = async (resourceId: number, workspaceId?: number) => {
    const res = await request.post(`/v1/external-docs/resources/${resourceId}/open`, {
      workspace_id: workspaceId, client_type: 'web',
    })
    if (res?.open_url) {
      window.open(res.open_url, '_blank')
    }
  }

  onMounted(fetchHome)

  return {
    myWorkspaces, recentDocs, currentStageDocs, governanceSummary,
    loading, fetchHome, openResource,
  }
}
