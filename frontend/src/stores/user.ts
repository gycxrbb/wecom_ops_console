import { defineStore } from 'pinia'
import request from '#/utils/request'
import { executeP0, scheduleP1, resetScheduler } from '#/utils/preloadScheduler'

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

        // 登录成功后按优先级预热侧边栏数据
        this.prefetchSidebarData()

        return res
      } catch (error) {
        this.user = null
        throw error
      }
    },
    async prefetchSidebarData() {
      // 清除旧缓存和调度器状态（登出后重新登录的场景）
      resetScheduler()

      // P0: 立即预热高频接口
      await executeP0(this.user)

      // P1: 空闲后预热次优先级接口
      scheduleP1(this.user)
    }
  }
})
