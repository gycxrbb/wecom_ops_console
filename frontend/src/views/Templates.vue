<template>
  <div class="templates-page" v-loading="loading">
    <section class="templates-hero">
      <div class="templates-hero__main">
        <span class="section-kicker">Template Library</span>
        <h2>模板中心</h2>
        <p>把系统母版和你的可发送模板拆开看，先按消息类型筛，再沿着最近更新快速回到手头内容。</p>
        <div class="hero-metrics">
          <div class="hero-metric">
            <span class="hero-metric__label">模板总数</span>
            <strong>{{ templates.length }}</strong>
          </div>
          <div class="hero-metric">
            <span class="hero-metric__label">我的模板</span>
            <strong>{{ mineTemplates.length }}</strong>
          </div>
          <div class="hero-metric">
            <span class="hero-metric__label">系统母版</span>
            <strong>{{ systemTemplates.length }}</strong>
          </div>
        </div>
      </div>
      <div class="templates-hero__aside">
        <div class="hero-note">
          <span class="hero-note__label">当前筛选</span>
          <strong>{{ currentTypeLabel }}</strong>
          <p>{{ searchKeyword ? `正在搜索“${searchKeyword}”` : '未输入关键词，展示全部可见模板。' }}</p>
        </div>
        <el-button type="primary" size="large" @click="openCreate">新增我的模板</el-button>
      </div>
    </section>

    <section class="toolbar-panel">
      <div class="toolbar-panel__top">
        <el-input
          v-model="searchKeyword"
          placeholder="搜索模板名称、分类或描述"
          clearable
          :prefix-icon="Search"
          class="toolbar-search"
        />
        <div class="toolbar-summary">
          <span>{{ filteredMineTemplates.length }} 个我的模板</span>
          <span>{{ filteredSystemTemplates.length }} 个系统模板</span>
        </div>
      </div>

      <div class="type-filter">
        <button
          v-for="item in typeTabs"
          :key="item.value"
          type="button"
          class="type-filter__chip"
          :class="{ 'type-filter__chip--active': activeType === item.value }"
          @click="activeType = item.value"
        >
          <span>{{ item.label }}</span>
          <span class="type-filter__count">{{ item.count }}</span>
        </button>
      </div>
    </section>

    <section v-if="recentMineTemplates.length" class="recent-strip">
      <div class="recent-strip__header">
        <div>
          <span class="section-kicker">Recent</span>
          <h3>最近更新</h3>
        </div>
        <span class="recent-strip__hint">点击卡片可自动定位到下方对应模板</span>
      </div>
      <div class="recent-strip__list">
        <button
          v-for="tpl in recentMineTemplates"
          :key="tpl.id"
          type="button"
          class="recent-card"
          @click="focusTemplateCard(tpl.id, tpl.msg_type)"
        >
          <span class="recent-card__type">{{ msgTypeLabel(tpl.msg_type) }}</span>
          <strong>{{ tpl.name }}</strong>
          <span class="recent-card__meta">{{ tpl.category || '未分类' }} · {{ formatDate(tpl.updated_at) }}</span>
        </button>
      </div>
    </section>

    <div class="workspace-grid">
      <section class="library-panel library-panel--mine">
        <div class="library-panel__header">
          <div>
            <span class="section-kicker section-kicker--green">Direct Use</span>
            <h3>我的可发送模板</h3>
            <p>适合直接发送，或在当前内容上继续做微调。</p>
          </div>
          <el-tag type="success" effect="plain" round>{{ filteredMineTemplates.length }} 个</el-tag>
        </div>

        <div v-if="filteredMineTemplates.length" class="template-grid template-grid--mine">
          <article
            v-for="tpl in filteredMineTemplates"
            :key="tpl.id"
            :data-template-id="tpl.id"
            class="template-card template-card--mine"
            :class="{ 'template-card--highlighted': highlightedTemplateId === tpl.id }"
          >
            <div class="template-card__head">
              <div>
                <div class="template-card__title">
                  <h4>{{ tpl.name }}</h4>
                  <el-tag size="small" effect="plain" type="success">我的</el-tag>
                </div>
                <div class="template-card__meta">
                  <span>{{ msgTypeLabel(tpl.msg_type) }}</span>
                  <span>{{ tpl.category || '未分类' }}</span>
                  <span>{{ formatDate(tpl.updated_at) }}</span>
                </div>
              </div>
            </div>

            <div class="template-card__preview">
              <p>{{ tpl.description || contentSummary(tpl) }}</p>
            </div>

            <div class="template-card__actions">
              <el-button type="primary" link @click="editTemplate(tpl)">编辑</el-button>
              <el-button type="primary" link @click="cloneTemplate(tpl)">复制</el-button>
              <el-button type="danger" link @click="deleteTemplate(tpl)">删除</el-button>
            </div>
          </article>
        </div>

        <el-empty
          v-else
          :description="searchKeyword ? '没有匹配到你的模板。' : '这个消息类型下还没有你的模板，可以从右侧系统母版开始。'"
        />
      </section>

      <section class="library-panel library-panel--system">
        <div class="library-panel__header">
          <div>
            <span class="section-kicker section-kicker--blue">Starting Point</span>
            <h3>系统模板库</h3>
            <p>作为起点使用，保存后会出现在左侧“我的可发送模板”。</p>
          </div>
          <el-tag effect="plain" round>{{ filteredSystemTemplates.length }} 个</el-tag>
        </div>

        <div v-if="filteredSystemTemplates.length" class="template-grid template-grid--system">
          <article
            v-for="tpl in filteredSystemTemplates"
            :key="tpl.id"
            class="template-card template-card--system"
          >
            <div class="template-card__head">
              <div>
                <div class="template-card__title">
                  <h4>{{ tpl.name }}</h4>
                  <el-tag size="small" effect="plain">系统</el-tag>
                </div>
                <div class="template-card__meta">
                  <span>{{ msgTypeLabel(tpl.msg_type) }}</span>
                  <span>{{ tpl.category || '未分类' }}</span>
                  <span>{{ formatDate(tpl.updated_at) }}</span>
                </div>
              </div>
            </div>

            <div class="template-card__preview">
              <p>{{ tpl.description || contentSummary(tpl) }}</p>
            </div>

            <div class="template-card__actions">
              <el-button type="primary" link @click="createFromTemplate(tpl)">基于此创建</el-button>
              <el-button type="primary" link @click="cloneTemplate(tpl)">复制到我的模板</el-button>
            </div>
          </article>
        </div>

        <el-empty
          v-else
          :description="searchKeyword ? '没有匹配到系统模板。' : '这个消息类型下暂时没有系统模板。'"
        />
      </section>
    </div>

    <el-dialog v-model="dialogVisible" :title="form.id ? '编辑模板' : '新增模板'" width="70%" top="5vh">
      <el-form label-width="100px">
        <el-form-item label="模板名称">
          <el-input v-model="form.name" placeholder="输入模板名称" />
        </el-form-item>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="分类">
              <el-input v-model="form.category" placeholder="例如：训练营 / 日报 / 通知" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="描述">
              <el-input v-model="form.description" placeholder="给团队看的备注，可选" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="消息类型">
          <el-select v-model="form.msg_type" @change="handleMsgTypeChange" style="width: 220px">
            <el-option
              v-for="item in msgTypeOptions"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="模板内容">
          <MessageEditor
            v-model="form.contentJson"
            :msg-type="form.msg_type"
            v-model:variables="form.variablesJson"
            :show-variables="supportsVariables(form.msg_type)"
            style="width: 100%"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveTemplate">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref } from 'vue'
