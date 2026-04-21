<template>
  <div class="teaching-page" v-loading="treeLoading || articleLoading">
    <section class="teaching-hero">
      <div>
        <div class="teaching-hero__eyebrow">System Learning Center</div>
        <h1 class="teaching-hero__title">系统教学</h1>
        <p class="teaching-hero__desc">把平台操作说明、上手手册和管理员指南收在系统内，方便新同学直接阅读。</p>
      </div>
      <div class="teaching-hero__actions">
        <el-input
          v-model="keyword"
          placeholder="搜索教学文档..."
          clearable
          class="teaching-hero__search"
        />
        <el-button v-if="isAdmin" type="primary" @click="openCreateDialog">新建文档</el-button>
      </div>
    </section>

    <div class="teaching-layout">
      <aside class="teaching-sidebar">
        <div
          v-for="section in groupedDocs"
          :key="section.category"
          class="teaching-sidebar__section"
        >
          <div class="teaching-sidebar__section-title">{{ section.category }}</div>
          <button
            v-for="doc in section.docs"
            :key="doc.slug"
            type="button"
            class="teaching-sidebar__item"
            :class="{ 'is-active': activeSlug === doc.slug }"
            @click="selectDoc(doc.slug)"
          >
            <strong>{{ doc.title }}</strong>
            <span>{{ doc.summary || '暂无摘要' }}</span>
          </button>
        </div>
        <el-empty
          v-if="!groupedDocs.length && !treeLoading"
          description="暂无教学文档"
          :image-size="48"
        />
      </aside>

      <main class="teaching-article">
        <template v-if="article">
          <div class="teaching-article__header">
            <div>
              <el-tag size="small" type="success">{{ article.category }}</el-tag>
              <h2>{{ article.title }}</h2>
              <p v-if="article.summary" class="teaching-article__summary">{{ article.summary }}</p>
              <div class="teaching-article__meta">最近更新：{{ formatDate(article.updated_at) }}</div>
            </div>
            <div v-if="isAdmin" class="teaching-article__actions">
              <el-button plain @click="openEditDialog">编辑文档</el-button>
              <el-button type="danger" plain @click="handleDelete">删除文档</el-button>
            </div>
          </div>

          <div class="teaching-article__body">
            <article ref="articleRef" class="markdown-body" v-html="articleHtml" />
          </div>
        </template>
        <el-empty v-else description="选择左侧文档开始阅读" :image-size="64" />
      </main>

      <aside class="teaching-toc">
        <div class="teaching-toc__title">本页目录</div>
        <button
          v-for="heading in toc"
          :key="heading.id"
          type="button"
          class="teaching-toc__item"
          :style="{ paddingLeft: `${(heading.level - 1) * 12 + 12}px` }"
          @click="scrollToHeading(heading.id)"
        >
          {{ heading.text }}
        </button>
        <div v-if="article?.updated_at" class="teaching-toc__meta">
          最近更新：{{ formatDate(article.updated_at) }}
        </div>
      </aside>
    </div>

    <el-dialog
      v-model="editorVisible"
      :title="editingSlug ? '编辑教学文档' : '新建教学文档'"
      width="1080px"
      top="4vh"
      destroy-on-close
    >
      <div class="editor-shell">
        <div class="editor-form">
          <el-form label-width="90px">
            <el-form-item label="标题">
              <el-input v-model="editorForm.title" placeholder="例如：发送中心" />
            </el-form-item>
            <el-form-item label="Slug">
              <el-input v-model="editorForm.slug" placeholder="例如：send-center" />
            </el-form-item>
            <el-form-item label="分类">
              <el-input v-model="editorForm.category" placeholder="例如：核心业务" />
            </el-form-item>
            <el-form-item label="排序">
              <el-input-number v-model="editorForm.order" :min="1" :max="999" style="width: 100%" />
            </el-form-item>
            <el-form-item label="摘要">
              <el-input v-model="editorForm.summary" type="textarea" :rows="3" placeholder="文档简介，显示在目录卡片里" />
            </el-form-item>
          </el-form>
        </div>

        <div class="editor-toolbar">
          <div class="editor-toolbar__left">
            <el-button
              :type="editorTab === 'edit' ? 'primary' : 'default'"
              plain
              @click="editorTab = 'edit'"
            >
              Markdown 编辑
            </el-button>
            <el-button
              :type="editorTab === 'preview' ? 'primary' : 'default'"
              plain
              @click="editorTab = 'preview'"
            >
              预览
            </el-button>
          </div>
          <el-upload
            action="javascript:;"
            :show-file-list="false"
            :auto-upload="false"
            accept=".png,.jpg,.jpeg,.webp,.gif"
            :on-change="handleImageUpload"
          >
            <el-button :loading="uploadingImage">上传图片并插入</el-button>
          </el-upload>
        </div>

        <div class="editor-panels">
          <el-input
            v-if="editorTab === 'edit'"
            v-model="editorForm.content"
            type="textarea"
            :rows="22"
            placeholder="输入 Markdown 内容..."
            class="editor-panels__textarea"
          />
          <div v-else class="editor-preview markdown-body" v-html="editorPreviewHtml" />
        </div>
      </div>

      <template #footer>
        <el-button @click="editorVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveDoc">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox, type UploadFile } from 'element-plus'
