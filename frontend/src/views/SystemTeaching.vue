<template>
  <div class="teaching-page" v-loading="treeLoading || articleLoading">
    <div class="teaching-page__backdrop" aria-hidden="true" />
    <section class="teaching-hero">
      <div class="teaching-hero__top">
        <div class="teaching-hero__content">
          <div class="teaching-hero__eyebrow">System Learning Center</div>
          <h1 class="teaching-hero__title">系统教学</h1>
          <p class="teaching-hero__desc">
            把平台操作说明、上手手册和管理员指南收在系统内，帮助新同学更快完成上手、查找和复盘。
          </p>
        </div>
        <div class="teaching-hero__tools">
          <el-input
            v-model="keyword"
            placeholder="搜索教学文档..."
            clearable
            class="teaching-hero__search"
          />
          <el-button v-if="isAdmin" type="primary" @click="openCreateDialog">新建文档</el-button>
        </div>
      </div>
      <div class="teaching-hero__meta-line">
        <div class="teaching-hero__stats">
          <span>共 {{ docs.length }} 篇文档</span>
          <span>{{ groupedDocs.length }} 个分类</span>
          <span>当前聚焦：{{ article?.category || '等待选择' }}</span>
          <span>当前展示 {{ filteredDocs.length }} 篇结果</span>
        </div>
        <div class="teaching-hero__meta-side">
          <span class="teaching-hero__search-note">搜索范围：标题 / 摘要 / 分类 / 标识</span>
          <div v-if="isAdmin" class="teaching-hero__admin-tip">
            管理员可直接在系统内维护正文、封面图和推荐阅读。
          </div>
        </div>
      </div>
    </section>

    <div class="teaching-layout" :class="{ 'is-toc-collapsed': !shouldShowToc }">
      <aside class="teaching-sidebar">
        <div class="teaching-sidebar__header">
          <div>
            <div class="teaching-sidebar__eyebrow">Knowledge Shelf</div>
            <strong>教学目录</strong>
          </div>
          <span>{{ filteredDocs.length }} 篇</span>
        </div>
        <div v-if="recentDocs.length" class="teaching-sidebar__recent">
          <div class="teaching-sidebar__section-title">最近阅读</div>
          <div class="teaching-sidebar__recent-list">
            <button
              v-for="doc in recentDocs"
              :key="`recent-${doc.slug}`"
              type="button"
              class="teaching-sidebar__recent-item"
              @click="selectDoc(doc.slug)"
            >
              {{ doc.title }}
            </button>
          </div>
        </div>
        <div v-if="keyword.trim()" class="teaching-sidebar__search-state">
          <strong>{{ searchStatusLabel }}</strong>
          <span v-if="filteredDocs.length">已按当前关键词过滤目录列表</span>
          <span v-else>试试更短的关键词，或改用模块名来搜索</span>
        </div>
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
            <div class="teaching-sidebar__text">
              <div class="teaching-sidebar__title-row">
                <strong>{{ doc.title }}</strong>
                <el-tag
                  v-if="isAdmin && doc.status === 'draft'"
                  size="small"
                  type="warning"
                  effect="plain"
                >
                  草稿
                </el-tag>
                <el-tag
                  v-else-if="isAdmin && doc.has_draft"
                  size="small"
                  effect="plain"
                >
                  待发布
                </el-tag>
              </div>
              <span>{{ keyword.trim() ? (searchHitMap.get(doc.slug)?.snippet || doc.summary || '暂无摘要') : (doc.summary || '暂无摘要') }}</span>
            </div>
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
          <div class="teaching-article__masthead">
            <div class="teaching-article__masthead-top">
              <div class="teaching-article__kicker">
                <span class="teaching-article__kicker-line" />
                <span>{{ article.category }}</span>
              </div>
              <el-button
                v-if="canShowToc"
                text
                class="teaching-article__toc-toggle"
                @click="showTocPanel = !showTocPanel"
              >
                {{ shouldShowToc ? '收起本页大纲' : '查看本页大纲' }}
              </el-button>
            </div>
            <div class="teaching-article__hero">
              <div class="teaching-article__header">
                <h2>{{ article.title }}</h2>
                <p v-if="article.summary" class="teaching-article__summary">{{ article.summary }}</p>
                <div class="teaching-article__meta-inline">
                  <span>最近更新：{{ formatDate(article.updated_at) }}</span>
                  <span v-if="article.author">作者：{{ article.author }}</span>
                  <span>难度：{{ currentDifficultyLabel }}</span>
                  <span>标识：{{ article.slug }}</span>
                  <span>顺位：{{ formatOrder(article.order) }}</span>
                </div>
                <div class="teaching-article__status-row">
                  <el-tag v-if="article.status === 'draft'" type="warning" effect="plain">草稿</el-tag>
                  <el-tag v-else type="success" effect="plain">已发布</el-tag>
                  <el-tag v-if="article.has_draft && article.status === 'published'" effect="plain">有未发布草稿</el-tag>
                  <span v-if="article.published_at">发布时间：{{ formatDate(article.published_at) }}</span>
                  <span v-if="article.draft_updated_at">草稿更新：{{ formatDate(article.draft_updated_at) }}</span>
                </div>
                <div v-if="isAdmin" class="teaching-article__actions">
                  <el-button plain @click="openEditDialog">编辑文档</el-button>
                  <el-button type="danger" plain @click="handleDelete">删除文档</el-button>
                </div>
              </div>
              <div v-if="article.cover_image" class="teaching-article__cover">
                <img :src="article.cover_image" :alt="article.title" />
              </div>
            </div>
          </div>

          <div class="teaching-article__sheet">
            <div class="teaching-article__sheet-edge" aria-hidden="true" />
            <div class="teaching-article__body">
              <article ref="articleRef" class="markdown-body" v-html="articleHtml" />
            </div>
          </div>
          <div v-if="previousDoc || nextDoc" class="teaching-article__pager">
            <button
              v-if="previousDoc"
              type="button"
              class="teaching-article__pager-card"
              @click="selectDoc(previousDoc.slug)"
            >
              <span>上一篇</span>
              <strong>{{ previousDoc.title }}</strong>
              <small>{{ previousDoc.category }}</small>
            </button>
            <div v-else class="teaching-article__pager-card is-placeholder" />
            <button
              v-if="nextDoc"
              type="button"
              class="teaching-article__pager-card is-next"
              @click="selectDoc(nextDoc.slug)"
            >
              <span>下一篇</span>
              <strong>{{ nextDoc.title }}</strong>
              <small>{{ nextDoc.category }}</small>
            </button>
            <div v-else class="teaching-article__pager-card is-placeholder" />
          </div>
          <section v-if="recommendedDocs.length" class="teaching-article__recommend">
            <div class="teaching-article__recommend-header">
              <span>Recommended Reading</span>
              <strong>继续阅读</strong>
            </div>
            <div class="teaching-article__recommend-grid">
              <button
                v-for="doc in recommendedDocs"
                :key="`recommended-${doc.slug}`"
                type="button"
                class="teaching-article__recommend-card"
                @click="selectDoc(doc.slug)"
              >
                <small>{{ formatDifficulty(doc.difficulty) }}</small>
                <strong>{{ doc.title }}</strong>
                <span>{{ doc.summary || doc.category }}</span>
              </button>
            </div>
          </section>
        </template>
        <el-empty v-else description="选择左侧文档开始阅读" :image-size="64" />
      </main>

      <aside v-if="shouldShowToc" class="teaching-toc">
        <div class="teaching-toc__header">
          <div class="teaching-toc__title">本页目录</div>
          <strong>{{ toc.length }}</strong>
        </div>
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
      :title="editorFocusMode ? '' : (editingSlug ? '编辑教学文档' : '新建教学文档')"
      width="1080px"
      top="8vh"
      :fullscreen="editorFocusMode"
      destroy-on-close
      append-to-body
      :before-close="handleEditorDialogBeforeClose"
      class="system-teaching-editor-dialog"
    >
      <div class="editor-shell" :class="{ 'is-focus-mode': editorFocusMode }">
        <div class="editor-shell__toolbar">
          <div class="editor-shell__identity">
            <div class="editor-shell__eyebrow">Writing Workspace</div>
            <strong>{{ editorForm.title.trim() || (editingSlug ? '未命名文档' : '新建教学文档') }}</strong>
            <span>{{ editorStatusLabel }}</span>
          </div>
          <div class="editor-shell__actions">
            <el-button
              plain
              class="editor-shell__tab-button"
              :class="{ 'is-active': editorTab === 'edit' }"
              @click="editorTab = 'edit'"
            >
              Markdown 编辑
            </el-button>
            <el-button
              plain
              class="editor-shell__tab-button"
              :class="{ 'is-active': editorTab === 'preview' }"
              @click="editorTab = 'preview'"
            >
              预览
            </el-button>
            <el-upload
              action="javascript:;"
              :show-file-list="false"
              :auto-upload="false"
              accept=".png,.jpg,.jpeg,.webp,.gif"
              :on-change="handleImageUpload"
            >
              <el-button :loading="uploadingImage">上传图片</el-button>
            </el-upload>
            <el-button plain @click="showEditorSettings = true">更多设置</el-button>
            <el-button plain @click="editorFocusMode = !editorFocusMode">
              {{ editorFocusMode ? '退出专注' : '专注模式' }}
            </el-button>
            <el-button @click="requestCloseEditor">关闭</el-button>
            <el-button :loading="saving" @click="saveDoc('draft')">保存草稿</el-button>
            <el-button type="primary" :loading="saving" @click="saveDoc('publish')">发布</el-button>
          </div>
        </div>
        <div class="editor-shell__subbar">
          <div class="editor-shell__meta">
            <span>快捷键：Ctrl/Cmd + S 保存</span>
            <span>Ctrl/Cmd + B/I/K 常用格式</span>
            <span>支持粘贴图片或拖拽图片到编辑区自动上传</span>
            <span>作者：{{ editorForm.author.trim() || '未填写' }}</span>
            <span>当前难度：{{ formatDifficulty(editorForm.difficulty) }}</span>
          </div>
          <span class="editor-shell__mode">{{ editorFocusMode ? '专注写作中' : '标准编辑模式' }}</span>
        </div>
        <div v-if="!editorFocusMode" class="editor-snippets">
          <div class="editor-snippets__title">常用插入</div>
          <div class="editor-snippets__list">
            <el-tooltip
              v-for="snippet in editorSnippets"
              :key="snippet.label"
              :content="`${snippet.label} · ${snippet.hint}`"
              placement="top"
            >
              <button
                type="button"
                class="editor-snippets__item"
                @click="insertSnippet(snippet.content)"
              >
                <component :is="snippet.icon" class="editor-snippets__icon" />
                <span>{{ snippet.label }}</span>
              </button>
            </el-tooltip>
          </div>
        </div>

        <div class="editor-panels">
          <div class="editor-panels__main">
            <el-input
              v-if="editorTab === 'edit'"
              ref="editorTextareaRef"
              v-model="editorForm.content"
              type="textarea"
              :rows="22"
              placeholder="输入 Markdown 内容..."
              class="editor-panels__textarea"
            />
            <div
              v-else
              ref="editorPreviewRef"
              class="editor-preview markdown-body"
              v-html="editorPreviewHtml"
            />
          </div>
          <aside v-if="!editorFocusMode" class="editor-outline">
            <div class="editor-outline__title">写作辅助</div>
            <div v-if="editorOutline.length" class="editor-outline__list">
              <button
                v-for="heading in editorOutline"
                :key="heading.id"
                type="button"
                class="editor-outline__item"
                @click="scrollEditorOutlineIntoView(heading.id)"
              >
                {{ heading.text }}
              </button>
            </div>
            <div v-else class="editor-outline__empty">写正文时生成的小标题，会显示在这里。</div>
            <div class="editor-outline__meta">
              当前难度：{{ formatDifficulty(editorForm.difficulty) }}
            </div>
            <div class="editor-outline__meta">
              推荐阅读：{{ editorForm.recommended_slugs.length }} 篇
            </div>
          </aside>
        </div>
      </div>
    </el-dialog>
    <el-drawer
      v-model="showEditorSettings"
      title="文档设置"
      size="420px"
      append-to-body
      :with-header="true"
    >
      <div class="editor-settings">
        <div class="editor-settings__summary">
          默认先写正文，分类、推荐阅读、封面图等配置都集中放在这里。
        </div>
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
          <el-form-item label="作者">
            <el-input v-model="editorForm.author" placeholder="例如：运营组 / 张三" />
          </el-form-item>
          <el-form-item label="排序">
            <el-input-number v-model="editorForm.order" :min="1" :max="999" style="width: 100%" />
          </el-form-item>
          <el-form-item label="摘要">
            <el-input v-model="editorForm.summary" type="textarea" :rows="3" placeholder="文档简介，显示在目录卡片里" />
          </el-form-item>
          <el-form-item label="封面图">
            <div class="editor-cover-field">
              <el-input v-model="editorForm.cover_image" placeholder="输入封面图 URL，建议使用 16:9 图片" />
              <el-button
                v-if="latestUploadedImageUrl"
                plain
                @click="useLatestUploadedImageAsCover"
              >
                使用最近上传图片
              </el-button>
            </div>
          </el-form-item>
          <el-form-item label="难度">
            <el-select v-model="editorForm.difficulty" style="width: 100%">
              <el-option
                v-for="option in DIFFICULTY_OPTIONS"
                :key="option.value"
                :label="option.label"
                :value="option.value"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="推荐阅读">
            <el-select
              v-model="editorForm.recommended_slugs"
              multiple
              clearable
              collapse-tags
              collapse-tags-tooltip
              style="width: 100%"
              placeholder="选择推荐给读者继续阅读的文档"
            >
              <el-option
                v-for="doc in docs.filter((item) => item.slug !== editingSlug)"
                :key="doc.slug"
                :label="doc.title"
                :value="doc.slug"
              />
            </el-select>
          </el-form-item>
        </el-form>
      </div>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