import { Search } from '@element-plus/icons-vue'
import request from '@/utils/request'
import { ElMessage, ElMessageBox } from 'element-plus'
import MessageEditor from '@/components/message-editor/index.vue'
import { CRM_DEMO_URL, createTemplateCardExample, templateCardExampleVariables } from '@/components/message-editor/templateCardPresets'

type TemplateItem = {
  id: number
  name: string
  category?: string
  msg_type: string
  description?: string
  content_json?: Record<string, any>
  content?: Record<string, any> | string
  variables_json?: Record<string, any>
  variable_schema?: Record<string, any> | string
  is_system?: boolean
  updated_at?: string
}

const templates = ref<TemplateItem[]>([])
const loading = ref(false)
const dialogVisible = ref(false)
const activeType = ref('all')
const searchKeyword = ref('')
const highlightedTemplateId = ref<number | null>(null)

const msgTypeOptions = [
  { value: 'text', label: '文本' },
  { value: 'markdown', label: 'Markdown' },
  { value: 'image', label: '图片' },
  { value: 'news', label: '图文' },
  { value: 'file', label: '文件' },
  { value: 'voice', label: '语音' },
  { value: 'template_card', label: '模板卡片' }
]

const defaultContentByType: Record<string, any> = {
  text: { content: '', mentioned_list: [], mentioned_mobile_list: [] },
  markdown: { content: '' },
  news: {
    articles: [
      {
        title: '惯能 H5 · 今日内容导读',
        description: '打开 CRM 内容页查看今天的 H5 讲解示例，运营同学可直接改标题、描述和封面图。',
        url: CRM_DEMO_URL,
        picurl: 'https://picsum.photos/seed/guanneng-h5-news/640/360',
      },
    ],
  },
  image: { asset_id: undefined, asset_name: '', asset_url: '', image_path: '' },
  file: { asset_id: undefined, asset_name: '', media_id: '' },
  voice: { asset_id: undefined, asset_name: '', media_id: '' },
  template_card: createTemplateCardExample('text_notice')
}

