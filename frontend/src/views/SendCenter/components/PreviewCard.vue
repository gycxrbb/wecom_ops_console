<template>
  <div class="card-panel">
    <div class="card-header">
      <div class="card-header-icon card-header-icon--blue">
        <el-icon :size="16"><Monitor /></el-icon>
      </div>
      <h3 class="card-header-title">预览结果</h3>
      <el-button size="small" :loading="isPreviewing" @click="$emit('preview')" class="preview-btn">
        <el-icon><View /></el-icon> 预览
      </el-button>
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
          <div class="wechat-msg">
            <div class="wechat-avatar">
              <img v-if="userAvatar" :src="userAvatar" alt="avatar" class="wechat-avatar__img" />
              <div v-else class="wechat-avatar__fallback">{{ userInitial }}</div>
            </div>
            <div class="wechat-body">
              <div class="wechat-name">{{ userName }}</div>
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

                <template v-else-if="msgType === 'image' || msgType === 'emotion'">
                  <div class="image-mock">
                    <img v-if="imageUrl" :src="imageUrl" alt="image preview" class="image-mock__img" />
                    <div v-else class="image-mock__placeholder">{{ msgType === 'emotion' ? '表情包静态图预览' : '图片素材预览' }}</div>
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

                <template v-else-if="msgType === 'voice'">
                  <div class="file-mock">
                    <el-icon :size="20"><Microphone /></el-icon>
                    <div>
                      <div class="file-mock__name">{{ renderedContent.asset_name || '语音素材' }}</div>
                      <div class="file-mock__desc">系统会先上传 AMR 语音并以企微语音消息发送</div>
                    </div>
                  </div>
                </template>

                <template v-else-if="msgType === 'news'">
                  <div class="news-list">
                    <div
                      v-for="(article, index) in articles"
                      :key="index"
                      class="news-item"
                      :class="{ 'news-item--clickable': !!article.url }"
                      @click="openExternalUrl(article.url)"
                    >
                      <div class="news-item__cover">
                        <img v-if="article.picurl" :src="article.picurl" alt="cover" class="news-item__cover-img" />
                        <div v-else class="news-item__cover-placeholder">图文封面</div>
                      </div>
                      <div class="news-item__content">
                        <div class="news-item__title">{{ article.title || '未填写标题' }}</div>
                        <div class="news-item__desc">{{ article.description || '未填写描述' }}</div>
                        <div class="news-item__url">{{ article.url || '未填写链接' }}</div>
                        <button
                          v-if="article.url"
                          type="button"
                          class="news-item__action"
                          @click.stop="openExternalUrl(article.url)"
                        >
                          打开原文
                        </button>
                      </div>
                    </div>
                  </div>
                </template>

                <template v-else-if="msgType === 'template_card'">
                  <div
                    class="card-mock"
                    :class="{ 'card-mock--clickable': !!templateCardPrimaryUrl }"
                    @click="handleTemplateCardClick"
                  >
                    <div v-if="templateCardSourceDesc" class="card-mock__source">
                      {{ templateCardSourceDesc }}
                    </div>
                    <div class="card-mock__title">{{ templateCardTitle }}</div>
                    <div v-if="templateCardMainDesc" class="card-mock__main-desc">{{ templateCardMainDesc }}</div>

                    <template v-if="templateCardType === 'news_notice'">
                      <div v-if="templateCardImageUrl" class="card-mock__hero">
                        <img :src="templateCardImageUrl" alt="template card cover" class="card-mock__hero-img" />
                      </div>

                      <div
                        v-if="templateCardImageTextTitle || templateCardImageTextDesc || templateCardImageTextImageUrl"
                        class="card-mock__news-block"
                      >
                        <div class="card-mock__news-copy">
                          <div v-if="templateCardImageTextTitle" class="card-mock__news-title">{{ templateCardImageTextTitle }}</div>
                          <div v-if="templateCardImageTextDesc" class="card-mock__desc">{{ templateCardImageTextDesc }}</div>
                        </div>
                        <img
                          v-if="templateCardImageTextImageUrl"
                          :src="templateCardImageTextImageUrl"
                          alt="template card inline"
                          class="card-mock__news-thumb"
                        />
                      </div>
                    </template>

                    <template v-else>
                      <div v-if="templateCardDesc" class="card-mock__desc">{{ templateCardDesc }}</div>
                    </template>

                    <div v-if="templateCardEmphasisTitle || templateCardEmphasisDesc" class="card-mock__emphasis">
                      <strong>{{ templateCardEmphasisTitle || '--' }}</strong>
                      <span>{{ templateCardEmphasisDesc || '重点信息' }}</span>
                    </div>

                    <div v-if="templateCardVerticalItems.length" class="card-mock__vertical-list">
                      <div v-for="(item, index) in templateCardVerticalItems" :key="index" class="card-mock__vertical-item">
                        <span>{{ item.title || '字段' }}</span>
                        <strong>{{ item.desc || '未填写' }}</strong>
                      </div>
                    </div>

                    <div v-if="templateCardQuoteTitle || templateCardQuoteText" class="card-mock__quote">
                      <div v-if="templateCardQuoteTitle" class="card-mock__quote-title">{{ templateCardQuoteTitle }}</div>
                      <div class="card-mock__quote-text">{{ templateCardQuoteText }}</div>
                    </div>

                    <div v-if="templateCardHorizontalItems.length" class="card-mock__meta-list">
                      <div v-for="(item, index) in templateCardHorizontalItems" :key="index" class="card-mock__meta-item">
                        <span>{{ item.keyname || '字段' }}</span>
                        <strong>{{ item.value || '未填写' }}</strong>
                      </div>
                    </div>

                    <div v-if="templateCardPrimaryUrl" class="card-mock__link">
                      {{ templateCardPrimaryUrl }}
                    </div>
                    <div v-if="templateCardPrimaryUrl" class="card-mock__hint">
                      预览可点击查看交互效果，真实发送不会展示这行提示。
                    </div>
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
import { Document, Loading, Microphone, Monitor, UserFilled, View } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'

