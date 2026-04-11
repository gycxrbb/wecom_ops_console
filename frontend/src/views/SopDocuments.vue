<template>
  <div class="sop-page">
    <div class="sop-hero">
      <div>
        <div class="sop-hero__eyebrow">Operation SOP</div>
        <h1 class="sop-hero__title">飞书文档</h1>
      </div>
      <el-button v-if="isAdmin" type="primary" size="large" @click="openCreate">新增文档</el-button>
    </div>

    <div class="sop-filter-bar">
      <div class="sop-filter-chips">
        <button
          v-for="cat in ['全部', ...categories]"
          :key="cat"
          type="button"
          class="sop-filter-chip"
          :class="{ 'is-active': activeCategory === cat }"
          @click="activeCategory = cat"
        >
          {{ cat }}
        </button>
      </div>
      <el-input
        v-model="searchKeyword"
        placeholder="搜索文档标题..."
        clearable
        :prefix-icon="Search"
        style="width: 240px"
      />
    </div>

    <div v-if="filteredDocs.length" class="sop-doc-grid">
      <div
        v-for="doc in filteredDocs"
        :key="doc.id"
        class="sop-doc-card"
        @click="openDoc(doc)"
      >
        <div class="sop-doc-card__head">
          <span class="sop-doc-card__category">{{ doc.category }}</span>
          <span class="sop-doc-card__time">{{ formatDate(doc.updated_at) }}</span>
        </div>
        <h4 class="sop-doc-card__title">{{ doc.title }}</h4>
        <p v-if="doc.description" class="sop-doc-card__desc">{{ doc.description }}</p>
        <div v-if="isAdmin" class="sop-doc-card__actions" @click.stop>
          <el-button link type="primary" @click="openEdit(doc)">编辑</el-button>
          <el-button link type="danger" @click="deleteDoc(doc)">删除</el-button>
        </div>
      </div>
    </div>
    <el-empty v-else :image-size="80" description="暂无SOP文档" />

    <el-dialog v-model="dialogVisible" :title="form.id ? '编辑文档' : '新增文档'" width="520px">
      <el-form label-width="80px">
        <el-form-item label="文档标题">
          <el-input v-model="form.title" placeholder="例如：CCM营养干预SOP" />
        </el-form-item>
        <el-form-item label="分类">
          <el-select v-model="form.category" style="width: 100%">
            <el-option v-for="cat in categories" :key="cat" :label="cat" :value="cat" />
          </el-select>
        </el-form-item>
        <el-form-item label="文档链接">
          <el-input v-model="form.url" placeholder="粘贴飞书文档链接" />
        </el-form-item>
        <el-form-item label="简短描述">
          <el-input v-model="form.description" type="textarea" :rows="3" placeholder="可选，给团队看的备注" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveDoc">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script lang="ts">
export default { name: 'SopDocuments' }
</script>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { Search } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useUserStore } from '@/stores/user'
import request from '@/utils/request'

interface SopDoc {
  id: number
  title: string
  category: string
  url: string
  description: string
  sort_order: number
  created_by: number | null
  created_at: string
  updated_at: string
}

const userStore = useUserStore()
const isAdmin = computed(() => userStore.user?.role === 'admin')

const docs = ref<SopDoc[]>([])
const categories = ['运营流程', '话术库', '营养知识', '培训手册', '其他']
const activeCategory = ref('全部')
const searchKeyword = ref('')
const dialogVisible = ref(false)
const form = reactive({ id: null as number | null, title: '', category: '运营流程', url: '', description: '' })

const filteredDocs = computed(() => {
  let list = docs.value
  if (activeCategory.value !== '全部') {
    list = list.filter(d => d.category === activeCategory.value)
  }
  if (searchKeyword.value.trim()) {
    const kw = searchKeyword.value.trim().toLowerCase()
    list = list.filter(d => d.title.toLowerCase().includes(kw) || d.description.toLowerCase().includes(kw))
  }
  return list
})

