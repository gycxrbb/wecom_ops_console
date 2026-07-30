// 提示词库数据获取：fetch registry JSON + 内存缓存 + 客户端过滤。
// 不引入 react-query，用模块级 Map 缓存（session 内不重复 fetch）。
// 远程 prompt 注入 AI 预计算的 profession 映射；NSFW 在此过滤（企业场景必须剔除）。

import { ALL_PROFESSION_OPTION, ALL_SOURCES_OPTION, PROMPT_SOURCES, registryUrl } from './sources'
import professionMapData from './profession_map.json'

type Contributor = { id: number; display_name: string; avatar_url: string }

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
  profession?: string[]                       // 职业分类（远程=AI 预计算；内部=上传时选）
  contributor?: Contributor | null            // 内部上传贡献者（远程无）
  internal?: boolean                          // true=内部上传，false=远程 registry
}

export type LoadResult = {
  prompts: Prompt[]
  failedSources: string[]
}

const professionMap = professionMapData as Record<string, unknown>
const nsfwIdSet = new Set<string>((professionMap._nsfw as string[]) || [])

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

// 并发拉取所有内置源；单个失败不阻断其余。按 id 去重。注入职业映射 + 过滤 NSFW。
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
          if (item.id && nsfwIdSet.has(item.id)) continue // 过滤 NSFW（企业场景必须剔除）
          const profs = professionMap[item.id]
          prompts.push({
            ...item,
            profession: Array.isArray(profs) ? (profs as string[]) : undefined,
          })
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
  profession: string // ALL_PROFESSION_OPTION 或具体职业（含 '通用'）
}

// 客户端过滤：职业 + 数据源 + 标签（多选，全部命中）+ 关键词（标题/正文/标签/作者）。
export function filterPrompts(all: Prompt[], filter: PromptFilter): Prompt[] {
  const keyword = filter.keyword.trim().toLowerCase()
  const tags = filter.tags.map((t) => t.toLowerCase())
  return all.filter((item) => {
    if (filter.profession && filter.profession !== ALL_PROFESSION_OPTION) {
      const profs = item.profession || []
      if (filter.profession === '通用') {
        if (profs.length > 0) return false // 通用桶 = 无职业映射
      } else if (!profs.includes(filter.profession)) {
        return false
      }
    }
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
