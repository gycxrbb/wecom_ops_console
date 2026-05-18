import { ref } from 'vue'

export interface ProbeResult {
  name: string
  status: 'ok' | 'fail' | 'timeout'
  latency_ms: number
  detail?: string
}

export function useBrowserDiagnostics() {
  const running = ref(false)
  const results = ref<ProbeResult[]>([])

  const run = async () => {
    running.value = true
    results.value = []
    const probes: Promise<ProbeResult>[] = [
      probeBackendHealth(),
      probeAiProvider(),
    ]
    results.value = await Promise.all(probes)
    running.value = false
  }

  return { running, results, run }
}

async function probeBackendHealth(): Promise<ProbeResult> {
  const start = performance.now()
  try {
    const res = await fetch('/api/v1/health', { signal: AbortSignal.timeout(5000) })
    const json = await res.json()
    const latency = Math.round(performance.now() - start)
    return {
      name: '后端服务',
      status: json.status === 'ok' ? 'ok' : 'fail',
      latency_ms: latency,
      detail: json.db ? '数据库连接正常' : '数据库连接异常',
    }
  } catch (e: any) {
    return {
      name: '后端服务',
      status: 'fail',
      latency_ms: Math.round(performance.now() - start),
      detail: e?.name === 'TimeoutError' ? '连接超时（5秒）' : '无法连接',
    }
  }
}

async function probeAiProvider(): Promise<ProbeResult> {
  // Test basic connectivity to the AI provider via the backend's diagnostics endpoint
  const start = performance.now()
  try {
    const token = localStorage.getItem('access_token')
    const res = await fetch('/api/v1/crm-customers/ai/diagnostics', {
      headers: { Authorization: token ? `Bearer ${token}` : '' },
      signal: AbortSignal.timeout(15000),
    })
    const latency = Math.round(performance.now() - start)
    if (!res.ok) {
      return {
        name: 'AI 服务诊断',
        status: res.status === 403 ? 'fail' : 'fail',
        latency_ms: latency,
        detail: res.status === 403 ? '需要管理员权限' : `HTTP ${res.status}`,
      }
    }
    const json = await res.json()
    const failed = (json.probes || []).filter((p: any) => p.status === 'fail')
    return {
      name: 'AI 服务诊断',
      status: failed.length === 0 ? 'ok' : 'fail',
      latency_ms: latency,
      detail: failed.length === 0
        ? '所有探针通过'
        : `${failed.length} 项异常: ${failed.map((p: any) => p.name).join(', ')}`,
    }
  } catch (e: any) {
    return {
      name: 'AI 服务诊断',
      status: 'timeout',
      latency_ms: Math.round(performance.now() - start),
      detail: e?.name === 'TimeoutError' ? '诊断超时（15秒）' : '无法执行诊断',
    }
  }
}
