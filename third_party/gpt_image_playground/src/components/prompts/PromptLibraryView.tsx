import { useEffect, useMemo, useState, type ReactNode } from 'react'
import PromptCard from './PromptCard'
import PromptDetailDialog from './PromptDetailDialog'
import UploadPromptDialog from './UploadPromptDialog'
import { ALL_PROFESSION_OPTION, ALL_SOURCES_OPTION, PROFESSION_FILTERS, PROMPT_SOURCES } from '../../lib/prompts/sources'
import { collectTags, filterPrompts, loadAllSources, type Prompt } from '../../lib/prompts/promptsService'
import { fetchInternalPrompts } from '../../lib/prompts/internalPrompts'
import { usePromptsStore } from '../../lib/prompts/usePromptsStore'
import { useStore } from '../../store'
import { getActiveApiProfile } from '../../lib/apiProfiles'
import { PlusIcon } from '../icons'

const PAGE_SIZE = 20

export default function PromptLibraryView() {
  const showToast = useStore((s) => s.showToast)
  const settings = useStore((s) => s.settings)
  const [tab, setTab] = useState<'library' | 'favorites'>('library')
  const [keyword, setKeyword] = useState('')
  const [debouncedKeyword, setDebouncedKeyword] = useState('')
  const [selectedTags, setSelectedTags] = useState<string[]>([])
  const [selectedSource, setSelectedSource] = useState<string>(ALL_SOURCES_OPTION)
  const [selectedProfession, setSelectedProfession] = useState<string>(ALL_PROFESSION_OPTION)
  const [remote, setRemote] = useState<Prompt[]>([])
  const [internal, setInternal] = useState<Prompt[]>([])
  const [loading, setLoading] = useState(true)
  const [loaded, setLoaded] = useState(false)
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE)
  const [selected, setSelected] = useState<Prompt | null>(null)
  const [showUpload, setShowUpload] = useState(false)
  const favoriteIds = usePromptsStore((s) => s.favoriteIds)

  const rawApiKey = getActiveApiProfile(settings).apiKey
  const apiKey = rawApiKey && rawApiKey !== 'PLACEHOLDER' ? rawApiKey : ''

  const reloadInternal = () => {
    if (!apiKey) return
    fetchInternalPrompts(apiKey)
      .then(setInternal)
      .catch(() => { /* 内部加载失败静默（远程仍可用） */ })
  }

  // 首次进入：并发拉取所有数据源 + 内部上传；单源失败不阻断其余。
  useEffect(() => {
    let cancelled = false
    loadAllSources()
      .then(({ prompts, failedSources }) => {
        if (cancelled) return
        setRemote(prompts)
        setLoaded(true)
        if (failedSources.length === PROMPT_SOURCES.length) {
          showToast('提示词库加载失败，请检查网络后重试', 'error')
        } else if (failedSources.length > 0) {
          showToast(`${failedSources.length} 个数据源加载失败，已显示可用部分`, 'info')
        }
      })
      .catch(() => { if (!cancelled) showToast('提示词库加载失败', 'error') })
      .finally(() => { if (!cancelled) setLoading(false) })
    reloadInternal()
    return () => { cancelled = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [showToast, apiKey])

  // 搜索防抖 300ms
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedKeyword(keyword), 300)
    return () => clearTimeout(timer)
  }, [keyword])

  // 内部上传置顶，再接远程
  const all = useMemo(() => [...internal, ...remote], [internal, remote])

  const baseList = useMemo(() => {
    if (tab === 'favorites') return all.filter((p) => favoriteIds.includes(p.id))
    return all
  }, [all, tab, favoriteIds])

  const filtered = useMemo(
    () => filterPrompts(baseList, { keyword: debouncedKeyword, tags: selectedTags, sourceId: selectedSource, profession: selectedProfession }),
    [baseList, debouncedKeyword, selectedTags, selectedSource, selectedProfession],
  )

  const tags = useMemo(() => collectTags(baseList), [baseList])

  // 筛选条件变化时重置分页
  useEffect(() => {
    setVisibleCount(PAGE_SIZE)
  }, [debouncedKeyword, selectedTags, selectedSource, selectedProfession, tab])

  const visible = filtered.slice(0, visibleCount)

  useEffect(() => {
    const onScroll = () => {
      if (visibleCount >= filtered.length) return
      if (window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 400) {
        setVisibleCount((count) => Math.min(count + PAGE_SIZE, filtered.length))
      }
    }
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [visibleCount, filtered.length])

  const toggleTag = (tag: string) => {
    setSelectedTags((cur) => (cur.includes(tag) ? cur.filter((t) => t !== tag) : [...cur, tag]))
  }

  return (
    <main className="pb-48">
      <div className="safe-area-x mx-auto w-full max-w-7xl px-4 py-6 sm:px-6">
        <div className="mb-5 flex items-center justify-center gap-3">
          <div className="text-center">
            <h1 className="text-2xl font-semibold text-gray-900 dark:text-gray-100">提示词中心</h1>
            <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
              当前共 {filtered.length} 条{tab === 'favorites' ? '（我的收藏）' : ''}
            </p>
          </div>
          {apiKey && (
            <button
              type="button"
              onClick={() => setShowUpload(true)}
              className="inline-flex items-center gap-1 rounded-full bg-blue-500 px-3 py-1.5 text-xs font-medium text-white shadow-sm transition-colors hover:bg-blue-600"
            >
              <PlusIcon className="h-3.5 w-3.5" /> 上传提示词
            </button>
          )}
        </div>

        {/* Tabs */}
        <div className="mb-5 flex justify-center gap-6 border-b border-gray-200 dark:border-white/[0.08]">
          {([['library', '提示词库'], ['favorites', `我的提示词(${favoriteIds.length})`]] as const).map(([key, label]) => (
            <button
              key={key}
              type="button"
              onClick={() => setTab(key)}
              className={`-mb-px border-b-2 px-1 pb-2 text-sm transition-colors ${tab === key ? 'border-blue-500 font-medium text-blue-600 dark:text-blue-400' : 'border-transparent text-gray-500 hover:text-gray-800 dark:hover:text-gray-200'}`}
            >
              {label}
            </button>
          ))}
        </div>

        <div className="grid items-start gap-5 lg:grid-cols-[220px_minmax(0,1fr)] lg:gap-6">
          {/* 筛选区 */}
          <aside className="max-h-72 overflow-y-auto border-b border-gray-200 pb-4 lg:sticky lg:top-0 lg:max-h-[calc(100vh-9rem)] lg:border-b-0 lg:border-r lg:pr-5 dark:border-white/[0.08]">
            <div className="mb-2 text-xs font-semibold uppercase tracking-widest text-gray-400">职业</div>
            <div className="flex flex-wrap gap-1.5">
              <FilterChip active={selectedProfession === ALL_PROFESSION_OPTION} onClick={() => setSelectedProfession(ALL_PROFESSION_OPTION)}>全部</FilterChip>
              {PROFESSION_FILTERS.map((p) => (
                <FilterChip key={p} active={selectedProfession === p} onClick={() => setSelectedProfession(p)}>{p}</FilterChip>
              ))}
            </div>
            <div className="mb-2 mt-5 text-xs font-semibold uppercase tracking-widest text-gray-400">来源</div>
            <div className="flex flex-wrap gap-1.5">
              <FilterChip active={selectedSource === ALL_SOURCES_OPTION} onClick={() => setSelectedSource(ALL_SOURCES_OPTION)}>全部</FilterChip>
              {PROMPT_SOURCES.map((s) => (
                <FilterChip key={s.id} active={selectedSource === s.id} onClick={() => setSelectedSource(s.id)}>{s.name}</FilterChip>
              ))}
            </div>
            <div className="mb-2 mt-5 text-xs font-semibold uppercase tracking-widest text-gray-400">标签</div>
            <div className="flex flex-wrap gap-1.5">
              <FilterChip active={selectedTags.length === 0} onClick={() => setSelectedTags([])}>全部</FilterChip>
              {tags.slice(0, 60).map((tag) => (
                <FilterChip key={tag} active={selectedTags.includes(tag)} onClick={() => toggleTag(tag)}>{tag}</FilterChip>
              ))}
            </div>
          </aside>

          {/* 列表区 */}
          <section className="min-w-0">
            <div className="relative mb-4">
              <svg className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
              <input
                value={keyword}
                onChange={(event) => setKeyword(event.target.value)}
                placeholder="搜索标题、内容或标签"
                className="w-full rounded-xl border border-gray-200/60 bg-white/60 py-2.5 pl-10 pr-3 text-sm text-gray-700 outline-none transition-colors focus:border-blue-300 dark:border-white/[0.08] dark:bg-white/[0.03] dark:text-gray-200 dark:focus:border-blue-500/50"
              />
            </div>
            {loading ? (
              <div className="flex h-60 items-center justify-center text-sm text-gray-400">加载中…</div>
            ) : visible.length === 0 ? (
              <div className="flex h-60 items-center justify-center text-sm text-gray-400">{loaded ? '没有匹配的提示词' : '加载失败'}</div>
            ) : (
              <>
                <div className="grid gap-3 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
                  {visible.map((item) => (
                    <PromptCard key={item.id} item={item} onOpen={() => setSelected(item)} />
                  ))}
                </div>
                <div className="mt-5 text-center text-xs text-gray-400">
                  {visibleCount < filtered.length ? '继续向下滚动加载更多' : '已经到底了'}
                </div>
              </>
            )}
          </section>
        </div>
      </div>
      <PromptDetailDialog prompt={selected} onClose={() => setSelected(null)} />
      {showUpload && (
        <UploadPromptDialog
          onClose={() => setShowUpload(false)}
          onSubmitted={() => { setShowUpload(false); reloadInternal(); showToast('提示词已上传', 'success') }}
        />
      )}
    </main>
  )
}

function FilterChip({ active, onClick, children }: { active: boolean; onClick: () => void; children: ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-full px-2.5 py-1 text-xs transition-colors ${active ? 'bg-gray-900 text-white dark:bg-white dark:text-gray-900' : 'bg-gray-100 text-gray-600 hover:bg-gray-200 dark:bg-white/[0.06] dark:text-gray-300 dark:hover:bg-white/[0.1]'}`}
    >
      {children}
    </button>
  )
}
