<template>
  <div class="card-panel">
    <div class="card-header">
      <div class="card-header-icon card-header-icon--blue">
        <el-icon :size="16"><Monitor /></el-icon>
      </div>
      <h3 class="card-header-title">预览结果</h3>
      <el-radio-group v-model="mode" size="small" class="preview-switch">
        <el-radio-button label="mock">模拟效果</el-radio-button>
        <el-radio-button label="json">JSON</el-radio-button>
      </el-radio-group>
    </div>

    <div class="card-body">
      <div v-if="isPreviewing" class="loading-state">
        <el-icon class="is-loading" :size="28"><Loading /></el-icon>
        <div style="margin-top: 12px;">正在生成预览...</div>
      </div>

      <div v-else-if="previewError" class="preview-error">{{ previewError }}</div>

      <div v-else-if="previewData" class="preview-content">
        <pre v-if="mode === 'json'" class="preview-box">{{ previewJson }}</pre>

        <div v-else class="wechat-shell">
          <div class="wechat-bubble">
            <template v-if="msgType === 'text'">
              <div class="message-text">{{ stringContent }}</div>
              <div v-if="mentionSummary" class="mention-info">
                <el-icon :size="12"><UserFilled /></el-icon>
                <span>将通知：{{ mentionSummary }}</span>
              </div>
            </template>

            <template v-else-if="msgType === 'markdown'">
              <div class="markdown-body" v-html="markdownHtml"></div>
            </template>

            <template v-else-if="msgType === 'image'">
              <div class="image-mock">
                <img v-if="imageUrl" :src="imageUrl" alt="image preview" class="image-mock__img" />
                <div v-else class="image-mock__placeholder">图片素材预览</div>
              </div>
            </template>

            <template v-else-if="msgType === 'file'">
              <div class="file-mock">
                <el-icon :size="20"><Document /></el-icon>
                <div>
                  <div class="file-mock__name">{{ renderedContent.asset_name || '文件素材' }}</div>
                  <div class="file-mock__desc">发送后用户会在企微里看到文件卡片</div>
                </div>
              </div>
            </template>

            <template v-else-if="msgType === 'news'">
              <div class="news-list">
                <div v-for="(article, index) in articles" :key="index" class="news-item">
                  <div class="news-item__cover">
                    <img v-if="article.picurl" :src="article.picurl" alt="cover" class="news-item__cover-img" />
                    <div v-else class="news-item__cover-placeholder">图文封面</div>
                  </div>
                  <div class="news-item__content">
                    <div class="news-item__title">{{ article.title || '未填写标题' }}</div>
                    <div class="news-item__desc">{{ article.description || '未填写描述' }}</div>
                    <div class="news-item__url">{{ article.url || '未填写链接' }}</div>
                  </div>
                </div>
              </div>
            </template>

            <template v-else-if="msgType === 'template_card'">
              <div class="card-mock">
                <div class="card-mock__title">{{ templateCardTitle }}</div>
                <div class="card-mock__desc">{{ templateCardDesc }}</div>
                <div v-if="templateCardButtonText" class="card-mock__button">{{ templateCardButtonText }}</div>
              </div>
            </template>

            <template v-else>
              <div class="message-text">
                {{ stringContent || '当前消息类型暂不支持可视化模拟，请切到 JSON 查看。' }}
              </div>
            </template>
          </div>
        </div>
      </div>

      <div v-else class="empty-state">
        <el-icon class="empty-state__icon"><Monitor /></el-icon>
        <span class="empty-state__text">点击「预览消息」查看发送效果</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { Document, Loading, Monitor, UserFilled } from '@element-plus/icons-vue'

const props = defineProps({
  previewData: { type: Object, default: null },
  previewError: { type: String, default: '' },
  msgType: { type: String, default: 'text' },
  isPreviewing: { type: Boolean, default: false },
  contentJson: { type: Object, default: () => ({}) }
})

const mode = ref<'mock' | 'json'>('mock')