const defaultVariablesByType: Record<string, any> = {
  template_card: { ...templateCardExampleVariables.text_notice }
}

const variableEnabledTypes = new Set(['text', 'markdown', 'news', 'template_card'])

const form = reactive({
  id: null as number | null,
  name: '',
  description: '',
  msg_type: 'text',
  category: 'general',
  contentJson: { ...defaultContentByType.text },
  variablesJson: {} as Record<string, any>
})

const msgTypeLabel = (type: string) => {
  const match = msgTypeOptions.find(item => item.value === type)
  return match?.label || type
}

const supportsVariables = (msgType: string) => variableEnabledTypes.has(msgType)

const matchesKeyword = (tpl: TemplateItem) => {
  const keyword = searchKeyword.value.trim().toLowerCase()
  if (!keyword) return true
  return [tpl.name, tpl.category, tpl.description]
    .filter(Boolean)
    .some(value => String(value).toLowerCase().includes(keyword))
}

const mineTemplates = computed(() => templates.value.filter(tpl => !tpl.is_system))
const systemTemplates = computed(() => templates.value.filter(tpl => !!tpl.is_system))

const typeTabs = computed(() => {
  const items = msgTypeOptions.map(item => ({
    value: item.value,
    label: item.label,
    count: templates.value.filter(tpl => tpl.msg_type === item.value).length
  }))
  return [{ value: 'all', label: '全部', count: templates.value.length }, ...items]
})

const currentTypeLabel = computed(() => {
  const current = typeTabs.value.find(item => item.value === activeType.value)
  return current?.label || '全部'
})

const filteredTemplates = computed(() => (
  templates.value.filter(tpl => {
    const typeMatched = activeType.value === 'all' || tpl.msg_type === activeType.value
    return typeMatched && matchesKeyword(tpl)
  })
))

const filteredMineTemplates = computed(() => (
  filteredTemplates.value
    .filter(tpl => !tpl.is_system)
    .sort((a, b) => String(b.updated_at || '').localeCompare(String(a.updated_at || '')))
))

const filteredSystemTemplates = computed(() => (
  filteredTemplates.value
    .filter(tpl => !!tpl.is_system)
    .sort((a, b) => String(b.updated_at || '').localeCompare(String(a.updated_at || '')))
))

