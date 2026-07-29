import { useEffect } from 'react'
import { CloseIcon, CopyIcon, FavoriteIcon } from '../icons'
import { useStore } from '../../store'
import { usePromptsStore } from '../../lib/prompts/usePromptsStore'
import { sourceName } from '../../lib/prompts/sources'
import type { Prompt } from '../../lib/prompts/promptsService'

interface Props {
  prompt: Prompt | null
  onClose: () => void
}

export default function PromptDetailDialog({ prompt, onClose }: Props) {
  const showToast = useStore((s) => s.showToast)
  const setAppMode = useStore((s) => s.setAppMode)
  const setPromptText = useStore((s) => s.setPrompt)
  const toggleFavorite = usePromptsStore((s) => s.toggleFavorite)
  const isFavorite = usePromptsStore((s) => (prompt ? s.favoriteIds.includes(prompt.id) : false))

  // Escape 关闭
  useEffect(() => {
    if (!prompt) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [prompt, onClose])

  if (!prompt) return null

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(prompt.prompt)
      showToast('提示词已复制', 'success')
    } catch {
      showToast('复制失败', 'error')
    }
  }

  const usePrompt = () => {
    setAppMode('gallery')
    setPromptText(prompt.prompt)
    onClose()
    showToast('已填入提示词，可编辑后生成', 'success')
  }

  return (
    <div className="fixed inset-0 z-[110] flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/20 backdrop-blur-md dark:bg-black/40" onClick={onClose} />
      <div className="relative flex max-h-[88vh] w-full max-w-3xl flex-col overflow-hidden rounded-3xl border border-white/50 bg-white/95 shadow-[0_8px_40px_rgb(0,0,0,0.12)] ring-1 ring-black/5 backdrop-blur-xl dark:border-white/[0.08] dark:bg-gray-900/95 dark:ring-white/10">
        <div className="flex items-center justify-between border-b border-gray-200/60 px-5 py-3 dark:border-white/[0.08]">
          <h2 className="truncate text-base font-semibold text-gray-800 dark:text-gray-100">{prompt.title || '未命名'}</h2>
          <button type="button" onClick={onClose} className="rounded-lg p-1.5 transition-colors hover:bg-gray-100 dark:hover:bg-white/[0.06]">
            <CloseIcon className="h-5 w-5 text-gray-500" />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto">
          {prompt.coverUrl && (
            <div className="bg-gray-100 dark:bg-gray-800">
              <img src={prompt.coverUrl} alt={prompt.title} className="mx-auto max-h-[50vh] object-contain" />
            </div>
          )}
          <div className="space-y-4 p-5">
            <div className="flex flex-wrap gap-1.5">
              <span className="rounded-full bg-blue-50 px-2.5 py-0.5 text-xs text-blue-600 dark:bg-blue-900/30 dark:text-blue-300">{sourceName(prompt.sourceId)}</span>
              {(prompt.tags || []).map((tag) => (
                <span key={tag} className="rounded-full bg-gray-100 px-2.5 py-0.5 text-xs text-gray-500 dark:bg-white/[0.06] dark:text-gray-400">{tag}</span>
              ))}
            </div>
            <div>
              <div className="mb-1.5 text-xs font-semibold uppercase tracking-widest text-gray-400">提示词</div>
              <p className="whitespace-pre-wrap rounded-xl bg-gray-50 p-3 text-sm leading-relaxed text-gray-700 dark:bg-white/[0.03] dark:text-gray-200">{prompt.prompt}</p>
            </div>
            {prompt.sourceUrl && (
              <a href={prompt.sourceUrl} target="_blank" rel="noopener noreferrer" className="inline-block text-xs text-blue-600 hover:underline dark:text-blue-400">来源链接</a>
            )}
          </div>
        </div>
        <div className="flex items-center justify-end gap-2 border-t border-gray-200/60 px-5 py-3 dark:border-white/[0.08]">
          <button type="button" onClick={() => toggleFavorite(prompt.id)} className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm transition-colors ${isFavorite ? 'bg-yellow-50 text-yellow-600 dark:bg-yellow-900/20 dark:text-yellow-400' : 'bg-gray-100 text-gray-600 hover:bg-gray-200 dark:bg-white/[0.06] dark:text-gray-300 dark:hover:bg-white/[0.1]'}`}>
            <FavoriteIcon className="h-4 w-4" filled={isFavorite} /> {isFavorite ? '已收藏' : '收藏'}
          </button>
          <button type="button" onClick={copy} className="inline-flex items-center gap-1.5 rounded-lg bg-gray-100 px-3 py-1.5 text-sm text-gray-600 transition-colors hover:bg-gray-200 dark:bg-white/[0.06] dark:text-gray-300 dark:hover:bg-white/[0.1]">
            <CopyIcon className="h-4 w-4" /> 复制
          </button>
          <button type="button" onClick={usePrompt} className="rounded-lg bg-blue-500 px-4 py-1.5 text-sm font-medium text-white transition-colors hover:bg-blue-600">使用</button>
        </div>
      </div>
    </div>
  )
}
