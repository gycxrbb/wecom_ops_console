<template>
  <div>
    <div class="tag-toolbar">
      <el-button size="small" type="primary" @click="openDialog()">新建标签</el-button>
      <el-button size="small" @click="refreshVocab" :loading="refreshing">从词汇表刷新</el-button>
      <el-select v-model="filterDimension" placeholder="筛选维度" clearable size="small" style="width: 150px; margin-left: 8px" @change="fetchTags">
        <el-option v-for="d in dimensions" :key="d" :label="d" :value="d" />
      </el-select>
    </div>

    <el-table :data="filteredTags" v-loading="loading" stripe border size="small">
      <el-table-column prop="dimension" label="维度" width="140" />
      <el-table-column prop="code" label="代码" width="140" />
      <el-table-column prop="name" label="名称" width="140" />
      <el-table-column label="别名" min-width="200">
        <template #default="{ row }">{{ (row.aliases || []).join('、') || '-' }}</template>
      </el-table-column>
      <el-table-column prop="sort_order" label="排序" width="60" align="center" />
      <el-table-column label="状态" width="70" align="center">
        <template #default="{ row }">
          <el-tag :type="row.enabled ? 'success' : 'info'" size="small">{{ row.enabled ? '启用' : '禁用' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="120" align="center">
        <template #default="{ row }">
          <el-button size="small" text type="primary" @click="openDialog(row)">编辑</el-button>
          <el-popconfirm :title="row.enabled ? '确定禁用？' : '确定启用？'" @confirm="toggleTag(row)">
            <template #reference>
              <el-button size="small" text :type="row.enabled ? 'warning' : 'success'">{{ row.enabled ? '禁用' : '启用' }}</el-button>
            </template>
          </el-popconfirm>
        </template>
      </el-table-column>
    </el-table>

    <!-- Dialog -->
    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑标签' : '新建标签'" width="500px" destroy-on-close>
      <el-form :model="form" label-width="80px">
        <el-form-item label="维度" required>
          <el-input v-model="form.dimension" placeholder="如 customer_goal" :disabled="!!editingId" />
        </el-form-item>
        <el-form-item label="代码" required>
          <el-input v-model="form.code" placeholder="如 weight_loss" :disabled="!!editingId" />
        </el-form-item>
        <el-form-item label="名称" required>
          <el-input v-model="form.name" placeholder="中文显示名" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="别名">
          <el-select v-model="form.aliases" multiple filterable allow-create default-first-option placeholder="输入回车添加" style="width: 100%" />
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="form.sort_order" :min="0" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveTag">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import request from '#/utils/request'

const loading = ref(false)
const saving = ref(false)
const refreshing = ref(false)
const tags = ref<any[]>([])
const filterDimension = ref('')
const dialogVisible = ref(false)
const editingId = ref<number | null>(null)

const form = reactive({
  dimension: '',
  code: '',
  name: '',
  description: '',
  aliases: [] as string[],
  sort_order: 0,
})

const dimensions = computed(() => [...new Set(tags.value.map(t => t.dimension))])
const filteredTags = computed(() => {
  if (!filterDimension.value) return tags.value
  return tags.value.filter(t => t.dimension === filterDimension.value)
})

const fetchTags = async () => {
  loading.value = true
  try {
    const res: any = await request.get('/v1/rag/tags', { params: filterDimension.value ? { dimension: filterDimension.value } : {} })
    tags.value = res.tags || []
  } catch { tags.value = [] }
  finally { loading.value = false }
}

const openDialog = (row?: any) => {
  if (row) {
    editingId.value = row.id
    Object.assign(form, { dimension: row.dimension, code: row.code, name: row.name, description: row.description || '', aliases: [...(row.aliases || [])], sort_order: row.sort_order || 0 })
  } else {
    editingId.value = null
    Object.assign(form, { dimension: '', code: '', name: '', description: '', aliases: [], sort_order: 0 })
  }
  dialogVisible.value = true
}

const saveTag = async () => {
  if (!form.dimension || !form.code || !form.name) return ElMessage.warning('请填写必填项')
  saving.value = true
  try {
    if (editingId.value) {
      await request.put(`/v1/rag/tags/${editingId.value}`, form)
    } else {
      await request.post('/v1/rag/tags', form)
    }
    ElMessage.success('保存成功')
    dialogVisible.value = false
    fetchTags()
  } catch (e: any) { ElMessage.error('保存失败: ' + String(e)) }
  finally { saving.value = false }
}

const toggleTag = async (row: any) => {
  try {
    await request.put(`/v1/rag/tags/${row.id}`, { enabled: !row.enabled })
    fetchTags()
  } catch (e: any) { ElMessage.error('操作失败: ' + String(e)) }
}

const refreshVocab = async () => {
  refreshing.value = true
  try {
    const res: any = await request.post('/v1/rag/tags/refresh')
    ElMessage.success(`刷新完成：新增 ${res.stats?.added || 0}，已存在 ${res.stats?.existing || 0}`)
    fetchTags()
  } catch (e: any) { ElMessage.error('刷新失败: ' + String(e)) }
  finally { refreshing.value = false }
}

onMounted(fetchTags)
</script>

<style scoped>
.tag-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}
</style>
