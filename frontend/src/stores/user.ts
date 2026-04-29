import { defineStore } from 'pinia'
import request from '#/utils/request'
import { setPreloaded, clearPreloadCache } from '#/utils/preloadCache'

export const useUserStore = defineStore('user', {
  state: () => ({
    user: null as any
  }),
  actions: {
    async fetchProfile() {
      const profile = await request.get('/v1/profile')
      this.user = {
        ...(this.user || {}),
        ...profile
      }
      return profile
    },
    async fetchUser() {
      try {
        const res = await request.get('/v1/bootstrap')
        // bootstrap 返回的 current_user 包含 permissions
        this.user = res.current_user
        await this.fetchProfile()

        // 登录成功后静默预热侧边栏数据缓存，去除首次进入页面的白屏和等待时间
        this.prefetchSidebarData()

        return res
      } catch (error) {
        this.user = null
        throw error
      }
    },
    async prefetchSidebarData() {
      // 清除旧缓存（登出后重新登录的场景）
      clearPreloadCache()

      // 所有需要预加载的接口：URL 作为缓存 key
      const endpoints = [
        '/v1/dashboard/summary',
        '/v1/groups',
        '/v1/templates',
        '/v1/schedules',
        '/v1/assets/folders/all',
        '/v1/speech-templates/scenes',
        '/v1/speech-templates',
        '/v1/crm-customers/list?page=1&page_size=20&include_filters=1',
        '/v1/crm-customers/filters',
        '/v1/external-docs/home/summary',
        '/v1/external-docs/bindings/flat',
        '/v1/external-docs/terms?dimension=stage',
        '/v1/system-docs/entries?mode=published',
        '/v1/rag/tags',
      ]

      // 捕获所有异常并忽略，不影响主流程和UI
      const results = await Promise.allSettled(
        endpoints.map(url =>
          request.get(url)
            .then(data => ({ url, data, ok: true as const }))
            .catch(() => ({ url, data: null, ok: false as const }))
        )
      )

      for (const r of results) {
        if (r.status === 'fulfilled' && r.value.ok) {
          setPreloaded(r.value.url, r.value.data)
        }
      }
    }
  }
})
