import { defineStore } from 'pinia'
import request from '@/utils/request'

export const useUserStore = defineStore('user', {
  state: () => ({
    user: null as any
  }),
  actions: {
    async fetchUser() {
      try {
        const res = await request.get('/v1/bootstrap')
        this.user = res.current_user
        return res
      } catch (error) {
        this.user = null
        throw error
      }
    }
  }
})
