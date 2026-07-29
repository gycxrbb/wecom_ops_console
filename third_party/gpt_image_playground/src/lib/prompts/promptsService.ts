// 提示词库数据获取：fetch registry JSON + 内存缓存 + 客户端过滤。
// 不引入 react-query，用模块级 Map 缓存（session 内不重复 fetch）。

import { ALL_SOURCES_OPTION, PROMPT_SOURCES, registryUrl } from './sources'

export type Prompt = {
  id: string
  sourceId: string
  title: string
  prompt: string
  description?: string
  coverUrl?: string
  referenceImageUrls?: string[]
  tags?: string[]
  author?: string
  sourceUrl?: string
  createdAt?: string
  imageMode?: string
  imageModel?: string
}

export type LoadResult = {
  prompts: Prompt[]
  failedSources: string[]
}

const cache = new Map<string, Prompt[]>()

// fetch 单个 source，成功后缓存。force-cache 让浏览器 HTTP 缓存生效（registry 是静态资源）。
async function loadSource(sourceId: string): Promise<Prompt[]> {
  const cached = cache.get(sourceId)
  if (cached) return cached
  const res = await fetch(registryUrl(sourceId), { cache: 'force-cache' })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  const data = (await res.json()) as Prompt[]
  // 兜底：registry 理论上每条都带 sourceId，这里补一次以防遗漏。
  const normalized = data.map((item) => ({ ...item, sourceId: item.sourceId || sourceId }))
  cache.set(sourceId, normalized)
  return normalized
}

// 并发拉取所有内置源；单个失败不阻断其余。按 id 去重。
export async function loadAllSources(): Promise<LoadResult> {
  const results = await Promise.allSettled(PROMPT_SOURCES.map((s) => loadSource(s.id)))
  const prompts: Prompt[] = []
  const failedSources: string[] = []
  const seen = new Set<string>()
  results.forEach((result, index) => {
    if (result.status === 'fulfilled') {
      for (const item of result.value) {
        const key = item.id || `${item.sourceId}:${item.title}`
        if (key && !seen.has(key)) {
          seen.add(key)
          prompts.push(item)
        }
      }
    } else {
      failedSources.push(PROMPT_SOURCES[index].name)
    }
  })
  return { prompts, failedSources }
}

export type PromptFilter = {
  keyword: string
  tags: string[]
  sourceId: string // ALL_SOURCES_OPTION 或具体 source id
}

// 客户端过滤：数据源 + 标签（多选，全部命中）+ 关键词（标题/正文/标签/作者）。
export function filterPrompts(all: Prompt[], filter: PromptFilter): Prompt[] {
  const keyword = filter.keyword.trim().toLowerCase()
  const tags = filter.tags.map((t) => t.toLowerCase())
  return all.filter((item) => {
    if (filter.sourceId !== ALL_SOURCES_OPTION && item.sourceId !== filter.sourceId) return false
    if (tags.length) {
      const itemTags = (item.tags || []).map((t) => t.toLowerCase())
      if (!tags.every((t) => itemTags.includes(t))) return false
    }
    if (keyword) {
      const haystack = [item.title, item.prompt, (item.tags || []).join(' '), item.author || '']
        .join(' ')
        .toLowerCase()
      if (!haystack.includes(keyword)) return false
    }
    return true
  })
}

// 收集所有出现过的标签，按中文 locale 排序去重。
export function collectTags(prompts: Prompt[]): string[] {
  const set = new Set<string>()
  for (const item of prompts) {
    for (const tag of item.tags || []) set.add(tag)
  }
  return [...set].sort((a, b) => a.localeCompare(b, 'zh'))
}