defineOptions({ name: 'SystemTeaching' })
import { computed, markRaw, nextTick, onBeforeUnmount, onMounted, ref, watch, type Component } from 'vue'
import { ElMessage, ElMessageBox, type UploadFile } from 'element-plus'
import {
  CollectionTag,
  DocumentAdd,
  Link,
  Picture,
  Tickets,
} from '@element-plus/icons-vue'
import request from '#/utils/request'
import { useUserStore } from '#/stores/user'
import { extractMarkdownHeadings, renderMarkdown } from '#/utils/simpleMarkdown'

type DocMeta = {
  slug: string
  title: string
  category: string
  author: string
  summary: string
  cover_image: string
  difficulty: string
  recommended_slugs: string[]
  status: 'draft' | 'published'
  has_draft: boolean
  published_at: string
  draft_updated_at: string
  order: number
  filename: string
  updated_at: string
}

type DocDetail = DocMeta & {
  content: string
  recommended_docs?: DocMeta[]
}

type SnippetItem = {
  label: string
  hint: string
  content: string
  icon: Component
}

type SearchHit = DocMeta & {
  snippet: string
  matched_fields: string[]
}

const userStore = useUserStore()
const isAdmin = computed(() => userStore.user?.role === 'admin')
const RECENT_DOCS_KEY = 'system_teaching_recent_docs'
const AUTOSAVE_DELAY_MS = 2500
const DIFFICULTY_OPTIONS = [
  { value: 'beginner', label: '入门' },
  { value: 'intermediate', label: '进阶' },
  { value: 'advanced', label: '高级' },
  { value: 'admin', label: '管理员' },
]

