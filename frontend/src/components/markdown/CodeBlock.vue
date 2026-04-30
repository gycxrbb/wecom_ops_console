<template>
  <div class="md-code-block" :class="{ 'md-code-block--customer-reply': isCustomerReplyBlock }">
    <div class="md-code-block__header" v-if="languageLabel">
      <span class="md-code-block__lang">{{ languageLabel }}</span>
      <button class="md-code-block__copy" @click="copyCode" :title="copied ? '已复制' : copyTitle">
        <svg v-if="!copied" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
        <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>
      </button>
    </div>
    <div class="md-code-block__body" :class="{ 'is-collapsed': isCollapsed }">
      <div v-if="highlightedHtml" class="md-code-block__highlight" v-html="highlightedHtml" />
      <pre v-else class="md-code-block__plain"><code>{{ displayCode }}</code></pre>
    </div>
    <button v-if="isLong && isCollapsed" class="md-code-block__expand" @click="isCollapsed = false">
      展开全部 {{ totalLines }} 行
    </button>
    <button v-if="isLong && !isCollapsed" class="md-code-block__expand" @click="isCollapsed = true">
      收起
    </button>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watchEffect, onMounted } from 'vue'
import { ElMessage } from 'element-plus'

const props = defineProps<{
  code: string
  language: string
}>()

const COLLAPSE_THRESHOLD = 30

const LANG_LABELS: Record<string, string> = {
  js: 'JavaScript', ts: 'TypeScript', py: 'Python', rb: 'Ruby',
  go: 'Go', rs: 'Rust', java: 'Java', cpp: 'C++', c: 'C',
  cs: 'C#', php: 'PHP', sql: 'SQL', sh: 'Shell', bash: 'Bash',
  json: 'JSON', yaml: 'YAML', yml: 'YAML', xml: 'XML', html: 'HTML',
  css: 'CSS', scss: 'SCSS', md: 'Markdown', vue: 'Vue',
}

const normalizedLanguage = computed(() => props.language?.trim().toLowerCase() || '')
const isCustomerReplyBlock = computed(() => normalizedLanguage.value === 'txt')
const copyTitle = computed(() => isCustomerReplyBlock.value ? '复制话术' : '复制代码')
const languageLabel = computed(() => {
  if (isCustomerReplyBlock.value) return '客户话术'
  const lang = normalizedLanguage.value
  return LANG_LABELS[lang] || (lang ? lang.charAt(0).toUpperCase() + lang.slice(1) : '')
})

const lines = computed(() => props.code.split('\n'))
const totalLines = computed(() => lines.value.length)
const isLong = computed(() => !isCustomerReplyBlock.value && totalLines.value > COLLAPSE_THRESHOLD)
const isCollapsed = ref(true)

const displayCode = computed(() => {
  if (!isLong.value || !isCollapsed.value) return props.code
  return lines.value.slice(0, COLLAPSE_THRESHOLD).join('\n')
})

const copied = ref(false)

async function copyCode() {
  try {
    await navigator.clipboard.writeText(props.code)
    copied.value = true
    setTimeout(() => { copied.value = false }, 1500)
  } catch {
    ElMessage.warning('复制失败，请手动选择复制')
  }
}

// Shiki lazy loading
type Highlighter = {
  codeToHtml: (code: string, options: { lang: string; theme: string }) => string
  getLoadedLanguages: () => string[]
}

let highlighterPromise: Promise<Highlighter> | null = null
const highlightedHtml = ref('')

function getHighlighter(): Promise<Highlighter> {
  if (!highlighterPromise) {
    highlighterPromise = import('shiki').then(async (shiki) => {
      return await shiki.createHighlighter({
        themes: ['github-light', 'github-dark'],
        langs: ['javascript', 'typescript', 'python', 'json', 'bash', 'sql', 'html', 'css', 'markdown', 'yaml', 'go', 'rust', 'java', 'cpp', 'c'],
      })
    })
  }
  return highlighterPromise
}

onMounted(async () => {
  if (isCustomerReplyBlock.value) return
  const lang = normalizedLanguage.value
  if (!lang) return
  try {
    const highlighter = await getHighlighter()
    const isDark = document.documentElement.classList.contains('dark')
    const supportedLangs = highlighter.getLoadedLanguages()
    const resolvedLang = supportedLangs.includes(lang) ? lang : 'text'
    highlightedHtml.value = highlighter.codeToHtml(
      isCollapsed.value && isLong.value ? displayCode.value : props.code,
      { lang: resolvedLang, theme: isDark ? 'github-dark' : 'github-light' },
    )
  } catch {
    // fallback to plain <pre>
  }
})