const previewJson = computed(() => props.previewData ? JSON.stringify(props.previewData, null, 2) : '')
const renderedContent = computed<Record<string, any>>(() => props.previewData?.rendered_content || {})
const stringContent = computed(() => {
  const content = renderedContent.value
  return content.content || content.text || JSON.stringify(content, null, 2)
})

const escapeHtml = (value: string) => value
  .replace(/&/g, '&amp;')
  .replace(/</g, '&lt;')
  .replace(/>/g, '&gt;')
  .replace(/"/g, '&quot;')
  .replace(/'/g, '&#39;')

const renderInlineMarkdown = (value: string) => {
  const escaped = escapeHtml(value)
  return escaped
    .replace(/!\[([^\]]*)\]\((https?:\/\/[^\s)]+)\)/g, '<img class="md-inline-image" alt="$1" src="$2" />')
    .replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
}

const markdownHtml = computed(() => {
  const source = String(renderedContent.value.content || '').replace(/\r\n/g, '\n')
  if (!source.trim()) return '<p class="md-paragraph">暂无内容</p>'

  const lines = source.split('\n')
  const blocks: string[] = []
  let listItems: string[] = []

  const flushList = () => {
    if (!listItems.length) return
    blocks.push(`<ul>${listItems.join('')}</ul>`)
    listItems = []
  }

  for (const rawLine of lines) {
    const line = rawLine.trim()

    if (!line) {
      flushList()
      continue
    }

    if (line.startsWith('- ')) {
      listItems.push(`<li>${renderInlineMarkdown(line.slice(2))}</li>`)
      continue
    }

    flushList()

    if (line.startsWith('### ')) {
      blocks.push(`<h3>${renderInlineMarkdown(line.slice(4))}</h3>`)
      continue
    }
    if (line.startsWith('## ')) {
      blocks.push(`<h2>${renderInlineMarkdown(line.slice(3))}</h2>`)
      continue
    }
    if (line.startsWith('# ')) {
      blocks.push(`<h1>${renderInlineMarkdown(line.slice(2))}</h1>`)
      continue
    }
    if (line.startsWith('> ')) {
      blocks.push(`<blockquote>${renderInlineMarkdown(line.slice(2))}</blockquote>`)
      continue
    }

    blocks.push(`<p class="md-paragraph">${renderInlineMarkdown(line)}</p>`)
  }

  flushList()
  return blocks.join('')
})

const imageUrl = computed(() => renderedContent.value.asset_url || renderedContent.value.image_url || '')
const mentionList = computed(() => {
  const raw = renderedContent.value.mentioned_list || props.contentJson?.mentioned_list || []
  return Array.isArray(raw) ? raw : []
})
const mentionMobileList = computed(() => {
  const raw = renderedContent.value.mentioned_mobile_list || props.contentJson?.mentioned_mobile_list || []
  return Array.isArray(raw) ? raw : []
})
const mentionSummary = computed(() => {
  const items: string[] = []
  for (const item of mentionList.value) {
    const label = item === '@all' || item === 'all' ? '@所有人' : String(item)
    if (!items.includes(label)) items.push(label)
  }
  for (const item of mentionMobileList.value) {
    const label = item === '@all' || item === 'all' ? '@所有人' : String(item)
    if (!items.includes(label)) items.push(label)
  }
  return items.join('、')
})
const articles = computed(() => Array.isArray(renderedContent.value.articles) ? renderedContent.value.articles : [])
const templateCard = computed<Record<string, any>>(() => renderedContent.value?.template_card || {})
const templateCardTitle = computed(() => templateCard.value?.main_title?.title || '模板卡片预览')
const templateCardDesc = computed(() => templateCard.value?.sub_title_text || templateCard.value?.horizontal_content_list?.[0]?.value || '模板卡片将按企微卡片样式发送到群里')
const templateCardButtonText = computed(() => templateCard.value?.jump_list?.[0]?.title || templateCard.value?.card_action?.title || '')
</script>

<style scoped>
.preview-switch {
  margin-left: auto;
}

.preview-content {
  min-height: 220px;
}