const recentMineTemplates = computed(() => (
  mineTemplates.value
    .filter(tpl => matchesKeyword(tpl))
    .sort((a, b) => String(b.updated_at || '').localeCompare(String(a.updated_at || '')))
    .slice(0, 4)
))

const fetchTemplates = async () => {
  loading.value = true
  try {
    const res = await request.get('/v1/templates')
    templates.value = res.list || res
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

const resetForm = () => {
  form.id = null
  form.name = ''
  form.description = ''
  form.msg_type = 'text'
  form.category = 'general'
  form.contentJson = { ...defaultContentByType.text }
  form.variablesJson = {}
}

const openCreate = () => {
  resetForm()
  dialogVisible.value = true
}

const fillForm = (row: TemplateItem, nextId: number | null) => {
  form.id = nextId
  form.name = nextId ? `${row.name} - 我的版本` : row.name
  form.description = row.description || ''
  form.msg_type = row.msg_type
  form.category = row.category || 'general'

  const rawContent = row.content_json ?? row.content
  try {
    form.contentJson = typeof rawContent === 'string'
      ? JSON.parse(rawContent)
      : (rawContent || { ...(defaultContentByType[row.msg_type] || {}) })
  } catch {
    form.contentJson = { ...(defaultContentByType[row.msg_type] || {}) }
  }

  const rawVars = row.variables_json ?? row.variable_schema
  try {
    form.variablesJson = typeof rawVars === 'string' ? JSON.parse(rawVars) : (rawVars || {})
  } catch {
    form.variablesJson = {}
  }
}

const editTemplate = (row: TemplateItem) => {
  fillForm(row, row.id)
  dialogVisible.value = true
}

const createFromTemplate = (row: TemplateItem) => {
  fillForm(row, null)
  dialogVisible.value = true
}

const handleMsgTypeChange = (type: string) => {
  form.contentJson = { ...(defaultContentByType[type] || {}) }
  form.variablesJson = supportsVariables(type)
    ? { ...(defaultVariablesByType[type] || {}) }
    : {}
}

const focusTemplateCard = async (id: number, msgType: string) => {
  activeType.value = msgType
  highlightedTemplateId.value = id
  await nextTick()
  const el = document.querySelector<HTMLElement>(`[data-template-id="${id}"]`)
  el?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  window.setTimeout(() => {
    if (highlightedTemplateId.value === id) {
      highlightedTemplateId.value = null
    }
  }, 2600)
}

const cloneTemplate = async (row: TemplateItem) => {
  try {
    const saved = await request.post(`/v1/templates/${row.id}/clone`)
    await fetchTemplates()
    ElMessage.success('已复制到我的模板')
    await focusTemplateCard(saved.id, saved.msg_type)
  } catch (e) {
    console.error(e)
  }
}

const deleteTemplate = (row: TemplateItem) => {
  ElMessageBox.confirm('确认删除该模板？', '警告', { type: 'warning' }).then(async () => {
    await request.delete(`/v1/templates/${row.id}`)
    ElMessage.success('删除成功')
    fetchTemplates()
  })
}

const saveTemplate = async () => {
  if (!form.name.trim()) {
    return ElMessage.warning('请输入模板名称')
  }
  try {
    const saved = await request.post('/v1/templates', {
      id: form.id,
      name: form.name,
      description: form.description,
      category: form.category,
      msg_type: form.msg_type,
      content_json: form.contentJson,
      variables_json: form.variablesJson
    })
    dialogVisible.value = false
    await fetchTemplates()
    ElMessage.success('保存成功')
    await focusTemplateCard(saved.id, saved.msg_type)
  } catch (e) {
    console.error(e)
  }
}

const formatDate = (value?: string) => {
  if (!value) return '刚刚更新'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '刚刚更新'
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

const contentSummary = (tpl: TemplateItem) => {
  const raw = tpl.content_json ?? tpl.content
  const content = typeof raw === 'string' ? raw : JSON.stringify(raw || {})
  const compact = content.replace(/\s+/g, ' ').trim()
  return compact.length > 88 ? `${compact.slice(0, 88)}...` : compact || '暂无描述'
}

onMounted(() => {
  fetchTemplates()
})
</script>

<style scoped>
.templates-page {
  --surface-1: linear-gradient(180deg, rgba(255, 255, 255, 0.92), rgba(255, 255, 255, 0.86));
  --surface-2: linear-gradient(180deg, rgba(248, 250, 252, 0.95), rgba(255, 255, 255, 0.92));
  --hero-glow: radial-gradient(circle at top left, rgba(34, 197, 94, 0.16), transparent 36%);
  --panel-border: rgba(148, 163, 184, 0.22);
  --soft-border: rgba(148, 163, 184, 0.18);
  --muted-surface: rgba(248, 250, 252, 0.82);
  --preview-surface: rgba(15, 23, 42, 0.03);
  --blue-tint: rgba(37, 99, 235, 0.08);
  --green-tint: rgba(34, 197, 94, 0.08);
  padding: 28px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.section-kicker {
  display: inline-flex;
  align-items: center;
  min-height: 28px;
  padding: 0 12px;
  border-radius: 999px;
  background: rgba(37, 99, 235, 0.08);
  color: #1d4ed8;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.section-kicker--green {
  background: rgba(34, 197, 94, 0.12);
  color: #15803d;
}

.section-kicker--blue {
  background: rgba(59, 130, 246, 0.1);
  color: #1d4ed8;
}

.templates-hero,
.toolbar-panel,
.recent-strip,
.library-panel {
  border: 1px solid var(--panel-border);
  background: var(--surface-1);
  box-shadow: 0 18px 40px rgba(15, 23, 42, 0.06);
  backdrop-filter: blur(14px);
}

.templates-hero {
  display: grid;
  grid-template-columns: minmax(0, 1.3fr) minmax(240px, 0.7fr);
  gap: 18px;
  padding: 26px 28px;
  border-radius: 28px;
  background-image: var(--hero-glow), var(--surface-1);
}

.templates-hero__main h2 {
  margin: 14px 0 10px;
  font-size: 34px;
  line-height: 1.05;
  letter-spacing: -0.03em;
  color: var(--text-primary);
}

.templates-hero__main p {
  max-width: 62ch;
  margin: 0;
  color: var(--text-secondary);
  font-size: 15px;
  line-height: 1.7;
}

.hero-metrics {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 20px;
}

.hero-metric {
  min-width: 116px;
  padding: 14px 16px;
  border-radius: 18px;
  border: 1px solid var(--soft-border);
  background: rgba(255, 255, 255, 0.72);
}

.hero-metric__label {
  display: block;
  color: var(--text-muted);
  font-size: 12px;
  margin-bottom: 8px;
}

.hero-metric strong {
  color: var(--text-primary);
  font-size: 24px;
  line-height: 1;
}

.templates-hero__aside {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  gap: 16px;
}

.hero-note {
  padding: 18px;
  border-radius: 22px;
  border: 1px solid var(--soft-border);
  background: rgba(255, 255, 255, 0.74);
}

.hero-note__label {
  display: block;
  color: var(--text-muted);
  font-size: 12px;
  margin-bottom: 10px;
}

.hero-note strong {
  display: block;
  color: var(--text-primary);
  font-size: 18px;
}

.hero-note p {
  margin: 10px 0 0;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.65;
}

.toolbar-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 18px;
  border-radius: 24px;
}

.toolbar-panel__top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.toolbar-search {
  max-width: 420px;
}

.toolbar-search :deep(.el-input__wrapper) {
  min-height: 46px;
  border-radius: 16px;
  box-shadow: none;
  background: var(--muted-surface);
}

.toolbar-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  color: var(--text-secondary);
  font-size: 13px;
}

.toolbar-summary span {
  padding: 8px 12px;
  border-radius: 999px;
  background: var(--preview-surface);
}

.type-filter {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.type-filter__chip {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-height: 44px;
  padding: 0 14px;
  border: 1px solid transparent;
  border-radius: 14px;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  transition: transform 0.2s ease, background-color 0.2s ease, color 0.2s ease, box-shadow 0.2s ease;
}

.type-filter__chip:hover {
  transform: translateY(-1px);
  background: var(--preview-surface);
  color: var(--text-primary);
}

.type-filter__chip--active {
  background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
  color: #fff;
  box-shadow: 0 12px 24px rgba(37, 99, 235, 0.24);
}

.type-filter__count {
  min-width: 24px;
  padding: 2px 7px;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.16);
  font-size: 12px;
}

.type-filter__chip--active .type-filter__count {
  background: rgba(255, 255, 255, 0.18);
}

.recent-strip {
  padding: 18px 20px 20px;
  border-radius: 24px;
}

.recent-strip__header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-end;
  margin-bottom: 16px;
}

.recent-strip__header h3 {
  margin: 10px 0 0;
  font-size: 22px;
  color: var(--text-primary);
}

.recent-strip__hint {
  color: var(--text-muted);
  font-size: 12px;
}

.recent-strip__list {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 14px;
}

.recent-card {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 10px;
  min-height: 124px;
  padding: 16px;
  border: 1px solid var(--soft-border);
  border-radius: 20px;
  background: var(--surface-2);
  cursor: pointer;
  text-align: left;
  transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;
}

.recent-card:hover {
  transform: translateY(-2px);
  border-color: rgba(59, 130, 246, 0.28);
  box-shadow: 0 16px 26px rgba(37, 99, 235, 0.08);
}

.recent-card__type {
  display: inline-flex;
  min-height: 28px;
  padding: 0 10px;
  border-radius: 999px;
  align-items: center;
  background: var(--blue-tint);
  color: #2563eb;
  font-size: 12px;
  font-weight: 600;
}

.recent-card strong {
  color: var(--text-primary);
  font-size: 15px;
  line-height: 1.4;
}

.recent-card__meta {
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.5;
}

.workspace-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.15fr) minmax(320px, 0.85fr);
  gap: 18px;
  align-items: start;
}

