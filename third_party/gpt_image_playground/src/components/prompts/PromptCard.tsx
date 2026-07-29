import { CopyIcon, FavoriteIcon } from '../icons'
import { useStore } from '../../store'
import { usePromptsStore } from '../../lib/prompts/usePromptsStore'
import { sourceName } from '../../lib/prompts/sources'
import type { Prompt } from '../../lib/prompts/promptsService'

interface Props {
  item: Prompt
  onOpen: () => void
}

export default function PromptCard({ item, onOpen }: Props) {
  const showToast = useStore((s) => s.showToast)
  const setAppMode = useStore((s) => s.setAppMode)
  const setPrompt = useStore((s) => s.setPrompt)
  const toggleFavorite = usePromptsStore((s) => s.toggleFavorite)
  const isFavorite = usePromptsStore((s) => s.favoriteIds.includes(item.id))

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(item.prompt)
      showToast('提示词已复制', 'success')
    } catch {
      showToast('复制失败', 'error')
    }
  }

  // 「使用」：先切 gallery（会恢复 gallery 草稿），再填 prompt，避免草稿恢复覆盖。
  const usePrompt = () => {
    setAppMode('gallery')
    setPrompt(item.prompt)
    showToast('已填入提示词，可编辑后生成', 'success')
  }

  return (
    <div className="group flex flex-col overflow-hidden rounded-2xl border border-gray-200/60 dark:border-white/[0.08] bg-white dark:bg-gray-900/40 shadow-sm transition-shadow hover:shadow-md">
      <button type="button" onClick={onOpen} className="relative block aspect-[4/3] w-full overflow-hidden bg-gray-100 dark:bg-gray-800">
        {item.coverUrl ? (
          <img src={item.coverUrl} alt={item.title} loading="lazy" className="h-full w-full object-cover transition-transform group-hover:scale-[1.02]" />
        ) : (
          <div className="flex h-full w-full items-center justify-center text-xs text-gray-400">无预览</div>
        )}
        <span className="absolute left-2 top-2 max-w-[calc(100%-1rem)] truncate rounded-full bg-black/50 px-2 py-0.5 text-[10px] text-white backdrop-blur-sm">
          {sourceName(item.sourceId)}
        </span>
      </button>
      <div className="flex flex-1 flex-col gap-2 p-3">
        <button type="button" onClick={onOpen} className="line-clamp-2 text-left text-sm font-medium text-gray-800 hover:text-blue-600 dark:text-gray-100 dark:hover:text-blue-400">
          {item.title || '未命名'}
        </button>
        {item.tags && item.tags.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {item.tags.slice(0, 3).map((tag) => (
              <span key={tag} className="rounded-full bg-gray-100 px-2 py-0.5 text-[10px] text-gray-500 dark:bg-white/[0.06] dark:text-gray-400">{tag}</span>
            ))}
          </div>
        )}
        <div className="mt-auto flex items-center justify-between pt-1">
          <div className="flex items-center gap-1">
            <button type="button" onClick={() => toggleFavorite(item.id)} title={isFavorite ? '取消收藏' : '收藏'} className="rounded-lg p-1.5 transition-colors hover:bg-gray-100 dark:hover:bg-white/[0.06]">
              <FavoriteIcon className={`h-4 w-4 ${isFavorite ? 'text-yellow-500' : 'text-gray-400'}`} filled={isFavorite} />
            </button>
            <button type="button" onClick={copy} title="复制" className="rounded-lg p-1.5 transition-colors hover:bg-gray-100 dark:hover:bg-white/[0.06]">
              <CopyIcon className="h-4 w-4 text-gray-400" />
            </button>
          </div>
          <button type="button" onClick={usePrompt} className="rounded-lg bg-blue-500 px-3 py-1 text-xs font-medium text-white transition-colors hover:bg-blue-600">使用</button>
        </div>
      </div>
    </div>
  )
}
