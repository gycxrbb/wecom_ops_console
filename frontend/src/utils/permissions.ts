export const PERMISSION_SCHEMA = [
  { key: 'send', label: '消息发送', group: '核心业务' },
  { key: 'schedule', label: '定时任务', group: '核心业务' },
  { key: 'group', label: '群管理', group: '数据管理' },
  { key: 'template', label: '模板管理', group: '数据管理' },
  { key: 'plan', label: '运营编排', group: '数据管理' },
  { key: 'asset', label: '素材管理', group: '数据管理' },
  { key: 'sop', label: '飞书文档', group: '数据管理' },
  { key: 'speech_template', label: '话术管理', group: '数据管理' },
  { key: 'crm_profile', label: '客户档案', group: '客户运营' },
  { key: 'log', label: '发送记录', group: '系统设置' },
  { key: 'approval', label: '审批操作', group: '系统设置' },
] as const

export type PermissionKey = typeof PERMISSION_SCHEMA[number]['key']

export function hasPermission(user: any, key: PermissionKey): boolean {
  if (!user) return false
  if (user.role === 'admin') return true
  return !!user.permissions?.[key]
}

export function moduleVisible(user: any, key: PermissionKey): boolean {
  return hasPermission(user, key)
}

/**
 * 统一的访问判断：路由守卫与菜单可见性共用同一套逻辑。
 * meta.role       -> 要求特定角色（如 'admin'）
 * meta.permission -> 要求特定模块权限 key
 */
export function canAccess(
  user: any,
  meta: { role?: string; permission?: PermissionKey } | undefined | null,
): boolean {
  if (!meta) return true
  if (meta.role && user?.role !== meta.role) return false
  if (meta.permission && !hasPermission(user, meta.permission)) return false
  return true
}
