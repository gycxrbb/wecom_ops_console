import { ref } from 'vue'
import request from '#/utils/request'

export interface TagOption {
  value: string
  label: string
  aliases: string[]
}

export interface TagEntry {
  id: number
  dimension: string
  code: string
  name: string
  aliases: string[]
  enabled: boolean
}

const cache = ref<Record<string, TagOption[]>>({})
const loaded = ref(false)
let loadingPromise: Promise<void> | null = null

async function loadTags(force = false): Promise<void> {
  if (loadingPromise && !force) return loadingPromise
  loadingPromise = (async () => {
    try {
      const res = await request.get('/v1/rag/tags')
      const grouped: Record<string, TagOption[]> = {}
      for (const t of res.data?.tags ?? res.tags ?? []) {
        if (!grouped[t.dimension]) grouped[t.dimension] = []
        grouped[t.dimension].push({
          value: t.code,
          label: t.name,
          aliases: t.aliases ?? [],
        })
      }
      cache.value = grouped
      loaded.value = true
    } finally {
      loadingPromise = null
    }
  })()
  return loadingPromise
}

function options(dimension: string): TagOption[] {
  return cache.value[dimension] ?? []
}

async function createTag(dimension: string, code: string, name: string, aliases?: string[]): Promise<void> {
  await request.post('/v1/rag/tags', { dimension, code, name, aliases })
  await loadTags(true)
}

async function updateTag(tagId: number, data: { name?: string; aliases?: string[]; enabled?: boolean }): Promise<void> {
  await request.put(`/v1/rag/tags/${tagId}`, data)
  await loadTags(true)
}

async function disableTag(tagId: number): Promise<void> {
  await request.delete(`/v1/rag/tags/${tagId}`)
  await loadTags(true)
}

export function useRagTags() {
  if (!loaded.value && !loadingPromise) {
    loadTags()
  }
  return { tags: cache, loaded, loadTags: () => loadTags(true), options, createTag, updateTag, disableTag }
}
