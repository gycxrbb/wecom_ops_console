import { ref, onMounted } from 'vue'
import request from '@/utils/request'
import { useUserStore } from '@/stores/user'

export interface WorkspaceItem {
  id: number
  name: string
  workspace_type: string
  status: string
  owner_user_id: number | null
  current_stage_term_id: number | null
  description: string
  created_at: string | null
  updated_at: string | null
}

export interface ResourceItem {
  id: number
  title: string
  canonical_url: string
  open_url: string
  source_platform: string
  doc_type: string
  status: string
  verification_status: string
  summary: string
  last_opened_at: string | null
  created_at: string | null
  updated_at: string | null
}

export interface GovernanceSummary {
  needs_sorting: any[]
  needs_verification: any[]
  duplicate_primary_docs: any[]
  missing_official_docs: any[]
}

export function useSopDocsHome() {
  const userStore = useUserStore()
  const myWorkspaces = ref<WorkspaceItem[]>([])
  const sharedWorkspaces = ref<WorkspaceItem[]>([])
  const systemWorkspaces = ref<WorkspaceItem[]>([])
  const allWorkspaces = ref<WorkspaceItem[]>([])
  const recentDocs = ref<ResourceItem[]>([])
  const governanceSummary = ref<GovernanceSummary | null>(null)
  const loading = ref(false)

  const fetchHome = async () => {
    loading.value = true
    try {
      const [ws, recent, gov] = await Promise.all([
        request.get('/v1/external-docs/workspaces'),
        request.get('/v1/external-docs/resources/recent-opened?limit=8'),
        request.get('/v1/external-docs/governance/queue'),
      ])
      allWorkspaces.value = (ws || []) as WorkspaceItem[]
      const currentUserId = userStore.user?.id ?? null
      const all = (ws || []) as WorkspaceItem[]
      myWorkspaces.value = all.filter(item =>
        item.owner_user_id === currentUserId &&
        item.workspace_type !== 'template_hub' &&
        item.workspace_type !== 'inbox',
      )
      systemWorkspaces.value = all.filter(item =>
        item.workspace_type === 'template_hub' || item.workspace_type === 'inbox',
      )
      sharedWorkspaces.value = all.filter(item =>
        !myWorkspaces.value.some(wsItem => wsItem.id === item.id) &&
        !systemWorkspaces.value.some(wsItem => wsItem.id === item.id),
      )
      recentDocs.value = (recent || []) as ResourceItem[]
      governanceSummary.value = (gov || null) as GovernanceSummary
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
    myWorkspaces, sharedWorkspaces, systemWorkspaces, allWorkspaces, recentDocs, governanceSummary,
    loading, fetchHome, openResource,
  }
}
