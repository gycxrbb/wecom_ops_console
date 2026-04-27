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

type CrmProfileNavigationCache = {
  customerId: number
  windowDays: number
}

export type AiProfileCacheStatus = {
  customer_id: number
  status: string
  cache_key: string
  health_window_days: number
  ready: boolean
  source: string
  generated_at?: string | null
  expires_at?: string | null
  stale_expires_at?: string | null
  message?: string
}

const NAVIGATION_CACHE_KEY = 'crm_profile.navigation_cache'
const HEALTH_WINDOWS = [7, 14, 30]

const normalizePositiveInt = (value: unknown): number | null => {
  const raw = Array.isArray(value) ? value[0] : value
  const parsed = Number(raw)
  return Number.isInteger(parsed) && parsed > 0 ? parsed : null
}

const normalizeWindowDays = (value: unknown): number => {
  const parsed = Number(value)
  return HEALTH_WINDOWS.includes(parsed) ? parsed : 7
}

const readNavigationCache = (): CrmProfileNavigationCache | null => {
  try {
    const raw = window.sessionStorage.getItem(NAVIGATION_CACHE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw)
    const customerId = normalizePositiveInt(parsed?.customerId)
    if (!customerId) return null
    return {
      customerId,
      windowDays: normalizeWindowDays(parsed?.windowDays),
    }
  } catch {
    return null
  }
}

const writeNavigationCache = (customerId: number, windowDays: number) => {
  try {
    window.sessionStorage.setItem(
      NAVIGATION_CACHE_KEY,
      JSON.stringify({ customerId, windowDays: normalizeWindowDays(windowDays) }),
    )
  } catch {
    // sessionStorage may be unavailable in restricted browser modes.
  }
}

const clearNavigationCache = () => {
  try {
    window.sessionStorage.removeItem(NAVIGATION_CACHE_KEY)
  } catch {
    // sessionStorage may be unavailable in restricted browser modes.
  }
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
  const currentWindowDays = ref(7)
  const healthLoading = ref(false)
  const profileCacheStatus = ref<AiProfileCacheStatus | null>(null)

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

  const refreshProfileCacheStatus = async (customerId: number, windowDays: number) => {
    try {
      const res: any = await request.get(`/v1/crm-customers/${customerId}/ai/cache-status`, {
        params: { health_window_days: normalizeWindowDays(windowDays) },
      })
      profileCacheStatus.value = res || null
      return profileCacheStatus.value
    } catch {
      return null
    }
  }

  const preloadProfileCache = async (customerId: number, windowDays: number) => {
    const w = normalizeWindowDays(windowDays)
    profileCacheStatus.value = {
      customer_id: customerId,
      status: 'checking',
      cache_key: `profile:${customerId}:hw${w}`,
      health_window_days: w,
      ready: false,
      source: 'frontend',
    }
    try {
      await request.post(`/v1/crm-customers/${customerId}/ai/preload`, {
        health_window_days: w,
      }).then((res: any) => {
        profileCacheStatus.value = res || profileCacheStatus.value
      })
      if (!profileCacheStatus.value?.ready) {
        window.setTimeout(() => { void refreshProfileCacheStatus(customerId, w) }, 1500)
        window.setTimeout(() => { void refreshProfileCacheStatus(customerId, w) }, 5000)
      }
    } catch {
      await refreshProfileCacheStatus(customerId, w)
    }
  }

  // --- Profile detail ---
  const loadProfile = async (customerId: number, windowDays?: number) => {
    loading.value = true
    profile.value = null
    profileCacheStatus.value = null
    try {
      const w = windowDays ?? currentWindowDays.value
      const res: any = await request.get(`/v1/crm-customers/${customerId}/profile`, {
        params: { window: w },
      })
      profile.value = res
      currentWindowDays.value = w
      void preloadProfileCache(customerId, w)
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

  const switchHealthWindow = async (customerId: number, windowDays: number) => {
    healthLoading.value = true
    try {
      const res: any = await request.get(`/v1/crm-customers/${customerId}/profile`, {
        params: { window: windowDays },
      })
      profile.value = res
      currentWindowDays.value = windowDays
      writeNavigationCache(customerId, windowDays)
      void preloadProfileCache(customerId, windowDays)
    } catch {
      // keep existing profile on error
    } finally {
      healthLoading.value = false
    }
  }

  const loadSafetySnapshotDetail = async (customerId: number, snapshotId: number) => {
    const res: any = await request.get(`/v1/crm-customers/${customerId}/safety-snapshots/${snapshotId}`)
    return res?.card || null
  }

  const selectCustomer = (item: CustomerSearchItem | CustomerListItem) => {
    selectedCustomer.value = item as CustomerSearchItem
    searchResults.value = []
    currentWindowDays.value = 7
    loadProfile(item.id)
    loadSafetySnapshots(item.id)
    writeNavigationCache(item.id, currentWindowDays.value)
    router.replace({ query: { ...route.query, cid: String(item.id) } })
  }

  const backToList = () => {
    selectedCustomer.value = null
    profile.value = null
    profileCacheStatus.value = null
    safetySnapshots.value = []
    clearNavigationCache()
    const q = { ...route.query }
    delete q.cid
    router.replace({ query: q })
  }

  const restoreFromUrl = async () => {
    const routeCustomerId = normalizePositiveInt(route.query.cid)
    const cachedNavigation = readNavigationCache()
    const customerId = routeCustomerId ?? cachedNavigation?.customerId
    if (!customerId) return

    const windowDays = cachedNavigation?.customerId === customerId
      ? cachedNavigation.windowDays
      : 7

    selectedCustomer.value = { id: customerId, name: '', gender: null, birthday: null, points: 0, total_points: 0, status: 0 }
    currentWindowDays.value = windowDays
    writeNavigationCache(customerId, windowDays)
    if (!routeCustomerId) {
      router.replace({ query: { ...route.query, cid: String(customerId) } })
    }
    await Promise.all([loadProfile(customerId, windowDays), loadSafetySnapshots(customerId)])
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
    currentWindowDays, healthLoading, switchHealthWindow,
    profileCacheStatus, preloadProfileCache, refreshProfileCacheStatus,
    // list
    listLoading, listItems, listTotal, listPage, listPageSize,
    filters, filterOptions, filterOptionsLoaded,
    loadFilterOptions, loadList, resetFilters,
  }
}
