/**
 * Preload cache — stores API responses from login-time prefetch.
 *
 * When a page calls request.get(url) and the URL was preloaded,
 * the cache entry is returned and consumed (one-time use).
 * Subsequent calls go to the network normally.
 */

const cache = new Map<string, any>()

export function setPreloaded(url: string, data: any): void {
  cache.set(url, data)
}

export function getPreloaded(url: string): any | null {
  const data = cache.get(url)
  if (data !== undefined) {
    cache.delete(url)
    return data
  }
  return null
}

export function hasPreloaded(url: string): boolean {
  return cache.has(url)
}

/** Clear all cached entries (e.g., on logout). */
export function clearPreloadCache(): void {
  cache.clear()
}
