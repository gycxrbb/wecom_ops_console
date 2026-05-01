/**
 * Preload scheduler — manages prioritized prefetch execution.
 *
 * P0: Execute immediately after login (Promise.allSettled).
 * P1: Execute after idle callback or short delay.
 * P2: On-demand only (hover/prefetchByRoute).
 *
 * Features:
 * - Concurrency limit (3)
 * - Per-request timeout (5s)
 * - In-flight promise dedup (same key shares one request)
 * - Silent failure (never blocks login or page access)
 */

import request from './request'
import { setPreloaded, buildCacheKey, clearPreloadCache } from './preloadCache'
import { hasPermission } from './permissions'
import type { PermissionKey } from './permissions'
import MANIFEST, { type PreloadTask, type PreloadPriority } from './preloadManifest'

const CONCURRENCY = 3
const TIMEOUT_MS = 5_000
const P1_DELAY_MS = 400

// ── In-flight dedup ──
const inFlight = new Map<string, Promise<any>>()

function fetchWithTimeout(url: string, params?: Record<string, unknown>): Promise<any> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error('preload timeout')), TIMEOUT_MS)
    request.get(url, { params, timeout: TIMEOUT_MS })
      .then((data: any) => { clearTimeout(timer); resolve(data) })
      .catch((err: any) => { clearTimeout(timer); reject(err) })
  })
}

function executeTask(task: PreloadTask): Promise<void> {
  const config = { method: 'get' as const, url: task.request.url, params: task.request.params }
  const key = buildCacheKey(config)

  // Deduplicate: reuse in-flight promise for same key
  if (inFlight.has(key)) return inFlight.get(key)!

  const promise = fetchWithTimeout(task.request.url, task.request.params)
    .then((data: any) => {
      setPreloaded(key, data, {
        ttlMs: task.ttlMs,
        resourceTags: task.resourceTags,
        source: 'login_preload',
      })
    })
    .catch(() => { /* silent */ })
    .finally(() => { inFlight.delete(key) })

  inFlight.set(key, promise)
  return promise
}

/** Filter manifest by user permissions and role. */
function filterTasks(user: any): PreloadTask[] {
  const isAdmin = user?.role === 'admin'
  return MANIFEST.filter(task => {
    if (task.adminOnly && !isAdmin) return false
    if (task.permission && !hasPermission(user, task.permission as PermissionKey)) return false
    return true
  })
}

/** Run tasks with concurrency limit. */
async function runWithConcurrency(tasks: PreloadTask[]): Promise<void> {
  const queue = [...tasks]
  const workers: Promise<void>[] = []

  const next = async (): Promise<void> => {
    while (queue.length) {
      const task = queue.shift()!
      await executeTask(task)
    }
  }

  for (let i = 0; i < Math.min(CONCURRENCY, queue.length); i++) {
    workers.push(next())
  }
  await Promise.all(workers)
}

// ── Public API ──

/** Execute P0 tasks immediately. Call after login/bootstrap. */
export async function executeP0(user: any): Promise<void> {
  const tasks = filterTasks(user).filter(t => t.priority === 'P0')
  await runWithConcurrency(tasks)
}

/** Schedule P1 tasks after idle/delay. Non-blocking. */
export function scheduleP1(user: any): void {
  const tasks = filterTasks(user).filter(t => t.priority === 'P1')

  const run = () => runWithConcurrency(tasks)

  if (typeof requestIdleCallback !== 'undefined') {
    requestIdleCallback(run, { timeout: 2000 })
  } else {
    setTimeout(run, P1_DELAY_MS)
  }
}

/** Prefetch tasks for a specific route name (for hover/on-demand). */
export function prefetchByRoute(user: any, routeName: string): void {
  const tasks = filterTasks(user).filter(
    t => t.priority === 'P2' || (t.priority === 'P1' && t.route === routeName)
  )
  if (!tasks.length) return
  runWithConcurrency(tasks)
}

/** Reset everything (call on logout or re-login). */
export function resetScheduler(): void {
  inFlight.clear()
  clearPreloadCache()
}