.library-panel {
  padding: 22px;
  border-radius: 26px;
}

.library-panel--mine {
  background-image:
    radial-gradient(circle at top left, rgba(34, 197, 94, 0.09), transparent 38%),
    var(--surface-1);
}

.library-panel--system {
  position: sticky;
  top: 20px;
  background-image:
    radial-gradient(circle at top right, rgba(59, 130, 246, 0.08), transparent 36%),
    var(--surface-1);
}

.library-panel__header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 18px;
}

.library-panel__header h3 {
  margin: 12px 0 8px;
  font-size: 28px;
  line-height: 1.1;
  color: var(--text-primary);
}

.library-panel__header p {
  margin: 0;
  color: var(--text-secondary);
  font-size: 14px;
  line-height: 1.7;
}

.template-grid {
  display: grid;
  gap: 14px;
}

.template-grid--mine {
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
}

.template-grid--system {
  grid-template-columns: 1fr;
}

.template-card {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 18px;
  border-radius: 22px;
  border: 1px solid var(--soft-border);
  background: var(--surface-2);
  transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;
}

.template-card:hover {
  transform: translateY(-2px);
  border-color: rgba(59, 130, 246, 0.24);
  box-shadow: 0 16px 28px rgba(15, 23, 42, 0.07);
}