import request from '@/utils/request'
import { useUserStore } from '@/stores/user'
import { extractMarkdownHeadings, renderMarkdown } from '@/utils/simpleMarkdown'

type DocMeta = {
  slug: string
  title: string
  category: string
  summary: string
  order: number
  filename: string
  updated_at: string
}

type DocDetail = DocMeta & {
  content: string
}

const userStore = useUserStore()
const isAdmin = computed(() => userStore.user?.role === 'admin')

const treeLoading = ref(false)
const articleLoading = ref(false)
const saving = ref(false)
const uploadingImage = ref(false)
const keyword = ref('')
const activeSlug = ref('')
const docs = ref<DocMeta[]>([])
const article = ref<DocDetail | null>(null)
const editorVisible = ref(false)
const editingSlug = ref('')
const editorTab = ref<'edit' | 'preview'>('edit')
const articleRef = ref<HTMLElement | null>(null)

const editorForm = ref({
  title: '',
  slug: '',
  category: '基础上手',
  summary: '',
  order: 1,
  content: '',
})

const filteredDocs = computed(() => {
  const query = keyword.value.trim().toLowerCase()
  if (!query) return docs.value
  return docs.value.filter((doc) => {
    const haystack = [doc.title, doc.summary, doc.category, doc.slug].join(' ').toLowerCase()
    return haystack.includes(query)
  })
})

const groupedDocs = computed(() => {
  const buckets = new Map<string, DocMeta[]>()
  filteredDocs.value
    .slice()
    .sort((left, right) => left.order - right.order || left.title.localeCompare(right.title, 'zh-CN'))
    .forEach((doc) => {
      if (!buckets.has(doc.category)) buckets.set(doc.category, [])
      buckets.get(doc.category)?.push(doc)
    })
  return [...buckets.entries()].map(([category, grouped]) => ({ category, docs: grouped }))
})

const articleHtml = computed(() => (article.value ? renderMarkdown(article.value.content) : ''))
const editorPreviewHtml = computed(() => renderMarkdown(editorForm.value.content))
const toc = computed(() => (article.value ? extractMarkdownHeadings(article.value.content) : []))

const formatDate = (value: string) => {
  if (!value) return '未知'
  return value.replace('T', ' ').replace('Z', '').slice(0, 16)
}

const fetchTree = async () => {
  treeLoading.value = true
  try {
    const res: any = await request.get('/v1/system-docs/tree')
    docs.value = res.docs || []
    if (!activeSlug.value && docs.value.length) {
      activeSlug.value = docs.value[0].slug
    }
  } catch (error: any) {
    ElMessage.error('加载系统教学目录失败: ' + String(error?.message || error))
  } finally {
    treeLoading.value = false
  }
}

const fetchDoc = async (slug: string) => {
  if (!slug) return
  articleLoading.value = true
  try {
    const res: any = await request.get(`/v1/system-docs/entries/${slug}`)
    article.value = res
    activeSlug.value = res.slug
    await nextTick()
    if (articleRef.value) {
      articleRef.value.scrollTop = 0
    }
  } catch (error: any) {
    ElMessage.error('加载文档失败: ' + String(error?.message || error))
  } finally {
    articleLoading.value = false
  }
}

const selectDoc = async (slug: string) => {
  await fetchDoc(slug)
}

const openCreateDialog = () => {
  editingSlug.value = ''
  editorTab.value = 'edit'
  editorForm.value = {
    title: '',
    slug: '',
    category: groupedDocs.value[0]?.category || '基础上手',
    summary: '',
    order: docs.value.length + 1,
    content: '# 新文档\n\n请在这里编写内容。',
  }
  editorVisible.value = true
}

