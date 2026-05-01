/**
 * Cache tag invalidation — maps URL paths to resource tags.
 * Used by request interceptor to auto-invalidate related caches after mutations.
 */

const URL_TAG_MAP: Record<string, string[]> = {
  '/v1/schedules': ['schedules', 'dashboard'],
  '/v1/groups': ['groups', 'send-center'],
  '/v1/templates': ['templates', 'send-center'],
  '/v1/assets': ['assets'],
  '/v1/asset-folders': ['assets', 'asset-folders'],
  '/v1/speech-templates': ['speech-templates'],
  '/v1/crm-customers': ['crm-customers'],
  '/v1/external-docs': ['external-docs'],
  '/v1/system-docs': ['system-docs'],
  '/v1/dashboard': ['dashboard'],
  '/v1/rag': ['rag'],
}

/** Get resource tags for a URL path (prefix matching, longest match wins). */
export function getTagsForUrl(url: string): string[] {
  const path = url.split('?')[0]
  let bestMatch = ''
  let bestTags: string[] = []
  for (const [prefix, tags] of Object.entries(URL_TAG_MAP)) {
    if (path.startsWith(prefix) && prefix.length > bestMatch.length) {
      bestMatch = prefix
      bestTags = tags
    }
  }
  return bestTags
}

/** Infer tags to invalidate from a mutation request config. */
export function inferInvalidateTags(method: string, url: string): string[] {
  const m = method.toLowerCase()
  if (m === 'get') return []
  // Only invalidate on mutations
  if (!['post', 'put', 'patch', 'delete'].includes(m)) return []
  return getTagsForUrl(url)
}