const formatDate = (iso: string) => {
  if (!iso) return ''
  const d = new Date(iso)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

const fetchDocs = async () => {
  try {
    docs.value = await request.get('/v1/sop-documents')
  } catch {
    ElMessage.error('加载SOP文档失败')
  }
}

const openDoc = (doc: SopDoc) => {
  window.open(doc.url, '_blank')
}

const openCreate = () => {
  form.id = null
  form.title = ''
  form.category = '运营流程'
  form.url = ''
  form.description = ''
  dialogVisible.value = true
}

const openEdit = (doc: SopDoc) => {
  form.id = doc.id
  form.title = doc.title
  form.category = doc.category
  form.url = doc.url
  form.description = doc.description
  dialogVisible.value = true
}

const saveDoc = async () => {
  if (!form.title.trim()) { ElMessage.warning('请输入文档标题'); return }
  if (!form.url.trim()) { ElMessage.warning('请输入文档链接'); return }
  try {
    if (form.id) {
      await request.put(`/v1/sop-documents/${form.id}`, {
        title: form.title,
        category: form.category,
        url: form.url,
        description: form.description,
      })
    } else {
      await request.post('/v1/sop-documents', {
        title: form.title,
        category: form.category,
        url: form.url,
        description: form.description,
      })
    }
    dialogVisible.value = false
    await fetchDocs()
    ElMessage.success('文档已保存')
  } catch {
    ElMessage.error('保存失败')
  }
}

const deleteDoc = async (doc: SopDoc) => {
  try {
    await ElMessageBox.confirm(`确认删除文档「${doc.title}」吗？`, '删除文档', { type: 'warning' })
    await request.delete(`/v1/sop-documents/${doc.id}`)
    await fetchDocs()
    ElMessage.success('文档已删除')
  } catch { /* cancel */ }
}

onMounted(fetchDocs)
</script>

<style scoped>
.sop-page {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.sop-hero {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 20px;
  padding: 24px 28px;
  border-radius: 20px;
  border: 1px solid var(--border-color);
  background: var(--card-bg);
}

.sop-hero__eyebrow {
  color: var(--primary-color);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.sop-hero__title {
  margin: 10px 0 0;
  font-size: 32px;
  color: var(--text-primary);
}

.sop-filter-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  padding: 14px 18px;
  border-radius: 20px;
  border: 1px solid var(--border-color);
  background: var(--card-bg);
}

.sop-filter-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.sop-filter-chip {
  appearance: none;
  border: 1px solid var(--border-color);
  border-radius: 999px;
  padding: 8px 14px;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.2s ease;
}

.sop-filter-chip.is-active {
  border-color: rgba(34, 197, 94, 0.38);
  background: rgba(34, 197, 94, 0.1);
  color: var(--primary-color);
  font-weight: 600;
}

.sop-doc-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 16px;
}

.sop-doc-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 18px;
  border-radius: 16px;
  border: 1px solid var(--border-color);
  background: linear-gradient(180deg, rgba(248, 250, 252, 0.85), rgba(255, 255, 255, 0.96));
  cursor: pointer;
  transition: transform 0.18s ease, border-color 0.18s ease, box-shadow 0.18s ease;
}

.sop-doc-card:hover {
  transform: translateY(-1px);
  border-color: rgba(34, 197, 94, 0.38);
  box-shadow: 0 12px 24px rgba(15, 23, 42, 0.06);
}

.sop-doc-card__head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.sop-doc-card__category {
  display: inline-flex;
  padding: 4px 10px;
  border-radius: 999px;
  background: rgba(59, 130, 246, 0.1);
  color: #2563eb;
  font-size: 12px;
  font-weight: 600;
}

.sop-doc-card__time {
  color: var(--text-muted);
  font-size: 12px;
}

.sop-doc-card__title {
  margin: 0;
  color: var(--text-primary);
  font-size: 17px;
  font-weight: 700;
}

.sop-doc-card__desc {
  margin: 0;
  color: var(--text-muted);
  font-size: 13px;
  line-height: 1.6;
}

.sop-doc-card__actions {
  display: flex;
  gap: 10px;
  margin-top: 4px;
}

:global(html.dark) .sop-doc-card {
  background: linear-gradient(180deg, rgba(39, 40, 42, 0.92), rgba(29, 30, 31, 0.98));
  border-color: rgba(74, 222, 128, 0.2);
}

:global(html.dark) .sop-doc-card:hover {
  border-color: rgba(74, 222, 128, 0.38);
  box-shadow: 0 16px 28px rgba(0, 0, 0, 0.28);
}

:global(html.dark) .sop-doc-card__category {
  background: rgba(96, 165, 250, 0.18);
  color: #93c5fd;
}

:global(html.dark) .sop-filter-chip.is-active {
  background: rgba(34, 197, 94, 0.14);
  border-color: rgba(74, 222, 128, 0.34);
}

:global(html.dark) .sop-hero,
:global(html.dark) .sop-filter-bar {
  background: #1d1e1f !important;
  border-color: #414243 !important;
}
</style>