const openEditDialog = () => {
  if (!article.value) return
  editingSlug.value = article.value.slug
  editorTab.value = 'edit'
  editorForm.value = {
    title: article.value.title,
    slug: article.value.slug,
    category: article.value.category,
    summary: article.value.summary,
    order: article.value.order,
    content: article.value.content,
  }
  editorVisible.value = true
}

const saveDoc = async () => {
  if (!editorForm.value.title.trim()) {
    ElMessage.warning('请输入文档标题')
    return
  }
  if (!editorForm.value.content.trim()) {
    ElMessage.warning('文档内容不能为空')
    return
  }
  saving.value = true
  try {
    const payload = {
      ...editorForm.value,
      title: editorForm.value.title.trim(),
      slug: editorForm.value.slug.trim(),
      category: editorForm.value.category.trim() || '基础上手',
      summary: editorForm.value.summary.trim(),
      content: editorForm.value.content,
    }
    const res: any = editingSlug.value
      ? await request.put(`/v1/system-docs/entries/${editingSlug.value}`, payload)
      : await request.post('/v1/system-docs/entries', payload)
    editorVisible.value = false
    ElMessage.success('文档已保存')
    await fetchTree()
    await fetchDoc(res.slug)
  } catch (error: any) {
    ElMessage.error('保存失败: ' + String(error?.message || error))
  } finally {
    saving.value = false
  }
}

const handleDelete = async () => {
  if (!article.value) return
  try {
    await ElMessageBox.confirm(`确认删除文档「${article.value.title}」吗？`, '删除系统教学文档', {
      type: 'warning',
    })
    await request.delete(`/v1/system-docs/entries/${article.value.slug}`)
    ElMessage.success('文档已删除')
    article.value = null
    activeSlug.value = ''
    await fetchTree()
    if (docs.value[0]?.slug) {
      await fetchDoc(docs.value[0].slug)
    }
  } catch {
    // ignore cancel
  }
}

const handleImageUpload = async (uploadFile: UploadFile) => {
  if (!uploadFile.raw) return
  uploadingImage.value = true
  try {
    const formData = new FormData()
    formData.append('file', uploadFile.raw)
    formData.append('article_slug', editorForm.value.slug || editingSlug.value || 'system-doc')
    const res: any = await request.post('/v1/system-docs/upload-image', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 180000,
    })
    editorForm.value.content = `${editorForm.value.content.trim()}\n\n${res.markdown}\n`
    ElMessage.success('图片已上传并插入 Markdown')
    editorTab.value = 'edit'
  } catch (error: any) {
    ElMessage.error('图片上传失败: ' + String(error?.message || error))
  } finally {
    uploadingImage.value = false
  }
}

