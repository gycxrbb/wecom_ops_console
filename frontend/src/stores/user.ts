import { defineStore } from 'pinia'
import request from '@/utils/request'

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
        return res
      } catch (error) {
        this.user = null
        throw error
      }
    }
  }
})
