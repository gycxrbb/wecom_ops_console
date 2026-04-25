<template>
  <div class="internal-groups">
    <div class="header-actions">
      <h2>内部群管理</h2>
      <el-button type="primary" @click="openCreate">新增群</el-button>
    </div>

    <!-- 移动端卡片视图 -->
    <div v-if="isMobile" v-loading="loading" class="m-card-list">
      <div v-for="row in groups" :key="row.id" class="m-card">
        <div class="m-card__row">
          <strong class="m-card__title">{{ row.name }}</strong>
          <el-tag :type="row.webhook_configured ? 'success' : 'danger'" size="small">
            {{ row.webhook_configured ? '已配置' : '未配置' }}
          </el-tag>
        </div>
        <div v-if="row.alias" class="m-card__sub">{{ row.alias }}</div>
        <div v-if="parseTags(row.tags).length" class="m-card__tags">
          <el-tag v-for="tag in parseTags(row.tags)" :key="tag" size="small" style="margin-right:4px">{{ tag }}</el-tag>
        </div>
        <div class="m-card__footer">
          <el-switch v-model="row.is_enabled" @change="toggleStatus(row)" />
          <el-button type="primary" link size="small" @click="editGroup(row)">编辑</el-button>
          <el-button type="danger" link size="small" @click="deleteGroup(row)">删除</el-button>
        </div>
      </div>
      <el-empty v-if="!loading && !groups.length" :image-size="48" description="暂无群组" />
    </div>
    <!-- 桌面端表格视图 -->
    <el-table v-else :data="groups" style="width: 100%" v-loading="loading">
      <el-table-column prop="name" label="群名称" min-width="120" />
      <el-table-column prop="alias" label="别名" min-width="100" />
      <el-table-column label="标签" min-width="120">
        <template #default="{ row }">
          <el-tag
            v-for="tag in parseTags(row.tags)"
            :key="tag"
            size="small"
            style="margin-right: 4px"
          >
            {{ tag }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="Webhook" width="110" align="center">
        <template #default="{ row }">
          <el-tag :type="row.webhook_configured ? 'success' : 'danger'" size="small">
            {{ row.webhook_configured ? '已配置' : '未配置' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="80" align="center">
        <template #default="{ row }">
          <el-switch v-model="row.is_enabled" @change="toggleStatus(row)" />
        </template>
      </el-table-column>
      <el-table-column label="操作" width="150" fixed="right">
        <template #default="{ row }">
          <el-button type="primary" link @click="editGroup(row)">编辑</el-button>
          <el-button type="danger" link @click="deleteGroup(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialogVisible" :title="form.id ? '编辑群' : '新增群'" width="500px">
      <el-form label-width="110px" :model="form">
        <el-form-item label="群名称" required>
          <el-input v-model="form.name" placeholder="输入群名称" />
        </el-form-item>
        <el-form-item label="别名">
          <el-input v-model="form.alias" placeholder="群的别名（可选）" />
        </el-form-item>
        <el-form-item label="标签">
          <el-select
            v-model="formTags"
            multiple
            filterable
            allow-create
            default-first-option
            placeholder="输入标签后回车"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="Webhook URL">
          <el-input
            v-model="form.webhook"
            type="textarea"
            :rows="3"
            :placeholder="form.id
              ? '留空不修改，填入新值则覆盖'
              : '粘贴企业微信群机器人 Webhook 地址'"
          />
          <div v-if="form.id && form.webhook_configured" style="font-size: 12px; color: #67c23a; margin-top: 4px">
            当前已配置 Webhook（出于安全考虑不展示原值，留空则不修改）
          </div>
        </el-form-item>
        <el-form-item label="测试群">
          <el-switch v-model="form.is_test" />
          <span style="margin-left: 8px; font-size: 12px; color: #909399">标记为测试群后可用于发送测试消息</span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveGroup" :loading="saving">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, reactive } from 'vue'
import request from '#/utils/request'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useMobile } from '#/composables/useMobile'

const { isMobile } = useMobile()

const groups = ref<any[]>([])
const loading = ref(false)
const dialogVisible = ref(false)
const saving = ref(false)

const form = reactive({
  id: null as number | null,
  name: '',
  alias: '',
  webhook: '',
  tags: '[]' as string,
  is_enabled: true,
  is_test: false,
  webhook_configured: false,
})

const formTags = ref<string[]>([])

const parseTags = (tags: any): string[] => {
  if (Array.isArray(tags)) return tags
  try { return JSON.parse(tags || '[]') } catch { return [] }
}

const fetchGroups = async () => {
  loading.value = true
  try {
    const res = await request.get('/v1/groups')
    groups.value = res.list || res
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

const openCreate = () => {
  form.id = null
  form.name = ''
  form.alias = ''
  form.webhook = ''
  form.tags = '[]'
  form.is_enabled = true
  form.is_test = false
  form.webhook_configured = false
  formTags.value = []
  dialogVisible.value = true
}

const editGroup = (row: any) => {
  form.id = row.id
  form.name = row.name
  form.alias = row.alias || ''
  form.webhook = ''
  form.is_enabled = row.is_enabled
  form.is_test = row.is_test_group || false
  form.webhook_configured = row.webhook_configured || false
  formTags.value = parseTags(row.tags)
  dialogVisible.value = true
}

const deleteGroup = (row: any) => {
  ElMessageBox.confirm(`确认删除群"${row.name}"？`, '警告', { type: 'warning' }).then(async () => {
    await request.delete(`/v1/groups/${row.id}`)
    ElMessage.success('删除成功')
    fetchGroups()
  })
}

const saveGroup = async () => {
  if (!form.name.trim()) {
    return ElMessage.warning('请输入群名称')
  }
  saving.value = true
  try {
    const payload: any = {
      id: form.id,
      name: form.name,
      alias: form.alias,
      tags: formTags.value,
      is_test_group: form.is_test,
      is_enabled: form.is_enabled,
    }
    if (form.webhook.trim()) {
      payload.webhook = form.webhook.trim()
    }
    await request.post('/v1/groups', payload)
    dialogVisible.value = false
    ElMessage.success('保存成功')
    fetchGroups()
  } catch (e: any) {
    ElMessage.error(e.message || '保存失败')
  } finally {
    saving.value = false
  }
}

const toggleStatus = async (row: any) => {
  try {
    await request.post('/v1/groups', {
      id: row.id,
      name: row.name,
      alias: row.alias || '',
      tags: parseTags(row.tags),
      is_test_group: row.is_test_group || false,
      is_enabled: row.is_enabled,
    })
    ElMessage.success(row.is_enabled ? '已启用' : '已禁用')
  } catch (e) {
    row.is_enabled = !row.is_enabled
  }
}

onMounted(() => {
  fetchGroups()
})
</script>

<style scoped>
.internal-groups {
  background: var(--card-bg, #fff);
  border-radius: 4px;
  overflow-x: auto;
}
.header-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  flex-wrap: wrap;
  gap: 12px;
}
.m-card-list { display: flex; flex-direction: column; gap: 10px; }
.m-card {
  padding: 14px;
  border: 1px solid var(--border-color);
  border-radius: 12px;
  background: var(--card-bg);
}
.m-card__row { display: flex; justify-content: space-between; align-items: center; gap: 8px; }
.m-card__title { font-size: 14px; color: var(--text-primary); }
.m-card__sub { font-size: 13px; color: var(--text-muted); margin-top: 4px; }
.m-card__tags { margin-top: 6px; }
.m-card__footer {
  display: flex; align-items: center; gap: 8px;
  margin-top: 10px; padding-top: 10px;
  border-top: 1px solid var(--border-color);
}
@media (max-width: 768px) {
  .internal-groups { padding: 12px; }
}
</style>
