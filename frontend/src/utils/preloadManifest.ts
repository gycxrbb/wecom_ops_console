/**
 * Preload manifest — declares all sidebar endpoint prefetch tasks.
 * Separated from user.ts to centralize endpoint definitions and TTL/priority config.
 */

import type { PermissionKey } from './permissions'

export type PreloadPriority = 'P0' | 'P1' | 'P2'

export interface PreloadTask {
  id: string
  route: string
  permission?: PermissionKey
  adminOnly?: boolean
  priority: PreloadPriority
  request: {
    method: 'get'
    url: string
    params?: Record<string, unknown>
  }
  resourceTags: string[]
  ttlMs: number
}

const MANIFEST: PreloadTask[] = [
  // ── P0: Login immediately ──
  {
    id: 'dashboard-summary',
    route: 'Dashboard',
    priority: 'P0',
    request: { method: 'get', url: '/v1/dashboard/summary' },
    resourceTags: ['dashboard'],
    ttlMs: 30_000,
  },
  {
    id: 'groups',
    route: 'Groups',
    permission: 'group',
    priority: 'P0',
    request: { method: 'get', url: '/v1/groups' },
    resourceTags: ['groups', 'send-center'],
    ttlMs: 60_000,
  },
  {
    id: 'templates',
    route: 'Templates',
    permission: 'template',
    priority: 'P0',
    request: { method: 'get', url: '/v1/templates' },
    resourceTags: ['templates', 'send-center'],
    ttlMs: 60_000,
  },
  {
    id: 'schedules',
    route: 'Schedules',
    permission: 'schedule',
    priority: 'P0',
    request: { method: 'get', url: '/v1/schedules' },
    resourceTags: ['schedules', 'dashboard'],
    ttlMs: 60_000,
  },

  // ── P1: Idle/deferred ──
  {
    id: 'speech-scenes',
    route: 'SpeechTemplates',
    permission: 'speech_template',
    priority: 'P1',
    request: { method: 'get', url: '/v1/speech-templates/scenes' },
    resourceTags: ['speech-templates'],
    ttlMs: 300_000,
  },
  {
    id: 'speech-templates',
    route: 'SpeechTemplates',
    permission: 'speech_template',
    priority: 'P1',
    request: { method: 'get', url: '/v1/speech-templates' },
    resourceTags: ['speech-templates'],
    ttlMs: 60_000,
  },
  {
    id: 'crm-customers-list',
    route: 'CrmProfile',
    permission: 'crm_profile',
    priority: 'P1',
    request: {
      method: 'get',
      url: '/v1/crm-customers/list',
      params: { page: 1, page_size: 20, include_filters: 1 },
    },
    resourceTags: ['crm-customers'],
    ttlMs: 60_000,
  },
  {
    id: 'crm-customers-filters',
    route: 'CrmProfile',
    permission: 'crm_profile',
    priority: 'P1',
    request: { method: 'get', url: '/v1/crm-customers/filters' },
    resourceTags: ['crm-customers'],
    ttlMs: 300_000,
  },
  {
    id: 'sop-summary',
    route: 'SopDocsHome',
    permission: 'sop',
    priority: 'P1',
    request: { method: 'get', url: '/v1/external-docs/home/summary' },
    resourceTags: ['external-docs'],
    ttlMs: 60_000,
  },
  {
    id: 'sop-bindings',
    route: 'SopDocsHome',
    permission: 'sop',
    priority: 'P1',
    request: { method: 'get', url: '/v1/external-docs/bindings/flat' },
    resourceTags: ['external-docs'],
    ttlMs: 60_000,
  },
  {
    id: 'sop-terms',
    route: 'SopDocsHome',
    permission: 'sop',
    priority: 'P1',
    request: {
      method: 'get',
      url: '/v1/external-docs/terms',
      params: { dimension: 'stage' },
    },
    resourceTags: ['external-docs'],
    ttlMs: 300_000,
  },
  {
    id: 'system-docs-tree',
    route: 'SystemTeaching',
    priority: 'P1',
    request: { method: 'get', url: '/v1/system-docs/tree' },
    resourceTags: ['system-docs'],
    ttlMs: 300_000,
  },
  {
    id: 'rag-tags',
    route: 'PromptManage',
    adminOnly: true,
    priority: 'P1',
    request: { method: 'get', url: '/v1/rag/tags' },
    resourceTags: ['rag'],
    ttlMs: 600_000,
  },
]

export default MANIFEST
