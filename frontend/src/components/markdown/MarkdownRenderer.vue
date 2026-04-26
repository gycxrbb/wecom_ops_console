<template>
  <div class="md-prose">
    <template v-for="(seg, i) in segments" :key="i">
      <CodeBlock v-if="seg.type === 'code'" :code="seg.code" :language="seg.language" />
      <div v-else v-html="seg.html" />
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useMarkdownIt, sanitize } from '#/composables/useMarkdownIt'
import { safeCloseMarkdown } from '#/lib/streaming/chunkBuffer'
import '#/styles/markdown.css'
import CodeBlock from './CodeBlock.vue'

type Segment =
  | { type: 'code'; code: string; language: string }
  | { type: 'html'; html: string }

const props = withDefaults(defineProps<{
  content: string
  streaming?: boolean
}>(), {
  streaming: false,
})

const { md, render } = useMarkdownIt()

const segments = computed<Segment[]>(() => {
  const src = props.streaming ? safeCloseMarkdown(props.content) : props.content
  if (!src) return []

  const tokens = md.parse(src, {})
  const result: Segment[] = []
  let htmlBatch: any[] = []

  const flushHtml = () => {
    if (htmlBatch.length === 0) return
    const html = md.renderer.render(htmlBatch, md.options, {})
    result.push({ type: 'html', html: sanitize(html) })
    htmlBatch = []
  }

  for (let i = 0; i < tokens.length; i++) {
    const token = tokens[i]
    if (token.type === 'fence' || token.type === 'code_block') {
      flushHtml()
      result.push({
        type: 'code',
        code: token.content,
        language: (token.info || '').trim().split(/\s+/)[0] || '',
      })
    } else {
      htmlBatch.push(token)
    }
  }

  flushHtml()
  return result
})
</script>
