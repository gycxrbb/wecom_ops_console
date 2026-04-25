import { ref, reactive } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import request from '#/utils/request'

export type CardModule = {
  key: string
  status: 'ok' | 'empty' | 'partial' | 'timeout' | 'error'
  payload: Record<string, any>
  freshness: string | null
  warnings: string[]
}

export type CustomerProfile = {
  customer_id: number
  cards: CardModule[]
  available_actions: string[]
  ai_chat_enabled: boolean
  ai_chat_reason: string | null
}

export type SafetySnapshotItem = {
  snapshot_id: number
  label: string
  display_label: string
  reference_time: string | null
  is_current: boolean
  is_archived: boolean
}

export type CustomerSearchItem = {
  id: number
  name: string
  gender: number | null
  birthday: string | null
  points: number
  total_points: number
  status: number
}

export type CustomerListItem = {
  id: number
  name: string
  gender: number | null
  birthday: string | null
  points: number
  total_points: number
  status: number
  channel_name: string | null
  coach_names: string | null
  group_names: string | null
  city: string | null
  created_at: string | null
}

export type FilterOption = { value: number; label: string }

export type FilterOptions = {
  coaches: FilterOption[]
  groups: FilterOption[]
  channels: FilterOption[]
}

export type ListFilters = {
  q: string
  coach_id: number | null
  group_id: number | null
  channel_id: number | null
}

export function useCrmProfile() {
  const router = useRouter()
  const route = useRoute()

  const loading = ref(false)
  const searching = ref(false)
  const searchResults = ref<CustomerSearchItem[]>([])
  const selectedCustomer = ref<CustomerSearchItem | null>(null)
  const profile = ref<CustomerProfile | null>(null)
  const safetySnapshots = ref<SafetySnapshotItem[]>([])
  const safetySnapshotLoading = ref(false)

  // --- List state ---
  const listLoading = ref(false)
  const listItems = ref<CustomerListItem[]>([])
  const listTotal = ref(0)
  const listPage = ref(1)
  const listPageSize = ref(20)
  const filters = reactive<ListFilters>({
    q: '',
    coach_id: null,
    group_id: null,
    channel_id: null,
  })

  // --- Filter options ---
  const filterOptions = ref<FilterOptions>({ coaches: [], groups: [], channels: [] })
  const filterOptionsLoaded = ref(false)

  const loadFilterOptions = async () => {
    if (filterOptionsLoaded.value) return
    try {
      const res: any = await request.get('/v1/crm-customers/filters')
      filterOptions.value = res || { coaches: [], groups: [], channels: [] }
      filterOptionsLoaded.value = true
    } catch {
      filterOptions.value = { coaches: [], groups: [], channels: [] }
    }
  }

  const loadList = async (page?: number, includeFilters = false) => {
    if (page !== undefined) listPage.value = page
    listLoading.value = true
    try {
      const params: Record<string, any> = {
        page: listPage.value,
        page_size: listPageSize.value,
      }
      if (filters.q.trim()) params.q = filters.q.trim()
      if (filters.coach_id !== null) params.coach_id = filters.coach_id
      if (filters.group_id !== null) params.group_id = filters.group_id
      if (filters.channel_id !== null) params.channel_id = filters.channel_id
      if (includeFilters) params.include_filters = 1

      const res: any = await request.get('/v1/crm-customers/list', { params })
      listItems.value = res?.items || []
      listTotal.value = res?.total || 0

      if (includeFilters && res?.filters && !filterOptionsLoaded.value) {
        filterOptions.value = res.filters
        filterOptionsLoaded.value = true
      }
    } catch {
      listItems.value = []
      listTotal.value = 0
    } finally {
      listLoading.value = false
    }
  }

  const resetFilters = () => {
    filters.q = ''
    filters.coach_id = null
    filters.group_id = null
    filters.channel_id = null
    loadList(1)
  }

  // --- Search (legacy dropdown) ---
  const searchCustomers = async (q: string) => {
    if (!q.trim()) {
      searchResults.value = []
      return
    }
    searching.value = true
    try {
      const res: any = await request.get('/v1/crm-customers/search', { params: { q } })
      searchResults.value = res || []
    } catch {
      searchResults.value = []
    } finally {
      searching.value = false
    }
  }

  // --- Profile detail ---
  const loadProfile = async (customerId: number) => {
    loading.value = true
    profile.value = null
    try {
      const res: any = await request.get(`/v1/crm-customers/${customerId}/profile`)
      profile.value = res
    } catch {
      profile.value = null
    } finally {
      loading.value = false
    }
  }

  const loadSafetySnapshots = async (customerId: number) => {
    safetySnapshotLoading.value = true
    try {
      const res: any = await request.get(`/v1/crm-customers/${customerId}/safety-snapshots`)
      safetySnapshots.value = res?.items || []
    } catch {
      safetySnapshots.value = []
    } finally {
      safetySnapshotLoading.value = false
    }
  }

  const loadSafetySnapshotDetail = async (customerId: number, snapshotId: number) => {
    const res: any = await request.get(`/v1/crm-customers/${customerId}/safety-snapshots/${snapshotId}`)
    return res?.card || null
  }

  const selectCustomer = (item: CustomerSearchItem | CustomerListItem) => {
    selectedCustomer.value = item as CustomerSearchItem
    searchResults.value = []
    loadProfile(item.id)
    loadSafetySnapshots(item.id)
    router.replace({ query: { ...route.query, cid: String(item.id) } })
  }

  const backToList = () => {
    selectedCustomer.value = null
    profile.value = null
    safetySnapshots.value = []
    const q = { ...route.query }
    delete q.cid
    router.replace({ query: q })
  }

  const restoreFromUrl = async () => {
    const cid = route.query.cid
    if (cid) {
      const customerId = Number(cid)
      if (!isNaN(customerId) && customerId > 0) {
        selectedCustomer.value = { id: customerId, name: '', gender: null, birthday: null, points: 0, total_points: 0, status: 0 }
        await Promise.all([loadProfile(customerId), loadSafetySnapshots(customerId)])
      }
    }
  }

  const getCard = (key: string): CardModule | undefined => {
    return profile.value?.cards?.find(c => c.key === key)
  }

  const genderText = (g: number | null) => {
    if (g === 1) return '男'
    if (g === 2) return '女'
    return '未知'
  }

  const calcAge = (birthday: string | null) => {
    if (!birthday) return null
    const birth = new Date(birthday)
    const diff = Date.now() - birth.getTime()
    return Math.floor(diff / (365.25 * 24 * 60 * 60 * 1000))
  }

  return {
    loading, searching, searchResults, selectedCustomer, profile,
    searchCustomers, loadProfile, selectCustomer, getCard,
    genderText, calcAge, backToList, restoreFromUrl,
    safetySnapshots, safetySnapshotLoading, loadSafetySnapshots, loadSafetySnapshotDetail,
    // list
    listLoading, listItems, listTotal, listPage, listPageSize,
    filters, filterOptions, filterOptionsLoaded,
    loadFilterOptions, loadList, resetFilters,
  }
}
