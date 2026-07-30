import { useState, type ReactNode } from 'react'
import { CloseIcon } from '../icons'
import { useStore } from '../../store'
import { getActiveApiProfile } from '../../lib/apiProfiles'
import { PROFESSIONS } from '../../lib/prompts/sources'
import { submitInternalPrompt, uploadPromptCover } from '../../lib/prompts/internalPrompts'

interface Props {
  onClose: () => void
  onSubmitted: () => void
}

const inputCls =
  'w-full rounded-xl border border-gray-200/60 bg-white/60 px-3 py-2 text-sm text-gray-700 outline-none transition-colors focus:border-blue-300 dark:border-white/[0.08] dark:bg-white/[0.03] dark:text-gray-200 dark:focus:border-blue-500/50'

export default function UploadPromptDialog({ onClose, onSubmitted }: Props) {
  const showToast = useStore((s) => s.showToast)
  const settings = useStore((s) => s.settings)
  const apiKey = getActiveApiProfile(settings).apiKey
  const [title, setTitle] = useState('')
  const [body, setBody] = useState('')
  const [category, setCategory] = useState<string>(PROFESSIONS[0])
  const [tagsText, setTagsText] = useState('')
  const [coverUrl, setCoverUrl] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const onCoverFile = async (file: File | undefined) => {
    if (!file || !apiKey) return
    try {
      const url = await uploadPromptCover(apiKey, file)
      setCoverUrl(url)
      showToast('封面上传成功', 'success')
    } catch {
      showToast('封面上传失败', 'error')
    }
  }

  const submit = async () => {
    if (!apiKey) { showToast('未获取到登录凭证', 'error'); return }
    if (!body.trim()) { showToast('请填写提示词正文', 'error'); return }
    setSubmitting(true)
    try {
      await submitInternalPrompt(apiKey, {
        title: title.trim(),
        body: body.trim(),
        category,
        tags: tagsText.split(/[,，]/).map((t) => t.trim()).filter(Boolean),
        cover_url: coverUrl,
      })
      onSubmitted()
    } catch {
      showToast('上传失败，请重试', 'error')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="fixed inset-0 z-[120] flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/20 backdrop-blur-md dark:bg-black/40" onClick={onClose} />
      <div className="relative flex max-h-[88vh] w-full max-w-xl flex-col overflow-hidden rounded-3xl border border-white/50 bg-white/95 shadow-[0_8px_40px_rgb(0,0,0,0.12)] ring-1 ring-black/5 backdrop-blur-xl dark:border-white/[0.08] dark:bg-gray-900/95 dark:ring-white/10">
        <div className="flex items-center justify-between border-b border-gray-200/60 px-5 py-3 dark:border-white/[0.08]">
          <h2 className="text-base font-semibold text-gray-800 dark:text-gray-100">上传提示词</h2>
          <button type="button" onClick={onClose} className="rounded-lg p-1.5 transition-colors hover:bg-gray-100 dark:hover:bg-white/[0.06]">
            <CloseIcon className="h-5 w-5 text-gray-500" />
          </button>
        </div>
        <div className="flex-1 space-y-4 overflow-y-auto p-5">
          <Field label="标题">
            <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="给这条提示词起个名字" className={inputCls} />
          </Field>
          <Field label="提示词正文（必填）">
            <textarea value={body} onChange={(e) => setBody(e.target.value)} rows={6} placeholder="粘贴或编写完整的生图提示词" className={`${inputCls} resize-y`} />
          </Field>
          <Field label="职业分类">
            <div className="flex flex-wrap gap-1.5">
              {PROFESSIONS.map((p) => (
                <button
                  key={p}
                  type="button"
                  onClick={() => setCategory(p)}
                  className={`rounded-full px-3 py-1 text-xs transition-colors ${category === p ? 'bg-blue-500 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200 dark:bg-white/[0.06] dark:text-gray-300'}`}
                >
                  {p}
                </button>
              ))}
            </div>
          </Field>
          <Field label="标签（逗号分隔）">
            <input value={tagsText} onChange={(e) => setTagsText(e.target.value)} placeholder="海报, 食谱" className={inputCls} />
          </Field>
          <Field label="封面图">
            <div className="space-y-2">
              <input type="file" accept="image/*" onChange={(e) => onCoverFile(e.target.files?.[0])} className="text-xs text-gray-500" />
              {coverUrl && <img src={coverUrl} alt="cover" className="h-24 rounded-lg object-cover" />}
            </div>
          </Field>
        </div>
        <div className="flex items-center justify-end gap-2 border-t border-gray-200/60 px-5 py-3 dark:border-white/[0.08]">
          <button type="button" onClick={onClose} className="rounded-lg bg-gray-100 px-4 py-1.5 text-sm text-gray-600 transition-colors hover:bg-gray-200 dark:bg-white/[0.06] dark:text-gray-300">取消</button>
          <button type="button" onClick={submit} disabled={submitting} className="rounded-lg bg-blue-500 px-4 py-1.5 text-sm font-medium text-white transition-colors hover:bg-blue-600 disabled:opacity-50">
            {submitting ? '上传中…' : '上传'}
          </button>
        </div>
      </div>
    </div>
  )
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <div className="mb-1.5 text-xs font-semibold uppercase tracking-widest text-gray-400">{label}</div>
      {children}
    </div>
  )
}
