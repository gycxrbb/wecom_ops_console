/**
 * Preload cache — stores API responses with unified key, TTL, and tag-based invalidation.
 *
 * Key features:
 * - buildCacheKey(config) merges URL query string + axios params into canonical key
 * - Cache entries carry TTL, resource tags, and source tracking
 * - invalidateTags(tags) for mutation-driven cache invalidation
 * - One-time consume semantics preserved (hit → delete)
 */

import type { AxiosRequestConfig } from 'axios'
import { getTagsForUrl } from './cacheTags'

// ── Types ──

export type CacheSource = 'login_preload' | 'route_prefetch'

export interface CacheEntry {
  data: any
  createdAt: number
  expiresAt: number
  resourceTags: string[]
  source: CacheSource
}

// ── Store ──

const cache = new Map<string, CacheEntry>()

// ── Key builder ──

/** Parse a query string like "a=1&b=2" into a sorted params object. */
function parseQueryString(qs: string): Record<string, string> {
  const params: Record<string, string> = {}
  if (!qs) return params
  for (const pair of qs.split('&')) {
    const idx = pair.indexOf('=')
    if (idx === -1) continue
    const key = decodeURIComponent(pair.slice(0, idx))
    const val = decodeURIComponent(pair.slice(idx + 1))
    if (val !== undefined) params[key] = val
  }
  return params
}

/**
 * Build a canonical cache key from an axios request config.
 * Merges URL query string + params object, sorts keys, normalizes method.
 */
export function buildCacheKey(config: AxiosRequestConfig): string {
  const method = (config.method || 'get').toLowerCase()
  const url = config.url || ''
  const params = config.params || {}

  const [path, existingQuery] = url.split('?')
  const mergedParams: Record<string, unknown> = {
    ...parseQueryString(existingQuery || ''),
    ...params,
  }

  const sortedKeys = Object.keys(mergedParams)
    .filter(k => mergedParams[k] !== undefined && mergedParams[k] !== null)
    .sort()

  const qs = sortedKeys.map(k => `${encodeURIComponent(k)}=${encodeURIComponent(String(mergedParams[k]))}`).join('&')
  return `${method}:${path}${qs ? '?' + qs : ''}`
}

// ── Public API ──

/** Store a preloaded response with TTL and resource tags. */
export function setPreloaded(
  key: string,
  data: any,
  options?: {
    ttlMs?: number
    resourceTags?: string[]
    source?: CacheSource
  },
): void {
  const now = Date.now()
  const ttlMs = options?.ttlMs ?? 60_000 // default 60s
  cache.set(key, {
    data,
    createdAt: now,
    expiresAt: now + ttlMs,
    resourceTags: options?.resourceTags ?? getTagsForUrl(key.split(':').slice(1).join(':')),
    source: options?.source ?? 'login_preload',
  })
}

/**
 * Retrieve a cached response by key (one-time consume).
 * Returns null if not found or expired.
 */
export function getPreloaded(key: string): any | null {
  const entry = cache.get(key)
  if (!entry) return null

  // Expired — delete and return null
  if (Date.now() > entry.expiresAt) {
    cache.delete(key)
    return null
  }

  // One-time consume
  cache.delete(key)
  return entry.data
}

/** Delete a specific cache entry by key. */
export function deletePreloaded(key: string): void {
  cache.delete(key)
}

/** Check if a cache entry exists and is not expired. */
export function hasPreloaded(key: string): boolean {
  const entry = cache.get(key)
  if (!entry) return false
  if (Date.now() > entry.expiresAt) {
    cache.delete(key)
    return false
  }
  return true
}

/** Invalidate all cache entries that match any of the given tags. */
export function invalidateTags(tags: string[]): void {
  if (!tags.length) return
  const tagSet = new Set(tags)
  for (const [key, entry] of cache) {
    if (entry.resourceTags.some(t => tagSet.has(t))) {
      cache.delete(key)
    }
  }
}

/** Clear all cached entries (e.g., on logout). */
export function clearPreloadCache(): void {
  cache.clear()
}

/** Return cache size for debugging. */
export function getCacheSize(): number {
  return cache.size
}

/** Return all cache entries for debugging. */
export function getCacheEntries(): Array<{ key: string; entry: CacheEntry }> {
  return Array.from(cache.entries()).map(([key, entry]) => ({ key, entry }))
}
