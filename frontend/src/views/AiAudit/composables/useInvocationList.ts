import { reactive, ref } from 'vue'
import request from '#/utils/request'
import type { InvocationListItem, InvocationDetail, InvocationStats, TrendItem, BreakdownItem } from './useInvocationTypes'

export function useInvocationList() {
  const items = ref<InvocationListItem[]>([])
  const loading = ref(false)
  const total = ref(0)
  const page = ref(1)
  const pageSize = 20

  const filters = reactive({
    status: '',
    error_code: '',
    crm_customer_id: '',
    primary_model: '',
    scene_key: '',
    session_id: '',
  })
  const dateRange = ref<string[] | null>(null)

  const stats = ref<InvocationStats | null>(null)
  const trends = ref<TrendItem[]>([])
  const breakdown = ref<BreakdownItem[]>([])
  const detail = ref<InvocationDetail | null>(null)
  const detailVisible = ref(false)

  const fetchList = async () => {
    loading.value = true
    try {
      const params: Record<string, any> = { page: page.value, page_size: pageSize }
      if (filters.status) params.status = filters.status
      if (filters.error_code) params.error_code = filters.error_code
      if (filters.crm_customer_id) params.crm_customer_id = filters.crm_customer_id
      if (filters.primary_model) params.primary_model = filters.primary_model
      if (filters.scene_key) params.scene_key = filters.scene_key
      if (filters.session_id) params.session_id = filters.session_id
      if (dateRange.value?.length === 2) {
        params.date_start = dateRange.value[0]
        params.date_end = dateRange.value[1]
      }
      const res = await request.get('/v1/crm-customers/ai/invocations', { params })
      items.value = res.items || []
      total.value = res.total || 0
    } finally {
      loading.value = false
    }
  }

  const fetchStats = async () => {
    const params: Record<string, any> = {}
    if (dateRange.value?.length === 2) {
      params.date_start = dateRange.value[0]
      params.date_end = dateRange.value[1]
    }
    try {
      stats.value = await request.get('/v1/crm-customers/ai/invocations/stats', { params })
    } catch { /* ignore */ }
  }

  const fetchTrends = async () => {
    const params: Record<string, any> = {}
    if (dateRange.value?.length === 2) {
      params.date_start = dateRange.value[0]
      params.date_end = dateRange.value[1]
    } else {
      params.days = 14
    }
    try {
      trends.value = await request.get('/v1/crm-customers/ai/invocations/trends', { params })
    } catch { /* ignore */ }
  }

  const fetchBreakdown = async (dimension: string = 'model') => {
    const params: Record<string, any> = { dimension }
    if (dateRange.value?.length === 2) {
      params.date_start = dateRange.value[0]
      params.date_end = dateRange.value[1]
    }
    try {
      breakdown.value = await request.get('/v1/crm-customers/ai/invocations/breakdown', { params })
    } catch { /* ignore */ }
  }

  const openDetail = async (callId: string) => {
    try {
      detail.value = await request.get(`/v1/crm-customers/ai/invocations/${callId}`)
      detailVisible.value = true
    } catch { /* ignore */ }
  }

  const refresh = () => {
    page.value = 1
    fetchList()
    fetchStats()
    fetchTrends()
    fetchBreakdown()
  }

  const refreshCritical = () => {
    page.value = 1
    fetchList()
    fetchStats()
  }

  const filterByCustomer = (customerId: number) => {
    filters.crm_customer_id = String(customerId)
    refreshCritical()
  }

  const filterBySession = (sessionId: string) => {
    filters.session_id = sessionId
    refreshCritical()
  }

  const clearGroupFilter = () => {
    filters.crm_customer_id = ''
    filters.session_id = ''
    refreshCritical()
  }

  return {
    items, loading, total, page, pageSize,
    filters, dateRange,
    stats, trends, breakdown, detail, detailVisible,
    fetchList, fetchStats, fetchTrends, fetchBreakdown, openDetail,
    refresh, refreshCritical, filterByCustomer, filterBySession, clearGroupFilter,
  }
}
