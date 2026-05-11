import { computed } from 'vue'
import { useRouter, type RouteRecordNormalized } from 'vue-router'
import { useUserStore } from '#/stores/user'
import { canAccess } from '#/utils/permissions'

export interface MenuItem {
  path: string
  title: string
  icon?: string
  order: number
}

export interface MenuGroup {
  group: string
  items: MenuItem[]
}

// 菜单分组展示顺序；未在此声明的分组排到最后
const GROUP_ORDER = ['核心业务', '数据管理', '运营配置', '系统设置']

function groupWeight(name: string): number {
  const idx = GROUP_ORDER.indexOf(name)
  return idx === -1 ? GROUP_ORDER.length : idx
}

/**
 * 从路由表派生侧边栏菜单。
 * 以路由 meta 为唯一真值源：
 *  - 只保留 meta.title + meta.group + !meta.hideInMenu 的路由
 *  - 依据当前用户权限过滤
 *  - 按 meta.order 组内排序，分组按 GROUP_ORDER 排序
 */
export function useMenu() {
  const router = useRouter()
  const userStore = useUserStore()

  const menuGroups = computed<MenuGroup[]>(() => {
    const accessible = router.getRoutes().filter((r: RouteRecordNormalized) => {
      const m = r.meta
      if (!m?.title || !m?.group) return false
      if (m.hideInMenu) return false
      return canAccess(userStore.user, m)
    })

    const bucket = new Map<string, MenuItem[]>()
    for (const r of accessible) {
      const m = r.meta
      const group = m.group as string
      const fullPath = r.path.startsWith('/') ? r.path : `/${r.path}`
      const item: MenuItem = {
        path: fullPath,
        title: m.title as string,
        icon: m.icon as string | undefined,
        order: (m.order as number | undefined) ?? 999,
      }
      if (!bucket.has(group)) bucket.set(group, [])
      bucket.get(group)!.push(item)
    }

    const groups: MenuGroup[] = []
    for (const [group, items] of bucket) {
      items.sort((a, b) => a.order - b.order)
      groups.push({ group, items })
    }
    groups.sort((a, b) => groupWeight(a.group) - groupWeight(b.group))
    return groups
  })

  return { menuGroups }
}

/**
 * 根据路径获取匹配路由的标题，用于面包屑等场景。
 */
export function useRouteTitle() {
  const router = useRouter()
  const resolveTitle = (path: string): string => {
    const matched = router.resolve(path).matched
    const last = matched[matched.length - 1]
    return (last?.meta?.title as string) || '页面'
  }
  return { resolveTitle }
}