.preview-box {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 12px;
  line-height: 1.6;
  color: var(--text-secondary);
}

.preview-error {
  color: var(--el-color-danger);
  white-space: pre-wrap;
}

.wechat-shell {
  min-height: 220px;
  padding: 14px;
  border-radius: 16px;
  background: var(--bg-color);
  border: 1px solid var(--border-color);
}

.wechat-bubble {
  max-width: 100%;
  padding: 14px;
  border-radius: 14px;
  background: var(--card-bg);
  box-shadow: 0 8px 20px rgba(0, 0, 0, 0.06);
}

.message-text {
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.7;
  color: var(--text-primary);
}

.mention-info {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 10px;
  padding: 8px 12px;
  border-radius: 8px;
  background: var(--bg-color);
  color: var(--text-muted);
  font-size: 12px;
  line-height: 1.5;
}

.markdown-body {
  color: var(--text-primary);
  line-height: 1.75;
}

.markdown-body :deep(h1),
.markdown-body :deep(h2),
.markdown-body :deep(h3) {
  margin: 0 0 10px;
  color: var(--text-primary);
  font-weight: 700;
}

.markdown-body :deep(h1) {
  font-size: 24px;
}

.markdown-body :deep(h2) {
  font-size: 20px;
}

.markdown-body :deep(h3) {
  font-size: 17px;
}

.markdown-body :deep(.md-paragraph) {
  margin: 0 0 10px;
}

.markdown-body :deep(ul) {
  margin: 0 0 10px;
  padding-left: 20px;
}

.markdown-body :deep(li) {
  margin: 4px 0;
}

.markdown-body :deep(blockquote) {
  margin: 0 0 10px;
  padding: 8px 12px;
  border-left: 3px solid #93c5fd;
  background: var(--bg-color);
  color: var(--text-secondary);
  border-radius: 0 8px 8px 0;
}

.markdown-body :deep(code) {
  padding: 2px 6px;
  border-radius: 6px;
  background: var(--bg-color);
  color: var(--text-primary);
  font-size: 12px;
}

.markdown-body :deep(a) {
  color: #2563eb;
  text-decoration: none;
}

.markdown-body :deep(a:hover) {
  text-decoration: underline;
}

.markdown-body :deep(.md-inline-image) {
  display: block;
  max-width: 100%;
  margin-top: 8px;
  border-radius: 10px;
}

.image-mock {
  border-radius: 12px;
  overflow: hidden;
  background: var(--bg-color);
}

.image-mock__img {
  display: block;
  width: 100%;
  max-height: 260px;
  object-fit: cover;
}

.image-mock__placeholder {
  padding: 40px 12px;
  text-align: center;
  color: var(--text-muted);
}

.file-mock {
  display: flex;
  gap: 12px;
  align-items: center;
  padding: 8px 0;
}

.file-mock__name {
  font-weight: 600;
  color: var(--text-primary);
}

.file-mock__desc,
.news-item__desc,
.news-item__url,
.card-mock__desc {
  font-size: 12px;
  color: var(--text-muted);
}

.news-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.news-item {
  display: grid;
  grid-template-columns: 92px 1fr;
  gap: 12px;
  align-items: start;
}

.news-item__cover {
  height: 72px;
  border-radius: 10px;
  overflow: hidden;
  background: var(--bg-color);
}

.news-item__cover-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.news-item__cover-placeholder {
  display: flex;
  width: 100%;
  height: 100%;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  color: var(--text-muted);
}

.news-item__content {
  min-width: 0;
}

.news-item__title,
.card-mock__title {
  margin-bottom: 6px;
  font-weight: 700;
  color: var(--text-primary);
}

.news-item__url {
  margin-top: 6px;
  word-break: break-all;
}

.card-mock {
  padding: 6px 0;
}

.card-mock__button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 110px;
  margin-top: 12px;
  padding: 8px 14px;
  border-radius: 999px;
  background: #2563eb;
  color: #ffffff;
  font-size: 12px;
  font-weight: 600;
}
</style>
