/* playground 对话上云——与后端 /api/image-gen/v1/conversations 同步。
 *
 * 独立模块（不动 store.ts 业务逻辑），apiKey 从 store 的 active profile 取
 * （修复嵌入模式下 URL apiKey 被 App.tsx replaceState 清掉导致的 401）。
 * 本期仅同步对话；任务/图片在 P3/P4。
 *
 * 同步策略：debounce 1s + diff（按 conversation.updatedAt 判断变更/新建/删除），
 * 复用 store.ts 的 persistence gate（flush 到 IndexedDB 后触发 scheduleServerSync）。
 */
import { useStore } from '../store'
import { getActiveApiProfile } from './apiProfiles'
import type { AgentConversation, TaskRecord } from '../types'

function getApiKey(): string {
  const profile = getActiveApiProfile(useStore.getState().settings)
  return profile?.apiKey || ''
}

async function authedFetch(path: string, init?: RequestInit): Promise<Response> {
  // 10s 超时：后端慢/不可达时及时失败（被调用方 catch），避免 initStore 卡住阻塞启动
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), 10000)
  try {
    const res = await fetch(`${window.location.origin}${path}`, {
      ...init,
      signal: controller.signal,
      headers: { Authorization: `Bearer ${getApiKey()}`, ...(init?.headers || {}) },
    })
    if (!res.ok) throw new Error(`${init?.method || 'GET'} ${path} -> ${res.status}`)
    return res
  } finally {
    clearTimeout(timer)
  }
}

interface ConversationSummary {
  conversation_id: string
  title: string | null
  auto_title: string | null
  last_active_at: string | null
}

export async function listServerConversations(page = 1, pageSize = 100): Promise<ConversationSummary[]> {
  const res = await authedFetch(`/api/image-gen/v1/conversations?page=${page}&page_size=${pageSize}`)
  const data = await res.json()
  return data?.items || []
}

export async function getServerConversationData(conversationId: string): Promise<string | null> {
  // 返回 data_json（整对话 JSON 字符串）；失败返回 null（不抛，让批量拉取跳过坏记录）
  try {
    const res = await authedFetch(`/api/image-gen/v1/conversations/${encodeURIComponent(conversationId)}`)
    const data = await res.json()
    return data?.data_json || null
  } catch {
    return null
  }
}

