import { ref, reactive, watch } from 'vue'
import request from '#/utils/request'

export interface BindingRow {
  binding_id: number
  resource_id: number
  title: string
  doc_type: string
  open_url: string
  verification_status: string
  relation_role: string
  is_primary: boolean
  remark: string
  workspace_id: number | null
  workspace_name: string
  stage_term_id: number | null
  stage_label: string
  deliverable_term_id: number | null
  deliverable_label: string
  owner_name: string
  updated_at: string
}

export function useBindingList() {
  const items = ref<BindingRow[]>([])
  const total = ref(0)
  const loading = ref(false)

  const filters = reactive({
    workspace_id: null as number | null,
    stage_term_id: null as number | null,
    relation_role: '' as string,
    keyword: '',
    page: 1,
    page_size: 20,
  })

  const fetchList = async () => {
    loading.value = true
    try {
      const params: Record<string, any> = {
        page: filters.page,
        page_size: filters.page_size,
      }
      if (filters.workspace_id) params.workspace_id = filters.workspace_id
      if (filters.stage_term_id) params.stage_term_id = filters.stage_term_id
      if (filters.relation_role) params.relation_role = filters.relation_role
      if (filters.keyword) params.keyword = filters.keyword
      const data = await request.get('/v1/external-docs/bindings/flat', { params })
      items.value = (data?.items || []) as BindingRow[]
      total.value = data?.total || 0
    } catch (e) {
      console.error(e)
    } finally {
      loading.value = false
    }
  }

  const setTab = (tab: string) => {
    filters.relation_role = tab === 'all' ? '' : tab
    filters.page = 1
  }

  watch(
    () => [filters.workspace_id, filters.stage_term_id, filters.relation_role, filters.keyword, filters.page],
    () => { fetchList() },
  )

  return { items, total, loading, filters, fetchList, setTab }
}