watchEffect(() => {
  if (highlightedHtml.value && isLong.value && !isCustomerReplyBlock.value) {
    // re-highlight when expanding
    getHighlighter().then((highlighter) => {
      const isDark = document.documentElement.classList.contains('dark')
      const lang = normalizedLanguage.value || 'text'
      const supportedLangs = highlighter.getLoadedLanguages()
      const resolvedLang = supportedLangs.includes(lang) ? lang : 'text'
      highlightedHtml.value = highlighter.codeToHtml(
        isCollapsed.value ? displayCode.value : props.code,
        { lang: resolvedLang, theme: isDark ? 'github-dark' : 'github-light' },
      )
    }).catch(() => {})
  }
})
</script>

<style scoped>
.md-code-block {
  margin: 0.8em 0;
  border-radius: 10px;
  overflow: hidden;
  border: 1px solid #e5e7eb;
  background: #fafbfc;
}

.md-code-block__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 12px;
  background: #f1f5f9;
  border-bottom: 1px solid #e5e7eb;
  font-size: 12px;
}

.md-code-block__lang {
  color: #64748b;
  font-family: inherit;
}

.md-code-block__copy {
  background: none;
  border: none;
  cursor: pointer;
  color: #94a3b8;
  padding: 2px;
  display: flex;
  align-items: center;
  transition: color 0.15s;
}

.md-code-block__copy:hover {
  color: #475569;
}

.md-code-block__body {
  overflow-x: auto;
  font-size: 13px;
  line-height: 1.6;
}

.md-code-block__highlight :deep(pre) {
  margin: 0 !important;
  padding: 14px 16px !important;
  background: transparent !important;
}

.md-code-block__highlight :deep(code) {
  font-family: 'Menlo', 'Consolas', 'Monaco', monospace;
  font-size: 13px;
}

.md-code-block__plain {
  margin: 0;
  padding: 14px 16px;
  background: #1e293b;
  color: #e2e8f0;
}

.md-code-block__plain code {
  font-family: 'Menlo', 'Consolas', 'Monaco', monospace;
  font-size: 13px;
  white-space: pre;
}

.md-code-block--customer-reply {
  width: 100%;
  margin: 1em 0 1.15em;
  border-color: #dfe6ff;
  background: #fbfcff;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.75);
}

.md-code-block--customer-reply .md-code-block__header {
  padding: 8px 14px;
  background: #f3f6ff;
  border-bottom-color: #dfe6ff;
}

.md-code-block--customer-reply .md-code-block__lang {
  color: #4f5f83;
  font-weight: 600;
}

.md-code-block--customer-reply .md-code-block__copy {
  color: #6476d8;
  padding: 4px;
  border-radius: 6px;
}

.md-code-block--customer-reply .md-code-block__copy:hover {
  color: #4f46e5;
  background: rgba(99, 102, 241, 0.1);
}

.md-code-block--customer-reply .md-code-block__body {
  overflow: visible;
  font-size: 14.5px;
  line-height: 1.78;
}

.md-code-block--customer-reply .md-code-block__plain {
  min-height: 132px;
  padding: 18px 20px;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.86), rgba(247, 249, 255, 0.92)),
    #fbfcff;
  color: #273244;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  word-break: break-word;
}

.md-code-block--customer-reply .md-code-block__plain code {
  font-family: inherit;
  font-size: inherit;
  white-space: pre-wrap;
}

.md-code-block__expand {
  display: block;
  width: 100%;
  padding: 8px;
  background: #f8fafc;
  border: none;
  border-top: 1px solid #e5e7eb;
  color: #6366f1;
  font-size: 12.5px;
  cursor: pointer;
  text-align: center;
}

.md-code-block__expand:hover {
  background: #f1f5f9;
}

:global(html.dark) .md-code-block {
  border-color: #374151;
  background: #1e293b;
}

:global(html.dark) .md-code-block__header {
  background: #111827;
  border-color: #374151;
}

:global(html.dark) .md-code-block__expand {
  background: #111827;
  border-color: #374151;
  color: #818cf8;
}

:global(html.dark) .md-code-block--customer-reply {
  border-color: rgba(129, 140, 248, 0.24);
  background: rgba(99, 102, 241, 0.08);
}

:global(html.dark) .md-code-block--customer-reply .md-code-block__header {
  background: rgba(99, 102, 241, 0.13);
  border-color: rgba(129, 140, 248, 0.24);
}

:global(html.dark) .md-code-block--customer-reply .md-code-block__lang,
:global(html.dark) .md-code-block--customer-reply .md-code-block__copy {
  color: #c7d2fe;
}

:global(html.dark) .md-code-block--customer-reply .md-code-block__plain {
  background: rgba(15, 23, 42, 0.38);
  color: #e8ecff;
}
</style>
