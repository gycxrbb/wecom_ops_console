// 内部上传提示词：与后端 /api/v1/image-gen/prompts 交互（Bearer JWT 鉴权，同 agent 端点）。
// 内部 prompt 的 profession = 上传时选的 category（单职业）；远程 prompt 的 profession 来自 AI 预计算。
import type { Prompt } from './promptsService'

const INTERNAL_PROMPTS_PATH = '/api/v1/image-gen/prompts'

type InternalPromptItem = {
  id: number
  title: string
  body: string
  category: string
  tags: string[]
  scope: string
  cover_url: string
  contributor: { id: number; display_name: string; avatar_url: string } | null
  created_at: string | null
}

export async function fetchInternalPrompts(apiKey: string, category?: string): Promise<Prompt[]> {
  const url = category ? `${INTERNAL_PROMPTS_PATH}?category=${encodeURIComponent(category)}` : INTERNAL_PROMPTS_PATH
  const res = await fetch(url, {
    headers: { Authorization: `Bearer ${apiKey}` },
    cache: 'no-store',
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  const data = (await res.json()) as { items: InternalPromptItem[] }
  return (data.items || []).map((item) => ({
    id: `internal-${item.id}`,
    sourceId: 'internal',
    title: item.title || '未命名',
    prompt: item.body,
    coverUrl: item.cover_url || undefined,
    tags: item.tags || [],
    profession: item.category ? [item.category] : [],
    contributor: item.contributor,
    internal: true,
    createdAt: item.created_at || undefined,
  }))
}

export async function submitInternalPrompt(
  apiKey: string,
  body: { title: string; body: string; category: string; tags: string[]; cover_url: string },
): Promise<void> {
  const res = await fetch(INTERNAL_PROMPTS_PATH, {
    method: 'POST',
    headers: { Authorization: `Bearer ${apiKey}`, 'Content-Type': 'application/json' },
    cache: 'no-store',
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
}

export async function uploadPromptCover(apiKey: string, file: File): Promise<string> {
  const form = new FormData()
  form.append('file', file)
  const res = await fetch(`${INTERNAL_PROMPTS_PATH}/covers`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${apiKey}` },
    cache: 'no-store',
    body: form,
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  const data = (await res.json()) as { cover_url: string }
  return data.cover_url
}
