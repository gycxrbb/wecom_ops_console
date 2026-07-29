// 提示词库收藏 store：单独的 zustand persist store，不并入主 useStore（避免主 store persist version 迁移风险）。
// 只存收藏的 prompt id 列表；「我的提示词」由全量 prompts + favoriteIds 过滤得到。

import { create } from 'zustand'
import { persist } from 'zustand/middleware'

type PromptsState = {
  favoriteIds: string[]
  toggleFavorite: (id: string) => void
  isFavorite: (id: string) => boolean
}

export const usePromptsStore = create<PromptsState>()(
  persist(
    (set, get) => ({
      favoriteIds: [],
      toggleFavorite: (id) =>
        set((state) => ({
          favoriteIds: state.favoriteIds.includes(id)
            ? state.favoriteIds.filter((x) => x !== id)
            : [...state.favoriteIds, id],
        })),
      isFavorite: (id) => get().favoriteIds.includes(id),
    }),
    { name: 'gpt-image-playground-prompts', version: 1 },
  ),
)