export async function upsertServerConversation(conversation: AgentConversation): Promise<void> {
  await authedFetch(`/api/image-gen/v1/conversations/${encodeURIComponent(conversation.id)}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      title: conversation.title,
      data_json: JSON.stringify(conversation),
      last_active_at: new Date(conversation.updatedAt).toISOString(),
    }),
  })
}

export async function deleteServerConversation(conversationId: string): Promise<void> {
  await authedFetch(`/api/image-gen/v1/conversations/${encodeURIComponent(conversationId)}`, { method: 'DELETE' })
}

/** 拉全部对话（摘要 + 并发 detail），解析 data_json 还原 AgentConversation。 */
export async function pullServerConversations(): Promise<AgentConversation[]> {
  const summaries = await listServerConversations()
  const details = await Promise.all(summaries.map((s) => getServerConversationData(s.conversation_id)))
  const result: AgentConversation[] = []
  for (const dataJson of details) {
    if (!dataJson) continue
    try {
      const parsed = JSON.parse(dataJson) as AgentConversation
      if (parsed && typeof parsed.id === 'string') result.push(parsed)
    } catch {
      // 跳过损坏记录
    }
  }
  return result
}

// ── 增量同步（debounce + diff）──

// conversation id -> 上次同步到后端的 updatedAt；用于 diff 判断变更/新建/删除
const lastSyncedUpdatedAt = new Map<string, number>()

/** 初始化同步缓存：把已知对话（拉取/首迁后的）标记为已同步，避免重复上传。 */
export function initServerSyncCache(conversations: AgentConversation[]) {
  lastSyncedUpdatedAt.clear()
  for (const c of conversations) lastSyncedUpdatedAt.set(c.id, c.updatedAt)
}

let serverSyncTimer: ReturnType<typeof setTimeout> | null = null
let serverSyncRunning = false

/** debounce 1s 后执行增量同步（变更/新建 upsert，删除 delete）。 */
export function scheduleServerSync() {
  if (serverSyncTimer) clearTimeout(serverSyncTimer)
  serverSyncTimer = setTimeout(() => {
    serverSyncTimer = null
    void syncConversationsToServer()
  }, 1000)
}

async function syncConversationsToServer() {
  if (serverSyncRunning) {
    scheduleServerSync()
    return
  }
  serverSyncRunning = true
  try {
    const current = useStore.getState().agentConversations
    const currentIds = new Set(current.map((c) => c.id))
    const toUpsert: AgentConversation[] = []
    for (const c of current) {
      if (lastSyncedUpdatedAt.get(c.id) !== c.updatedAt) toUpsert.push(c)
    }
    const toDelete: string[] = []
    for (const id of lastSyncedUpdatedAt.keys()) {
      if (!currentIds.has(id)) toDelete.push(id)
    }
    if (toUpsert.length === 0 && toDelete.length === 0) return
    await Promise.all([
      ...toUpsert.map((c) => upsertServerConversation(c).catch(() => {})),
      ...toDelete.map((id) => deleteServerConversation(id).catch(() => {})),
    ])
    for (const c of toUpsert) lastSyncedUpdatedAt.set(c.id, c.updatedAt)
    for (const id of toDelete) lastSyncedUpdatedAt.delete(id)
  } catch (e) {
    console.warn('sync conversations to server failed', e)
  } finally {
    serverSyncRunning = false
  }
}

// ── 任务同步（P3）──

interface TaskSummary {
  task_id: string
  conversation_id: string | null
  created_at: string | null
}

export async function listServerTasks(page = 1, pageSize = 100): Promise<TaskSummary[]> {
  const res = await authedFetch(`/api/image-gen/v1/tasks?page=${page}&page_size=${pageSize}`)
  const data = await res.json()
  return data?.items || []
}

export async function getServerTaskData(taskId: string): Promise<string | null> {
  try {
    const res = await authedFetch(`/api/image-gen/v1/tasks/${encodeURIComponent(taskId)}`)
    const data = await res.json()
    return data?.data_json || null
  } catch {
    return null
  }
}

export async function upsertServerTask(task: TaskRecord): Promise<void> {
  await authedFetch(`/api/image-gen/v1/tasks/${encodeURIComponent(task.id)}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      conversation_id: task.agentConversationId || null,
      data_json: JSON.stringify(task),
      created_at: task.createdAt ? new Date(task.createdAt).toISOString() : null,
    }),
  })
}

export async function deleteServerTask(taskId: string): Promise<void> {
  await authedFetch(`/api/image-gen/v1/tasks/${encodeURIComponent(taskId)}`, { method: 'DELETE' })
}

export async function pullServerTasks(): Promise<TaskRecord[]> {
  const summaries = await listServerTasks()
  const details = await Promise.all(summaries.map((s) => getServerTaskData(s.task_id)))
  const result: TaskRecord[] = []
  for (const dataJson of details) {
    if (!dataJson) continue
    try {
      const parsed = JSON.parse(dataJson) as TaskRecord
      if (parsed && typeof parsed.id === 'string') result.push(parsed)
    } catch {
      // 跳过损坏记录
    }
  }
  return result
}

const lastSyncedTaskHash = new Map<string, number>()

function taskHash(task: TaskRecord): number {
  // 用 JSON 字符串的简易 hash 判断 task 是否变化（含 status/outputImages/参数等）
  let h = 0
  const s = JSON.stringify(task)
  for (let i = 0; i < s.length; i++) h = (Math.imul(31, h) + s.charCodeAt(i)) | 0
  return h
}

export function initServerTaskSyncCache(tasks: TaskRecord[]) {
  lastSyncedTaskHash.clear()
  for (const t of tasks) lastSyncedTaskHash.set(t.id, taskHash(t))
}

let taskSyncTimer: ReturnType<typeof setTimeout> | null = null
let taskSyncRunning = false

export function scheduleServerTaskSync() {
  if (taskSyncTimer) clearTimeout(taskSyncTimer)
  taskSyncTimer = setTimeout(() => {
    taskSyncTimer = null
    void syncTasksToServer()
  }, 1500)
}