const props = defineProps({
  previewData: { type: Object, default: null },
  previewError: { type: String, default: '' },
  msgType: { type: String, default: 'text' },
  isPreviewing: { type: Boolean, default: false },
  contentJson: { type: Object, default: () => ({}) }
})

const userStore = useUserStore()
const userName = computed(() => userStore.user?.display_name || userStore.user?.username || '机器人')
const userAvatar = computed(() => {
  if (userStore.user?.avatar_url) return userStore.user.avatar_url
  if (userStore.user?.role === 'admin') return '/images/admain.jpg'
  return ''
})
const userInitial = computed(() => {
  const name = userName.value
  return name ? name.charAt(0).toUpperCase() : '机'
})

const mode = ref<'mock' | 'json'>('mock')

defineEmits(['preview'])

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
const templateCardType = computed(() => templateCard.value?.card_type || 'text_notice')
const templateCardSourceDesc = computed(() => templateCard.value?.source?.desc || '')
const templateCardTitle = computed(() => templateCard.value?.main_title?.title || '模板卡片预览')
const templateCardMainDesc = computed(() => templateCard.value?.main_title?.desc || '')
const templateCardDesc = computed(() => templateCard.value?.sub_title_text || templateCard.value?.horizontal_content_list?.[0]?.value || '模板卡片将按企微卡片样式发送到群里')
const templateCardImageUrl = computed(() => templateCard.value?.card_image?.url || '')
const templateCardImageTextTitle = computed(() => templateCard.value?.image_text_area?.title || '')
const templateCardImageTextDesc = computed(() => templateCard.value?.image_text_area?.desc || '')
const templateCardImageTextImageUrl = computed(() => templateCard.value?.image_text_area?.image_url || '')
const templateCardEmphasisTitle = computed(() => templateCard.value?.emphasis_content?.title || '')
const templateCardEmphasisDesc = computed(() => templateCard.value?.emphasis_content?.desc || '')
const templateCardQuoteTitle = computed(() => templateCard.value?.quote_area?.title || '')
const templateCardQuoteText = computed(() => templateCard.value?.quote_area?.quote_text || '')
const templateCardHorizontalItems = computed(() => Array.isArray(templateCard.value?.horizontal_content_list) ? templateCard.value.horizontal_content_list : [])
const templateCardVerticalItems = computed(() => Array.isArray(templateCard.value?.vertical_content_list) ? templateCard.value.vertical_content_list : [])
const templateCardPrimaryUrl = computed(() => (
  templateCard.value?.jump_list?.[0]?.url
  || templateCard.value?.card_action?.url
  || templateCard.value?.image_text_area?.url
  || templateCard.value?.quote_area?.url
  || ''
))