const scrollToHeading = (id: string) => {
  const element = document.getElementById(id)
  element?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

onMounted(async () => {
  await fetchTree()
  if (activeSlug.value) {
    await fetchDoc(activeSlug.value)
  }
})
</script>

<style scoped>
.teaching-page {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.teaching-hero {
  display: flex;
  justify-content: space-between;
  gap: 20px;
  padding: 24px 28px;
  border-radius: 20px;
  border: 1px solid var(--border-color);
  background: var(--card-bg);
}

.teaching-hero__eyebrow {
  color: var(--primary-color);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.teaching-hero__title {
  margin: 10px 0 8px;
  font-size: 32px;
  color: var(--text-primary);
}

.teaching-hero__desc {
  max-width: 720px;
  margin: 0;
  color: var(--text-secondary);
  line-height: 1.7;
}

.teaching-hero__actions {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-width: 260px;
}

.teaching-layout {
  display: grid;
  grid-template-columns: 280px minmax(0, 1fr) 220px;
  gap: 18px;
  align-items: start;
}

.teaching-sidebar,
.teaching-article,
.teaching-toc {
  border: 1px solid var(--border-color);
  border-radius: 20px;
  background: var(--card-bg);
}

.teaching-sidebar,
.teaching-toc {
  position: sticky;
  top: 0;
  max-height: calc(100vh - 120px);
  overflow: auto;
}

.teaching-sidebar {
  padding: 14px;
}

.teaching-sidebar__section + .teaching-sidebar__section {
  margin-top: 14px;
}

.teaching-sidebar__section-title {
  margin-bottom: 8px;
  font-size: 12px;
  font-weight: 700;
  color: var(--text-muted);
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.teaching-sidebar__item {
  display: flex;
  width: 100%;
  border: 0;
  background: transparent;
  text-align: left;
  border-radius: 12px;
  padding: 10px 12px;
  cursor: pointer;
  flex-direction: column;
  gap: 4px;
  color: var(--text-primary);
}

.teaching-sidebar__item:hover,
.teaching-sidebar__item.is-active {
  background: rgba(34, 197, 94, 0.08);
}

.teaching-sidebar__item span {
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.5;
}

.teaching-article {
  padding: 24px 28px;
}

.teaching-article__header {
  display: flex;
  justify-content: space-between;
  gap: 20px;
  padding-bottom: 20px;
  border-bottom: 1px solid var(--border-color);
}

.teaching-article__header h2 {
  margin: 10px 0 8px;
  font-size: 28px;
  color: var(--text-primary);
}

.teaching-article__summary,
.teaching-article__meta {
  color: var(--text-secondary);
  line-height: 1.7;
}

.teaching-article__actions {
  display: flex;
  gap: 10px;
  align-items: flex-start;
}

.teaching-article__body {
  margin-top: 20px;
}

.teaching-toc {
  padding: 16px 12px;
}

.teaching-toc__title {
  margin-bottom: 10px;
  font-size: 13px;
  font-weight: 700;
  color: var(--text-primary);
}

.teaching-toc__item {
  display: block;
  width: 100%;
  border: 0;
  background: transparent;
  text-align: left;
  padding: 8px 10px;
  border-radius: 10px;
  color: var(--text-secondary);
  cursor: pointer;
}

.teaching-toc__item:hover {
  background: rgba(34, 197, 94, 0.08);
  color: var(--text-primary);
}

.teaching-toc__meta {
  margin-top: 14px;
  padding-top: 14px;
  border-top: 1px solid var(--border-color);
  font-size: 12px;
  color: var(--text-muted);
}

.editor-shell {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.editor-form {
  padding: 4px 0;
}

.editor-toolbar {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
}

.editor-toolbar__left {
  display: flex;
  gap: 10px;
}

.editor-panels__textarea :deep(textarea) {
  font-family: "Consolas", "Courier New", monospace;
}

.editor-preview {
  min-height: 520px;
  max-height: 520px;
  overflow: auto;
  padding: 18px 20px;
  border-radius: 14px;
  border: 1px solid var(--border-color);
  background: var(--bg-color);
}

:deep(.markdown-body) {
  color: var(--text-primary);
  line-height: 1.8;
  word-break: break-word;
}

:deep(.markdown-body .md-heading) {
  margin: 1.4em 0 0.6em;
  scroll-margin-top: 20px;
}

:deep(.markdown-body .md-paragraph) {
  margin: 0 0 1em;
  color: var(--text-primary);
}

:deep(.markdown-body .md-list) {
  padding-left: 1.5em;
  margin: 0 0 1em;
}

:deep(.markdown-body .md-code-block) {
  margin: 1em 0;
  padding: 14px 16px;
  border-radius: 14px;
  overflow: auto;
  background: #111827;
  color: #e5e7eb;
}

:deep(.markdown-body .md-inline-code) {
  padding: 2px 6px;
  border-radius: 6px;
  background: rgba(15, 23, 42, 0.08);
  font-size: 0.95em;
}

:deep(.markdown-body .md-link) {
  color: #15803d;
  text-decoration: none;
}

:deep(.markdown-body .md-link:hover) {
  text-decoration: underline;
}

:deep(.markdown-body .md-image) {
  display: block;
  max-width: 100%;
  margin: 16px auto;
  border-radius: 14px;
  box-shadow: 0 12px 32px rgba(15, 23, 42, 0.08);
}

:deep(.markdown-body .md-blockquote) {
  margin: 1em 0;
  padding: 10px 14px;
  border-left: 4px solid rgba(34, 197, 94, 0.65);
  background: rgba(34, 197, 94, 0.06);
  border-radius: 0 12px 12px 0;
}

:deep(.markdown-body .md-divider) {
  margin: 1.4em 0;
  border: 0;
  border-top: 1px solid var(--border-color);
}

@media (max-width: 1180px) {
  .teaching-layout {
    grid-template-columns: 250px minmax(0, 1fr);
  }

  .teaching-toc {
    display: none;
  }
}

@media (max-width: 768px) {
  .teaching-hero {
    flex-direction: column;
    padding: 18px 16px;
  }

  .teaching-hero__title {
    font-size: 24px;
  }

  .teaching-hero__actions {
    min-width: 0;
  }

  .teaching-layout {
    grid-template-columns: 1fr;
  }

  .teaching-sidebar,
  .teaching-toc {
    position: static;
    max-height: none;
  }

  .teaching-article,
  .teaching-sidebar {
    padding: 16px;
  }

  .teaching-article__header {
    flex-direction: column;
  }

  .editor-toolbar {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