.template-card--highlighted {
  border-color: rgba(34, 197, 94, 0.45);
  box-shadow: 0 0 0 4px rgba(34, 197, 94, 0.12), 0 18px 30px rgba(34, 197, 94, 0.12);
}

.template-card__title {
  display: flex;
  align-items: center;
  gap: 8px;
}

.template-card__title h4 {
  margin: 0;
  font-size: 18px;
  color: var(--text-primary);
  line-height: 1.3;
}

.template-card__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
}

.template-card__meta span {
  display: inline-flex;
  align-items: center;
  min-height: 28px;
  padding: 0 10px;
  border-radius: 999px;
  background: var(--preview-surface);
  color: var(--text-secondary);
  font-size: 12px;
}

.template-card__preview {
  padding: 14px 15px;
  border-radius: 16px;
  background: var(--preview-surface);
  border: 1px solid rgba(148, 163, 184, 0.12);
}

.template-card__preview p {
  margin: 0;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.75;
  word-break: break-word;
}

.template-card__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 12px;
  padding-top: 4px;
}

:global(html.dark) .templates-page {
  --surface-1: linear-gradient(180deg, rgba(30, 32, 35, 0.96), rgba(24, 26, 28, 0.92));
  --surface-2: linear-gradient(180deg, rgba(34, 37, 40, 0.96), rgba(26, 28, 30, 0.92));
  --hero-glow: radial-gradient(circle at top left, rgba(34, 197, 94, 0.12), transparent 36%);
  --panel-border: rgba(100, 116, 139, 0.28);
  --soft-border: rgba(100, 116, 139, 0.24);
  --muted-surface: rgba(17, 24, 39, 0.72);
  --preview-surface: rgba(255, 255, 255, 0.04);
  --blue-tint: rgba(59, 130, 246, 0.16);
  --green-tint: rgba(34, 197, 94, 0.14);
}