const openExternalUrl = (url?: string) => {
  if (!url) return
  window.open(url, '_blank', 'noopener,noreferrer')
}

const openTemplateCardUrl = (url?: string) => {
  openExternalUrl(url)
}

const handleTemplateCardClick = () => {
  if (!templateCardPrimaryUrl.value) return
  openTemplateCardUrl(templateCardPrimaryUrl.value)
}
</script>

<style scoped>
.preview-btn {
  margin-left: auto;
  margin-right: 8px;
}
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
  padding: 16px;
  border-radius: 16px;
  background: #ededed;
  border: 1px solid var(--border-color);
}
:global(html.dark) .wechat-shell {
  background: #1a1a1a;
}
.wechat-msg {
  display: flex;
  gap: 10px;
  align-items: flex-start;
}
.wechat-avatar {
  flex-shrink: 0;
  width: 40px;
  height: 40px;
  border-radius: 6px;
  overflow: hidden;
}
.wechat-avatar__img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.wechat-avatar__fallback {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #4a90d9;
  color: #fff;
  font-size: 16px;
  font-weight: 700;
}
.wechat-body {
  min-width: 0;
  max-width: calc(100% - 54px);
}
.wechat-name {
  font-size: 12px;
  color: #999;
  margin-bottom: 4px;
  line-height: 1;
}

.wechat-bubble {
  position: relative;
  padding: 10px 14px;
  border-radius: 0 10px 10px 10px;
  background: #fff;
  word-break: break-word;
}
:global(html.dark) .wechat-bubble {
  background: #2a2a2a;
}
.wechat-bubble::before {
  content: '';
  position: absolute;
  top: 0;
  left: -8px;
  width: 0;
  height: 0;
  border-top: 0 solid transparent;
  border-bottom: 10px solid transparent;
  border-right: 8px solid #fff;
}
:global(html.dark) .wechat-bubble::before {
  border-right-color: #2a2a2a;
}

.message-text {
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.7;
  color: #333;
}
:global(html.dark) .message-text {
  color: var(--text-primary);
}

.mention-info {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 10px;
  padding: 8px 12px;
  border-radius: 8px;
  background: #f5f5f5;
  color: #888;
  font-size: 12px;
  line-height: 1.5;
}
:global(html.dark) .mention-info {
  background: rgba(255,255,255,0.06);
  color: var(--text-muted);
}

.markdown-body {
  color: #333;
  line-height: 1.75;
}
:global(html.dark) .markdown-body {
  color: var(--text-primary);
}

.markdown-body :deep(h1),
.markdown-body :deep(h2),
.markdown-body :deep(h3) {
  margin: 0 0 10px;
  color: #333;
  font-weight: 700;
}
:global(html.dark) .markdown-body :deep(h1),
:global(html.dark) .markdown-body :deep(h2),
:global(html.dark) .markdown-body :deep(h3) {
  color: var(--text-primary);
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
  background: #f5f5f5;
  color: #666;
  border-radius: 0 8px 8px 0;
}

.markdown-body :deep(code) {
  padding: 2px 6px;
  border-radius: 6px;
  background: #f0f0f0;
  color: #333;
  font-size: 12px;
}

:global(html.dark) .markdown-body :deep(blockquote) {
  background: rgba(255,255,255,0.06);
  color: var(--text-secondary);
}

:global(html.dark) .markdown-body :deep(code) {
  background: rgba(255,255,255,0.08);
  color: var(--text-primary);
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
  color: #333;
}