const treeLoading = ref(false)
const articleLoading = ref(false)
const saving = ref(false)
const uploadingImage = ref(false)
const keyword = ref('')
const activeSlug = ref('')
const docs = ref<DocMeta[]>([])
const article = ref<DocDetail | null>(null)
const searchHits = ref<SearchHit[]>([])
const searchLoading = ref(false)
const editorVisible = ref(false)
const editingSlug = ref('')
const editorTab = ref<'edit' | 'preview'>('edit')
const articleRef = ref<HTMLElement | null>(null)
const editorTextareaRef = ref<any>(null)
const editorPreviewRef = ref<HTMLElement | null>(null)
const recentSlugs = ref<string[]>([])
const latestUploadedImageUrl = ref('')
const editorInitialSnapshot = ref('')
const showTocPanel = ref(false)
const showEditorSettings = ref(false)
const editorFocusMode = ref(false)
const editorAutosaving = ref(false)
const editorLastSavedAt = ref('')
const editorSaveTimer = ref<number | null>(null)
const keywordSearchTimer = ref<number | null>(null)
const isBootstrappingEditor = ref(false)

const editorForm = ref({
  title: '',
  slug: '',
  category: '基础上手',
  author: '',
  summary: '',
  cover_image: '',
  difficulty: 'beginner',
  recommended_slugs: [] as string[],
  status: 'draft' as 'draft' | 'published',
  order: 1,
  content: '',
})

