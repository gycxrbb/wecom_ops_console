import { ref, watch } from 'vue'
import request from '#/utils/request'

export interface BioageResult {
  id: number
  customer_id: number
  param_version: string
  chronological_age: number
  biological_age: number
  age_acceleration: number
  n_biomarkers: number
  total_biomarkers: number
  confidence: string
  dim_scores: Record<string, number | null> | null
  contributions: Record<string, number> | null
  missing_codes: string[] | null
  warnings: string[] | null
  llm_reading: string | null
  llm_actions: string[] | null
  created_at: string | null
}

export interface DataReadiness {
  customer_id: number
  has_birthday: boolean
  has_gender: boolean
  has_checkup: boolean
  latest_checkup_date: string | null
  checkup_age_days: number | null
  bp_records_last_7d: number
  biomarkers: Record<string, { available: boolean; value?: number; unit?: string; date?: string }>
  n_available: number
  total: number
  can_calculate: boolean
  confidence: string
  missing: string[]
}

export interface BioageHistory {
  history: BioageResult[]
  trend: {
    comparable: boolean
    last_change?: number
    total_change?: number
  } | null
  version_changes: { from: string; to: string; date: string }[]
}

export function useBioAge() {
  const result = ref<BioageResult | null>(null)
  const readiness = ref<DataReadiness | null>(null)
  const history = ref<BioageHistory | null>(null)
  const loading = ref(false)
  const calculating = ref(false)
  const error = ref('')

  const fetchLatest = async (customerId: number) => {
    try {
      const res = await request.get<any>(`/v1/bioage/latest/${customerId}`)
      if (res && typeof res === 'object' && res.biological_age !== undefined) {
        result.value = res
      } else {
        result.value = null
      }
    } catch {
      result.value = null
    }
  }

  const fetchReadiness = async (customerId: number) => {
    try {
      const res = await request.get<any>(`/v1/bioage/data-readiness/${customerId}`)
      if (res && typeof res === 'object' && res.customer_id) {
        readiness.value = res
      } else {
        readiness.value = null
      }
    } catch {
      readiness.value = null
    }
  }

  const fetchHistory = async (customerId: number) => {
    try {
      const res = await request.get<any>(`/v1/bioage/history/${customerId}`)
      if (res && Array.isArray(res.history)) {
        history.value = res
      } else {
        history.value = null
      }
    } catch {
      history.value = null
    }
  }

  const loadAll = async (customerId: number) => {
    loading.value = true
    error.value = ''
    try {
      await Promise.all([fetchLatest(customerId), fetchReadiness(customerId), fetchHistory(customerId)])
    } catch (e: any) {
      error.value = e.message || '加载失败'
    } finally {
      loading.value = false
    }
  }

  const calculate = async (customerId: number) => {
    calculating.value = true
    error.value = ''
    try {
      const res = await request.post<any>(`/v1/bioage/calculate`, {
        customer_id: customerId,
      })
      if (res && res.biological_age !== undefined) {
        result.value = res
        await fetchHistory(customerId)
        await fetchReadiness(customerId)
        return res
      } else {
        error.value = res?.reason || '测算失败'
        return null
      }
    } catch (e: any) {
      error.value = e.serverData?.reason || e.message || '测算失败'
      return null
    } finally {
      calculating.value = false
    }
  }

  return {
    result, readiness, history,
    loading, calculating, error,
    loadAll, calculate,
    fetchLatest, fetchReadiness, fetchHistory,
  }
}
