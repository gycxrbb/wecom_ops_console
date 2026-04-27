<template>
  <template v-if="streaming">
    <div class="md-mermaid-block">
      <div style="font-size:12px;color:#94a3b8;margin-bottom:8px;">Mermaid 图表（等待生成完成...）</div>
      <pre class="md-mermaid-code">{{ code }}</pre>
    </div>
  </template>
  <div v-else-if="svgHtml" class="md-mermaid-block" v-html="svgHtml" />
  <div v-else-if="errorMsg" class="md-mermaid-error">
    <div style="font-weight:600;margin-bottom:6px;">Mermaid 渲染失败</div>
    <div>{{ errorMsg }}</div>
    <pre class="md-mermaid-code">{{ code }}</pre>
  </div>
  <div v-else class="md-mermaid-block">
    <div style="font-size:13px;color:#94a3b8;">正在加载 Mermaid...</div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'

const props = defineProps<{
  code: string
  streaming?: boolean
}>()

let mermaidPromise: Promise<any> | null = null
let renderCounter = 0

const svgHtml = ref('')
const errorMsg = ref('')

function getMermaid() {
  if (!mermaidPromise) {
    mermaidPromise = import('mermaid').then(async (m) => {
      const isDark = document.documentElement.classList.contains('dark')
      m.default.initialize({
        startOnLoad: false,
        theme: isDark ? 'dark' : 'default',
      })
      return m.default
    })
  }
  return mermaidPromise
}

function sanitizeMermaidCode(code: string): string {
  return code
    .replace(/；/g, ';')
    .replace(/，/g, ',')
    .replace(/：/g, ':')
    .replace(/（/g, '(')
    .replace(/）/g, ')')
    .replace(/【/g, '[')
    .replace(/】/g, ']')
    .replace(/《/g, '<')
    .replace(/》/g, '>')
    .replace(/\u3001/g, '/') // 、
}

async function renderDiagram() {
  if (!props.code.trim() || props.streaming) return
  try {
    const mermaid = await getMermaid()
    const isDark = document.documentElement.classList.contains('dark')
    mermaid.initialize({ startOnLoad: false, theme: isDark ? 'dark' : 'default' })
    const id = `mermaid-${++renderCounter}-${Date.now()}`
    const sanitized = sanitizeMermaidCode(props.code)
    const { svg } = await mermaid.render(id, sanitized)
    svgHtml.value = svg
    errorMsg.value = ''
  } catch (e: any) {
    errorMsg.value = e?.message || '解析失败'
    svgHtml.value = ''
  }
}

onMounted(() => {
  if (!props.streaming) renderDiagram()
})

watch(() => props.streaming, (val) => {
  if (!val) renderDiagram()
})
</script>

<style scoped>
.md-mermaid-code {
  margin: 0;
  padding: 10px 14px;
  background: #1e293b;
  color: #e2e8f0;
  font-family: 'Menlo', 'Consolas', 'Monaco', monospace;
  font-size: 12px;
  white-space: pre;
  border-radius: 8px;
  text-align: left;
  overflow-x: auto;
}
</style>