const filteredDocs = computed(() => {
  if (!keyword.value.trim()) return docs.value
  return searchHits.value
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

const sortedDocs = computed(() =>
  docs.value
    .slice()
    .sort((left, right) => left.order - right.order || left.title.localeCompare(right.title, 'zh-CN'))
)

const activeDocIndex = computed(() => sortedDocs.value.findIndex((doc) => doc.slug === activeSlug.value))

const previousDoc = computed(() => {
  const index = activeDocIndex.value
  if (index <= 0) return null
  return sortedDocs.value[index - 1]
})

const nextDoc = computed(() => {
  const index = activeDocIndex.value
  if (index < 0 || index >= sortedDocs.value.length - 1) return null
  return sortedDocs.value[index + 1]
})

const recentDocs = computed(() =>
  recentSlugs.value
    .map((slug) => docs.value.find((doc) => doc.slug === slug))
    .filter((doc): doc is DocMeta => Boolean(doc))
    .filter((doc) => doc.slug !== activeSlug.value)
    .slice(0, 5)
)

const editorSnippets: SnippetItem[] = [
  {
    label: '二级标题',
    hint: '快速补一个章节标题',
    content: '## 章节标题\n\n请在这里补充这一节的教学内容。\n',
    icon: markRaw(DocumentAdd),
  },
  {
    label: '操作步骤',
    hint: '适合写流程或按钮指引',
    content: '## 操作步骤\n\n1. 第一步\n2. 第二步\n3. 第三步\n',
    icon: markRaw(CollectionTag),
  },
  {
    label: '注意事项',
    hint: '用强调块提醒新同学',
    content: '> 注意事项：这里填写执行前必须知道的提醒。\n',
    icon: markRaw(Tickets),
  },
  {
    label: '示例代码',
    hint: '适合命令或配置片段',
    content: '```text\n在这里输入示例内容\n```\n',
    icon: markRaw(Link),
  },
  {
    label: '配图说明',
    hint: '图片后接一句解读更清楚',
    content: '![配图说明](https://example.com/image.png)\n\n图示说明：这里补充这张图想表达的重点。\n',
    icon: markRaw(Picture),
  },
]

const articleHtml = computed(() => (article.value ? renderMarkdown(article.value.content) : ''))
const editorPreviewHtml = computed(() => renderMarkdown(editorForm.value.content))
const toc = computed(() => (article.value ? extractMarkdownHeadings(article.value.content) : []))
const editorOutline = computed(() => extractMarkdownHeadings(editorForm.value.content))
const recommendedDocs = computed(() => {
  if (article.value?.recommended_docs?.length) return article.value.recommended_docs
  if (!article.value?.recommended_slugs?.length) return []
  return article.value.recommended_slugs
    .map((slug) => docs.value.find((doc) => doc.slug === slug))
    .filter((doc): doc is DocMeta => Boolean(doc))
    .filter((doc) => doc.slug !== article.value?.slug)
})
const difficultyLabelMap = Object.fromEntries(DIFFICULTY_OPTIONS.map((item) => [item.value, item.label]))
const currentDifficultyLabel = computed(() => difficultyLabelMap[article.value?.difficulty || 'beginner'] || '入门')
const isEditorDirty = computed(() => JSON.stringify(editorForm.value) !== editorInitialSnapshot.value)
const canShowToc = computed(() => toc.value.length >= 4)
const shouldShowToc = computed(() => canShowToc.value && showTocPanel.value)
const searchHitMap = computed(() => {
  const map = new Map<string, SearchHit>()
  searchHits.value.forEach((hit) => map.set(hit.slug, hit))
  return map
})
const searchStatusLabel = computed(() => {
  const query = keyword.value.trim()
  if (!query) return '浏览全部教学文档'
  if (searchLoading.value) return `正在搜索“${query}”...`
  return filteredDocs.value.length
    ? `搜索“${query}”找到 ${filteredDocs.value.length} 篇文档`
    : `没有找到“${query}”相关文档`
})
const editorStatusLabel = computed(() => {
  if (saving.value) return '保存中...'
  if (editorAutosaving.value) return '自动保存中...'
  if (isEditorDirty.value) return '未保存修改'
  if (editorLastSavedAt.value) return `已保存 ${editorLastSavedAt.value}`
  return '已保存'
})

const formatDate = (value: string) => {
  if (!value) return '未知'
  return value.replace('T', ' ').replace('Z', '').slice(0, 16)
}

const formatOrder = (value: number) => String(value || 0).padStart(2, '0')
const formatDifficulty = (value: string) => difficultyLabelMap[value] || '入门'

const syncEditorSnapshot = () => {
  editorInitialSnapshot.value = JSON.stringify(editorForm.value)
}

const loadRecentSlugs = () => {
  if (typeof window === 'undefined') return
  try {
    const parsed = JSON.parse(window.localStorage.getItem(RECENT_DOCS_KEY) || '[]')
    recentSlugs.value = Array.isArray(parsed) ? parsed.filter((item) => typeof item === 'string').slice(0, 6) : []
  } catch {
    recentSlugs.value = []
  }
}

const persistRecentSlugs = () => {
  if (typeof window === 'undefined') return
  window.localStorage.setItem(RECENT_DOCS_KEY, JSON.stringify(recentSlugs.value.slice(0, 6)))
}

const recordRecentDoc = (slug: string) => {
  if (!slug) return
  recentSlugs.value = [slug, ...recentSlugs.value.filter((item) => item !== slug)].slice(0, 6)
  persistRecentSlugs()
}

const handleBeforeUnload = (event: BeforeUnloadEvent) => {
  if (!editorVisible.value || !isEditorDirty.value) return
  event.preventDefault()
  event.returnValue = ''
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

const fetchSearch = async (query: string) => {
  const normalized = query.trim()
  if (!normalized) {
    searchHits.value = []
    return
  }
  searchLoading.value = true
  try {
    const res: any = await request.get('/v1/system-docs/search', { params: { q: normalized } })
    searchHits.value = res.docs || []
  } catch (error: any) {
    ElMessage.error('搜索系统教学文档失败: ' + String(error?.message || error))
  } finally {
    searchLoading.value = false
  }
}

const fetchDoc = async (slug: string, mode: 'published' | 'draft' = 'published') => {
  if (!slug) return
  articleLoading.value = true
  try {
    const res: any = await request.get(`/v1/system-docs/entries/${slug}`, { params: { mode } })
    article.value = res
    activeSlug.value = res.slug
    recordRecentDoc(res.slug)
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
  latestUploadedImageUrl.value = ''
  editorFocusMode.value = false
  showEditorSettings.value = false
  editorLastSavedAt.value = ''
  isBootstrappingEditor.value = true
  editorForm.value = {
    title: '',
    slug: '',
    category: groupedDocs.value[0]?.category || '基础上手',
    author: '',
    summary: '',
    cover_image: '',
    difficulty: 'beginner',
    recommended_slugs: [],
    status: 'draft',
    order: docs.value.length + 1,
    content: '# 新文档\n\n请在这里编写内容。',
  }
  syncEditorSnapshot()
  editorVisible.value = true
  nextTick(() => {
    isBootstrappingEditor.value = false
  })
}

const openEditDialog = () => {
  if (!article.value) return
  articleLoading.value = true
  request.get(`/v1/system-docs/entries/${article.value.slug}`, { params: { mode: 'draft' } })
    .then(async (res: any) => {
      editingSlug.value = res.slug
      editorTab.value = 'edit'
      latestUploadedImageUrl.value = res.cover_image || ''
      editorFocusMode.value = false
      showEditorSettings.value = false
      editorLastSavedAt.value = ''
      isBootstrappingEditor.value = true
      editorForm.value = {
        title: res.title,
        slug: res.slug,
        category: res.category,
        author: res.author || '',
        summary: res.summary || '',
        cover_image: res.cover_image || '',
        difficulty: res.difficulty || 'beginner',
        recommended_slugs: [...(res.recommended_slugs || [])],
        status: res.status || 'published',
        order: res.order,
        content: res.content,
      }
      syncEditorSnapshot()
      editorVisible.value = true
      await nextTick()
      isBootstrappingEditor.value = false
    })
    .catch((error: any) => {
      ElMessage.error('加载编辑草稿失败: ' + String(error?.message || error))
    })
    .finally(() => {
      articleLoading.value = false
    })
}

const syncEditorResponse = (res: any) => {
  editingSlug.value = res.slug
  editorForm.value = {
    title: res.title,
    slug: res.slug,
    category: res.category,
    author: res.author || '',
    summary: res.summary || '',
    cover_image: res.cover_image || '',
    difficulty: res.difficulty || 'beginner',
    recommended_slugs: [...(res.recommended_slugs || [])],
    status: res.status || 'published',
    order: res.order,
    content: res.content || editorForm.value.content,
  }
  syncEditorSnapshot()
  editorLastSavedAt.value = formatDate(res.draft_updated_at || res.published_at || res.updated_at)
}

const saveDoc = async (saveMode: 'draft' | 'publish' = 'draft', options?: { silent?: boolean; keepOpen?: boolean }) => {
  const silent = Boolean(options?.silent)
  const keepOpen = Boolean(options?.keepOpen)
  if (!editorForm.value.title.trim()) {
    if (!silent) {
      ElMessage.warning('请输入文档标题')
    }
    return
  }
  if (!editorForm.value.content.trim()) {
    if (!silent) {
      ElMessage.warning('文档内容不能为空')
    }
    return
  }
  if (editorSaveTimer.value) {
    window.clearTimeout(editorSaveTimer.value)
    editorSaveTimer.value = null
  }
  if (saveMode === 'draft' && silent) {
    editorAutosaving.value = true
  } else {
    saving.value = true
  }
  try {
    const payload = {
      ...editorForm.value,
      title: editorForm.value.title.trim(),
      slug: editorForm.value.slug.trim(),
      category: editorForm.value.category.trim() || '基础上手',
      author: editorForm.value.author.trim(),
      summary: editorForm.value.summary.trim(),
      cover_image: editorForm.value.cover_image.trim(),
      difficulty: editorForm.value.difficulty,
      recommended_slugs: editorForm.value.recommended_slugs.filter((slug) => slug && slug !== editingSlug.value),
      content: editorForm.value.content,
      save_mode: saveMode,
    }
    const res: any = editingSlug.value
      ? await request.put(`/v1/system-docs/entries/${editingSlug.value}`, payload)
      : await request.post('/v1/system-docs/entries', payload)
    syncEditorResponse(res)
    await fetchTree()
    if (saveMode === 'publish') {
      if (!keepOpen) {
        editorVisible.value = false
      }
      await fetchDoc(res.slug)
    }
    if (!silent) {
      ElMessage.success(saveMode === 'publish' ? '文档已发布' : '草稿已保存')
    }
  } catch (error: any) {
    if (!silent) {
      ElMessage.error('保存失败: ' + String(error?.message || error))
    }
  } finally {
    saving.value = false
    editorAutosaving.value = false
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

const uploadImageFile = async (file: File) => {
  const textarea = editorTextareaRef.value?.textarea as HTMLTextAreaElement | undefined
  const insertionSelection = {
    start: textarea?.selectionStart ?? (editorForm.value.content || '').length,
    end: textarea?.selectionEnd ?? (editorForm.value.content || '').length,
    content: editorForm.value.content || '',
  }
  uploadingImage.value = true
  try {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('article_slug', editorForm.value.slug || editingSlug.value || 'system-doc')
    const res: any = await request.post('/v1/system-docs/upload-image', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 180000,
    })
    latestUploadedImageUrl.value = res.url || ''
    await insertTextAtSelection(res.markdown, insertionSelection)
    ElMessage.success('图片已上传并插入 Markdown')
    editorTab.value = 'edit'
  } catch (error: any) {
    ElMessage.error('图片上传失败: ' + String(error?.message || error))
  } finally {
    uploadingImage.value = false
  }
}

const handleImageUpload = async (uploadFile: UploadFile) => {
  if (!uploadFile.raw) return
  await uploadImageFile(uploadFile.raw)
}

const insertSnippet = async (snippet: string) => {
  editorTab.value = 'edit'
  const currentContent = editorForm.value.content || ''
  const textarea = editorTextareaRef.value?.textarea as HTMLTextAreaElement | undefined
  if (!textarea) {
    editorForm.value.content = `${currentContent.trim()}\n\n${snippet}`.trim()
    return
  }

  const start = textarea.selectionStart ?? currentContent.length
  const end = textarea.selectionEnd ?? currentContent.length
  const prefix = start > 0 && !currentContent.slice(0, start).endsWith('\n') ? '\n\n' : ''
  const suffix = end < currentContent.length && !currentContent.slice(end).startsWith('\n') ? '\n\n' : ''

  editorForm.value.content =
    currentContent.slice(0, start) +
    prefix +
    snippet +
    suffix +
    currentContent.slice(end)

  await nextTick()
  const nextCursor = start + prefix.length + snippet.length
  textarea.focus()
  textarea.setSelectionRange(nextCursor, nextCursor)
}

const wrapSelection = async (prefix: string, suffix = prefix, placeholder = '文本') => {
  editorTab.value = 'edit'
  const currentContent = editorForm.value.content || ''
  const textarea = editorTextareaRef.value?.textarea as HTMLTextAreaElement | undefined
  if (!textarea) {
    editorForm.value.content = `${currentContent}${prefix}${placeholder}${suffix}`
    return
  }
  const start = textarea.selectionStart ?? currentContent.length
  const end = textarea.selectionEnd ?? currentContent.length
  const selected = currentContent.slice(start, end) || placeholder
  editorForm.value.content =
    currentContent.slice(0, start) +
    prefix +
    selected +
    suffix +
    currentContent.slice(end)
  await nextTick()
  const cursorEnd = start + prefix.length + selected.length + suffix.length
  textarea.focus()
  textarea.setSelectionRange(cursorEnd, cursorEnd)
}

const insertTextAtSelection = async (
  insertedText: string,
  selection?: { start: number; end: number; content: string },
) => {
  editorTab.value = 'edit'
  const textarea = editorTextareaRef.value?.textarea as HTMLTextAreaElement | undefined
  const currentContent = selection?.content ?? editorForm.value.content ?? ''
  const start = selection?.start ?? textarea?.selectionStart ?? currentContent.length
  const end = selection?.end ?? textarea?.selectionEnd ?? currentContent.length
  const prefix = start > 0 && !currentContent.slice(0, start).endsWith('\n') ? '\n\n' : ''
  const suffix = end < currentContent.length && !currentContent.slice(end).startsWith('\n') ? '\n\n' : ''

  editorForm.value.content =
    currentContent.slice(0, start) +
    prefix +
    insertedText +
    suffix +
    currentContent.slice(end)

  await nextTick()
  const nextCursor = start + prefix.length + insertedText.length
  if (textarea) {
    textarea.focus()
    textarea.setSelectionRange(nextCursor, nextCursor)
  }
}

const useLatestUploadedImageAsCover = () => {
  if (!latestUploadedImageUrl.value) return
  editorForm.value.cover_image = latestUploadedImageUrl.value
  ElMessage.success('已将最近上传图片设为封面图')
}

const requestCloseEditor = async () => {
  if (!editorVisible.value) return
  if (editorSaveTimer.value) {
    window.clearTimeout(editorSaveTimer.value)
    editorSaveTimer.value = null
  }
  if (!isEditorDirty.value) {
    editorVisible.value = false
    return
  }
  try {
    await ElMessageBox.confirm('当前文档有未保存修改，确认要关闭编辑器吗？', '未保存的内容', {
      type: 'warning',
      confirmButtonText: '仍然关闭',
      cancelButtonText: '继续编辑',
    })
    editorVisible.value = false
  } catch {
    // keep editing
  }
}

const handleEditorDialogBeforeClose = async (done: () => void) => {
  if (editorSaveTimer.value) {
    window.clearTimeout(editorSaveTimer.value)
    editorSaveTimer.value = null
  }
  if (!isEditorDirty.value) {
    done()
    return
  }
  try {
    await ElMessageBox.confirm('当前文档有未保存修改，确认要关闭编辑器吗？', '未保存的内容', {
      type: 'warning',
      confirmButtonText: '仍然关闭',
      cancelButtonText: '继续编辑',
    })
    done()
  } catch {
    // keep editing
  }
}

const scrollToHeading = (id: string) => {
  const element = document.getElementById(id)
  element?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

const scrollEditorOutlineIntoView = (headingId: string) => {
  if (editorTab.value !== 'preview') {
    editorTab.value = 'preview'
    nextTick(() => {
      const target = editorPreviewRef.value?.querySelector(`#${CSS.escape(headingId)}`) as HTMLElement | null
      target?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    })
    return
  }
  const target = editorPreviewRef.value?.querySelector(`#${CSS.escape(headingId)}`) as HTMLElement | null
  target?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

const handleEditorKeydown = async (event: KeyboardEvent) => {
  if (!editorVisible.value) return
  if (!(event.ctrlKey || event.metaKey)) return
  const key = event.key.toLowerCase()
  if (key === 's') {
    event.preventDefault()
    await saveDoc('draft')
    return
  }
  if (editorTab.value !== 'edit') return
  if (key === 'b') {
    event.preventDefault()
    await wrapSelection('**')
  } else if (key === 'i') {
    event.preventDefault()
    await wrapSelection('*')
  } else if (key === 'k') {
    event.preventDefault()
    await wrapSelection('[', '](https://example.com)', '链接文字')
  } else if (key === '/') {
    event.preventDefault()
    ElMessage.info('快捷键：Ctrl/Cmd + S 保存，Ctrl/Cmd + B/I/K 插入常用 Markdown')
  }
}

const bindEditorTransferEvents = () => {
  const textarea = editorTextareaRef.value?.textarea as HTMLTextAreaElement | undefined
  if (!textarea) return
  textarea.ondrop = async (event: DragEvent) => {
    const file = event.dataTransfer?.files?.[0]
    if (!file || !file.type.startsWith('image/')) return
    event.preventDefault()
    await uploadImageFile(file)
  }
  textarea.onpaste = async (event: ClipboardEvent) => {
    const items = Array.from(event.clipboardData?.items || [])
    const imageItem = items.find((item) => item.type.startsWith('image/'))
    const file = imageItem?.getAsFile()
    if (!file) return
    event.preventDefault()
    await uploadImageFile(file)
  }
}

onMounted(async () => {
  window.addEventListener('beforeunload', handleBeforeUnload)
  window.addEventListener('keydown', handleEditorKeydown)
  loadRecentSlugs()
  await fetchTree()
  if (activeSlug.value) {
    await fetchDoc(activeSlug.value)
  }
})

onBeforeUnmount(() => {
  window.removeEventListener('beforeunload', handleBeforeUnload)
  window.removeEventListener('keydown', handleEditorKeydown)
  if (editorSaveTimer.value) {
    window.clearTimeout(editorSaveTimer.value)
  }
  if (keywordSearchTimer.value) {
    window.clearTimeout(keywordSearchTimer.value)
  }
})

watch(toc, (value) => {
  showTocPanel.value = value.length >= 4
}, { immediate: true })

watch(keyword, (value) => {
  if (keywordSearchTimer.value) {
    window.clearTimeout(keywordSearchTimer.value)
    keywordSearchTimer.value = null
  }
  if (!value.trim()) {
    searchHits.value = []
    return
  }
  keywordSearchTimer.value = window.setTimeout(() => {
    fetchSearch(value)
  }, 220)
})

watch(
  () => [editorVisible.value, editorTab.value],
  async ([visible, tab]) => {
    if (!visible || tab !== 'edit') return
    await nextTick()
    bindEditorTransferEvents()
  },
)

watch(
  editorForm,
  () => {
    if (!editorVisible.value || isBootstrappingEditor.value || !isEditorDirty.value) return
    if (!editorForm.value.title.trim() || !editorForm.value.content.trim()) return
    if (editorSaveTimer.value) {
      window.clearTimeout(editorSaveTimer.value)
    }
    editorSaveTimer.value = window.setTimeout(() => {
      saveDoc('draft', { silent: true, keepOpen: true })
    }, AUTOSAVE_DELAY_MS)
  },
  { deep: true },
)
</script>

<style scoped src="./styles/systemTeaching.css"></style>