:global(html.dark) .hero-metric,
:global(html.dark) .hero-note {
  background: rgba(17, 24, 39, 0.4);
}

:global(html.dark) .templates-hero,
:global(html.dark) .toolbar-panel,
:global(html.dark) .recent-strip,
:global(html.dark) .library-panel {
  background: var(--surface-1);
  box-shadow: 0 18px 40px rgba(0, 0, 0, 0.24);
}

:global(html.dark) .recent-card,
:global(html.dark) .template-card {
  background: var(--surface-2);
  border-color: rgba(100, 116, 139, 0.26);
  box-shadow: 0 12px 28px rgba(0, 0, 0, 0.18);
}

:global(html.dark) .recent-card:hover,
:global(html.dark) .template-card:hover {
  box-shadow: 0 18px 32px rgba(0, 0, 0, 0.28);
}

:global(html.dark) .recent-card__type {
  background: rgba(59, 130, 246, 0.18);
  color: #93c5fd;
}

:global(html.dark) .section-kicker {
  background: rgba(59, 130, 246, 0.16);
  color: #93c5fd;
}

:global(html.dark) .section-kicker--green {
  background: rgba(34, 197, 94, 0.16);
  color: #86efac;
}

:global(html.dark) .section-kicker--blue {
  background: rgba(59, 130, 246, 0.16);
  color: #93c5fd;
}

:global(html.dark) .toolbar-search :deep(.el-input__wrapper) {
  background: rgba(17, 24, 39, 0.72);
}

:global(html.dark) .toolbar-summary span,
:global(html.dark) .template-card__meta span,
:global(html.dark) .template-card__preview {
  background: rgba(255, 255, 255, 0.04);
}

:global(html.dark) .type-filter__chip:hover {
  background: rgba(255, 255, 255, 0.05);
}

:global(html.dark) .el-empty__description p {
  color: var(--text-secondary);
}

@media (max-width: 1180px) {
  .templates-hero,
  .workspace-grid {
    grid-template-columns: 1fr;
  }

  .library-panel--system {
    position: static;
  }
}

@media (max-width: 760px) {
  .templates-page {
    padding: 16px;
  }

  .templates-hero,
  .toolbar-panel,
  .recent-strip,
  .library-panel {
    padding: 18px;
    border-radius: 22px;
  }

  .templates-hero__main h2,
  .library-panel__header h3 {
    font-size: 26px;
  }

  .toolbar-panel__top,
  .recent-strip__header,
  .library-panel__header {
    flex-direction: column;
    align-items: stretch;
  }

  .toolbar-search {
    max-width: none;
  }

  .template-grid--mine {
    grid-template-columns: 1fr;
  }
}

@media (prefers-reduced-motion: reduce) {
  .type-filter__chip,
  .recent-card,
  .template-card {
    transition: none;
  }
}
</style>