.file-mock__desc,
.news-item__desc,
.news-item__url,
.card-mock__desc {
  font-size: 12px;
  color: #888;
}
:global(html.dark) .file-mock__name {
  color: var(--text-primary);
}
:global(html.dark) .file-mock__desc,
:global(html.dark) .news-item__desc,
:global(html.dark) .news-item__url,
:global(html.dark) .card-mock__desc {
  color: var(--text-muted);
}

.news-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.news-item {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 12px;
  border-radius: 12px;
  background: #ffffff;
  border: 1px solid #eef2f7;
}

.news-item--clickable {
  cursor: pointer;
}

.news-item--clickable:hover .news-item__title {
  color: #2563eb;
}

.news-item__cover {
  width: 100%;
  height: 148px;
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
  display: flex;
  flex-direction: column;
}

.news-item__title,
.card-mock__title {
  margin-bottom: 6px;
  font-weight: 700;
  color: #333;
}
:global(html.dark) .news-item__title,
:global(html.dark) .card-mock__title {
  color: var(--text-primary);
}

.news-item__url {
  margin-top: 6px;
  word-break: break-all;
}

.news-item__action {
  margin-top: 10px;
  align-self: flex-start;
  padding: 0;
  border: none;
  background: transparent;
  color: #2563eb;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
}

.news-item__action:hover {
  text-decoration: underline;
}

.card-mock {
  padding: 6px 0;
}
.card-mock--clickable {
  cursor: pointer;
}
.card-mock--clickable:hover .card-mock__title {
  color: #2563eb;
}
.card-mock__source {
  margin-bottom: 8px;
  font-size: 11px;
  color: #94a3b8;
}
.card-mock__main-desc {
  margin-bottom: 10px;
  font-size: 13px;
  line-height: 1.6;
  color: #64748b;
}
.card-mock__hero {
  margin: 12px 0;
  overflow: hidden;
  border-radius: 12px;
  background: #f8fafc;
}
.card-mock__hero-img {
  display: block;
  width: 100%;
  max-height: 180px;
  object-fit: cover;
}
.card-mock__news-block {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 12px;
  margin: 12px 0;
  padding: 12px;
  border-radius: 12px;
  background: #f8fafc;
}
.card-mock__news-copy {
  min-width: 0;
}
.card-mock__news-title {
  margin-bottom: 6px;
  font-size: 14px;
  font-weight: 700;
  color: #0f172a;
}
.card-mock__news-thumb {
  width: 64px;
  height: 64px;
  border-radius: 10px;
  object-fit: cover;
}
.card-mock__emphasis {
  display: inline-flex;
  flex-direction: column;
  gap: 4px;
  margin: 12px 0;
  padding: 12px 14px;
  border-radius: 12px;
  background: #eff6ff;
}
.card-mock__emphasis strong {
  font-size: 20px;
  color: #1d4ed8;
}
.card-mock__emphasis span {
  font-size: 12px;
  color: #64748b;
}
.card-mock__vertical-list,
.card-mock__meta-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 12px;
}
.card-mock__vertical-item,
.card-mock__meta-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  border-radius: 10px;
  background: #f8fafc;
}
.card-mock__vertical-item span,
.card-mock__meta-item span {
  font-size: 12px;
  color: #64748b;
}
.card-mock__vertical-item strong,
.card-mock__meta-item strong {
  font-size: 12px;
  color: #0f172a;
  text-align: right;
}
.card-mock__quote {
  margin-top: 12px;
  padding: 12px 14px;
  border-left: 3px solid #93c5fd;
  border-radius: 0 10px 10px 0;
  background: #f8fafc;
}
.card-mock__quote-title {
  margin-bottom: 4px;
  font-size: 12px;
  font-weight: 700;
  color: #0f172a;
}
.card-mock__quote-text {
  font-size: 12px;
  line-height: 1.6;
  color: #64748b;
}
.card-mock__link {
  margin-top: 10px;
  font-size: 11px;
  line-height: 1.5;
  color: #94a3b8;
  word-break: break-all;
}
.card-mock__hint {
  margin-top: 8px;
  font-size: 11px;
  line-height: 1.5;
  color: #94a3b8;
}
</style>
