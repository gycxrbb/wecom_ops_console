/** Composable for visual job polling, confirm, regenerate, feedback, hide. */
import { ref } from 'vue'
import request from '#/utils/request'

export interface JobDetail {
  job_id: string
  status: string
  topic: string
  confidence: number
  safety_level: string
  preview_url: string | null
  asset_id: string | null
  sendable: boolean
  error_message: string | null
}

export function useVisualJobs() {
  const pollers = ref<Map<string, ReturnType<typeof setInterval>>>(new Map())
  const POLL_INTERVAL = 2000
  const POLL_MAX_MS = 180000

  function startPolling(
    jobId: string,
    onUpdate: (jobId: string, data: JobDetail) => void,
  ) {
    if (pollers.value.has(jobId)) return
    const startTime = Date.now()

    const id = setInterval(async () => {
      if (Date.now() - startTime > POLL_MAX_MS) {
        stopPolling(jobId)
        onUpdate(jobId, { job_id: jobId, status: 'failed', topic: '', confidence: 0, safety_level: '', preview_url: null, asset_id: null, sendable: false, error_message: '轮询超时' })
        return
      }
      try {
        const data = await request.get<any, JobDetail>(`/v1/ai-visual/jobs/${jobId}`)
        onUpdate(jobId, data)
        if (data.status === 'ready' || data.status === 'failed') {
          stopPolling(jobId)
        }
      } catch {
        // Network error — keep polling
      }
    }, POLL_INTERVAL)

    pollers.value.set(jobId, id)
  }

  function stopPolling(jobId: string) {
    const id = pollers.value.get(jobId)
    if (id) {
      clearInterval(id)
      pollers.value.delete(jobId)
    }
  }

  async function confirmVisual(
    sessionId: string,
    customerId: number | undefined,
    topic: string,
    confirmed: boolean,
    extra: { visual_type?: string; safety_level?: string; confidence?: number } = {},
  ): Promise<{ job_id: string | null; status: string } | null> {
    try {
      const res = await request.post<any, any>('/v1/ai-visual/jobs/confirm', {
        session_id: sessionId,
        customer_id: customerId,
        topic,
        confirmed,
        ...extra,
      })
      return { job_id: res.job_id || null, status: res.status }
    } catch {
      return null
    }
  }

  async function regenerateVisual(jobId: string): Promise<{ job_id: string; status: string } | null> {
    try {
      return await request.post<any, any>(`/v1/ai-visual/jobs/${jobId}/regenerate`)
    } catch {
      return null
    }
  }

  async function hideVisual(jobId: string): Promise<void> {
    try {
      await request.post(`/v1/ai-visual/jobs/${jobId}/hide`)
    } catch { /* ignore */ }
  }

  async function sendVisualFeedback(jobId: string, feedback: 'like' | 'dislike'): Promise<void> {
    try {
      await request.post(`/v1/ai-visual/jobs/${jobId}/feedback`, { feedback })
    } catch { /* ignore */ }
  }

  function cleanup() {
    for (const id of pollers.value.values()) {
      clearInterval(id)
    }
    pollers.value.clear()
  }

  return { startPolling, stopPolling, confirmVisual, regenerateVisual, hideVisual, sendVisualFeedback, cleanup }
}