async function syncTasksToServer() {
  if (taskSyncRunning) {
    scheduleServerTaskSync()
    return
  }
  taskSyncRunning = true
  try {
    const current = useStore.getState().tasks
    const currentIds = new Set(current.map((t) => t.id))
    const toUpsert: TaskRecord[] = []
    for (const t of current) {
      if (lastSyncedTaskHash.get(t.id) !== taskHash(t)) toUpsert.push(t)
    }
    const toDelete: string[] = []
    for (const id of lastSyncedTaskHash.keys()) {
      if (!currentIds.has(id)) toDelete.push(id)
    }
    if (toUpsert.length === 0 && toDelete.length === 0) return
    await Promise.all([
      ...toUpsert.map((t) => upsertServerTask(t).catch(() => {})),
      ...toDelete.map((id) => deleteServerTask(id).catch(() => {})),
    ])
    for (const t of toUpsert) lastSyncedTaskHash.set(t.id, taskHash(t))
    for (const id of toDelete) lastSyncedTaskHash.delete(id)
  } catch (e) {
    console.warn('sync tasks to server failed', e)
  } finally {
    taskSyncRunning = false
  }
}

// ── 图片资产（P4 七牛直传）──

export async function getServerAssetUrl(imageId: string): Promise<{ public_url: string; thumb_url: string } | null> {
  try {
    const res = await authedFetch(`/api/image-gen/v1/assets/${encodeURIComponent(imageId)}`)
    const data = await res.json()
    if (data?.public_url) return { public_url: data.public_url, thumb_url: data.thumb_url || data.public_url }
    return null
  } catch {
    return null
  }
}

interface AssetPrepareResponse {
  mode: string
  upload_url?: string
  token?: string
  object_key?: string
  public_url?: string
  thumb_url?: string
}

async function prepareServerAsset(imageId: string, mimeType: string): Promise<AssetPrepareResponse | null> {
  const res = await authedFetch(`/api/image-gen/v1/assets/prepare`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ image_id: imageId, mime_type: mimeType }),
  })
  return (await res.json()) as AssetPrepareResponse
}

async function confirmServerAsset(
  imageId: string,
  objectKey: string,
  publicUrl: string,
  width: number,
  height: number,
  source: string,
): Promise<void> {
  await authedFetch(`/api/image-gen/v1/assets/confirm`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      image_id: imageId,
      object_key: objectKey,
      public_url: publicUrl,
      width,
      height,
      source,
    }),
  })
}

function mimeFromDataUrl(dataUrl: string): string {
  return /data:(.*?);/.exec(dataUrl)?.[1] || 'image/png'
}

function dataUrlToBlob(dataUrl: string): Blob {
  const b64 = dataUrl.split(',')[1] || ''
  const binary = atob(b64)
  const bytes = new Uint8Array(binary.length)
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i)
  return new Blob([bytes], { type: mimeFromDataUrl(dataUrl) })
}

/**
 * 确保图片已上云（查重 → prepare → 直传七牛 → confirm），返回 url。
 * 失败返回 null（不阻塞本地持久化/显示）。
 */
export async function ensureServerAsset(
  imageId: string,
  dataUrl: string,
  source: string,
  width = 0,
  height = 0,
): Promise<string | null> {
  const existing = await getServerAssetUrl(imageId)
  if (existing) return existing.public_url
  const cred = await prepareServerAsset(imageId, mimeFromDataUrl(dataUrl))
  if (!cred) return null
  if (cred.mode === 'existing' && cred.public_url) return cred.public_url
  if (cred.mode !== 'qiniu' || !cred.upload_url || !cred.token || !cred.object_key || !cred.public_url) return null
  // 直传七牛：FormData(token + key + file) POST upload_url
  const form = new FormData()
  form.append('token', cred.token)
  form.append('key', cred.object_key)
  form.append('file', dataUrlToBlob(dataUrl))
  const uploadRes = await fetch(cred.upload_url, { method: 'POST', body: form })
  if (!uploadRes.ok) {
    console.warn('qiniu direct upload failed', uploadRes.status)
    return null
  }
  await confirmServerAsset(imageId, cred.object_key, cred.public_url, width, height, source)
  return cred.public_url
}
