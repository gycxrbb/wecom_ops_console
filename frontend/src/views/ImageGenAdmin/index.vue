<template>
  <div class="page-container">
    <div class="page-header">
      <div>
        <h1 class="page-title">图片生成管理</h1>
        <p class="page-desc">配置生图供应商（多套按 priority 自动 failover，api_key 加密存储不下发）；查看生图历史与审计。生图入口在「客户档案 → AI 教练 → 图片生成」。</p>
      </div>
    </div>

    <el-card shadow="never" class="table-card">
      <el-tabs v-model="activeTab">
        <!-- 供应商配置 -->
        <el-tab-pane label="供应商配置" name="providers">
          <div class="toolbar">
            <el-button type="primary" @click="openProviderDialog(null)"><el-icon><Plus /></el-icon> 新增供应商</el-button>
            <span class="ig-hint">按 priority 升序生效（小优先）；当前供应商全失败才会切换下一套。</span>
          </div>
          <el-table :data="providers" v-loading="providersLoading" style="width: 100%">
            <el-table-column prop="priority" label="优先级" width="80" />
            <el-table-column prop="name" label="名称" />
            <el-table-column prop="provider_kind" label="类型" width="150" />
            <el-table-column prop="base_url" label="根地址" show-overflow-tooltip />
            <el-table-column prop="default_model" label="默认模型" width="140" />
            <el-table-column label="API Key" width="160">
              <template #default="scope">{{ scope.row.api_key_masked || '—' }}</template>
            </el-table-column>
            <el-table-column label="启用" width="80">
              <template #default="scope">
                <el-tag :type="scope.row.enabled ? 'success' : 'info'" size="small">{{ scope.row.enabled ? '是' : '否' }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="140" fixed="right">
              <template #default="scope">
                <el-button link type="primary" @click="openProviderDialog(scope.row)">编辑</el-button>
                <el-button link type="danger" @click="deleteProvider(scope.row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <!-- 生图历史 -->
        <el-tab-pane label="生图历史" name="history">
          <div class="toolbar">
            <el-select v-model="historyFilter.status" placeholder="状态" clearable style="width: 120px" @change="loadHistory(1)">
              <el-option label="成功" value="success" />
              <el-option label="失败" value="failed" />
            </el-select>
            <el-select v-model="historyFilter.mode" placeholder="模式" clearable style="width: 120px" @change="loadHistory(1)">
              <el-option label="直出" value="direct" />
              <el-option label="agent" value="agent" />
            </el-select>
            <el-button @click="loadHistory()">刷新</el-button>
          </div>
          <el-table :data="history" v-loading="historyLoading" style="width: 100%">
            <el-table-column prop="created_at" label="时间" width="160" />
            <el-table-column label="状态" width="80">
              <template #default="scope">
                <el-tag :type="scope.row.status === 'success' ? 'success' : 'danger'" size="small">{{ scope.row.status === 'success' ? '成功' : '失败' }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="mode" label="模式" width="70" />
            <el-table-column prop="model" label="模型" width="130" />
            <el-table-column prop="provider_name" label="供应商" width="110" />
            <el-table-column label="耗时" width="90">
              <template #default="scope">{{ scope.row.latency_ms ? (scope.row.latency_ms / 1000).toFixed(1) + 's' : '—' }}</template>
            </el-table-column>
            <el-table-column prop="prompt" label="提示词" show-overflow-tooltip />
            <el-table-column label="结果" width="80">
              <template #default="scope">
                <el-image v-if="scope.row.public_url" :src="scope.row.public_url" :preview-src-list="[scope.row.public_url]" fit="cover" style="width: 44px; height: 44px; border-radius: 4px" />
                <el-tooltip v-else-if="scope.row.error_code" :content="scope.row.error_message || scope.row.error_code" placement="top">
                  <span style="color: var(--el-color-danger)">{{ scope.row.error_code }}</span>
                </el-tooltip>
                <span v-else>—</span>
              </template>
            </el-table-column>
          </el-table>
          <div class="ig-pagination">
            <el-pagination background layout="prev, pager, next, total" :total="historyTotal" :page-size="historyPageSize" :current-page="historyPage" @current-change="loadHistory" />
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- 供应商新增/编辑 -->
    <el-dialog v-model="providerDialogVisible" :title="editingProvider?.id ? '编辑供应商' : '新增供应商'" width="520px" append-to-body>
      <el-form :model="providerForm" :rules="providerRules" ref="providerFormRef" label-width="100px">
        <el-form-item label="名称" prop="name"><el-input v-model="providerForm.name" placeholder="如 inferera" /></el-form-item>
        <el-form-item label="类型" prop="provider_kind">
          <el-select v-model="providerForm.provider_kind" style="width: 100%">
            <el-option label="OpenAI 兼容" value="openai_compatible" />
            <el-option label="Doubao（暂未启用）" value="doubao" disabled />
          </el-select>
        </el-form-item>
        <el-form-item label="根地址" prop="base_url"><el-input v-model="providerForm.base_url" placeholder="不含 /v1，如 https://api.inferera.com" /></el-form-item>
        <el-form-item label="API Key" prop="api_key">
          <el-input v-model="providerForm.api_key" type="password" show-password :placeholder="editingProvider?.id ? '留空则不修改' : '必填'" />
        </el-form-item>
        <el-form-item label="默认模型" prop="default_model"><el-input v-model="providerForm.default_model" placeholder="gpt-image-2" /></el-form-item>
        <el-form-item label="优先级"><el-input-number v-model="providerForm.priority" :min="0" :max="999" /></el-form-item>
        <el-form-item label="超时(秒)"><el-input-number v-model="providerForm.timeout_seconds" :min="30" :max="3600" :step="30" /></el-form-item>
        <el-form-item label="重试次数"><el-input-number v-model="providerForm.max_retries" :min="0" :max="5" /></el-form-item>
        <el-form-item label="启用"><el-switch v-model="providerForm.enabled" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="providerDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="providerSaving" @click="saveProvider">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Plus } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import request from '#/utils/request'

const activeTab = ref('providers')

// ── 供应商配置 ──
const providers = ref<any[]>([])
const providersLoading = ref(false)
const providerDialogVisible = ref(false)
const providerSaving = ref(false)
const editingProvider = ref<any>(null)
const providerFormRef = ref()
const providerForm = ref(emptyProviderForm())
const providerRules = {
  name: [{ required: true, message: '必填', trigger: 'blur' }],
  base_url: [{ required: true, message: '必填', trigger: 'blur' }],
}

function emptyProviderForm() {
  return {
    name: '', provider_kind: 'openai_compatible', base_url: '', api_key: '',
    default_model: 'gpt-image-2', priority: 0, enabled: true, timeout_seconds: 1500, max_retries: 2,
  }
}

async function loadProviders() {
  providersLoading.value = true
  try {
    const data: any = await request.get('/v1/image-gen/providers')
    providers.value = data?.items || []
  } finally {
    providersLoading.value = false
  }
}

function openProviderDialog(row: any) {
  editingProvider.value = row
  providerForm.value = row
    ? { name: row.name, provider_kind: row.provider_kind, base_url: row.base_url, api_key: '',
        default_model: row.default_model, priority: row.priority, enabled: row.enabled,
        timeout_seconds: row.timeout_seconds, max_retries: row.max_retries }
    : emptyProviderForm()
  providerDialogVisible.value = true
}

async function saveProvider() {
  try {
    await providerFormRef.value?.validate()
  } catch {
    return
  }
  if (!editingProvider.value?.id && !providerForm.value.api_key) {
    ElMessage.warning('请填写 API Key')
    return
  }
  providerSaving.value = true
  try {
    const body: any = { ...providerForm.value }
    if (!body.api_key) delete body.api_key // 留空 = 不修改
    if (editingProvider.value?.id) {
      await request.put(`/v1/image-gen/providers/${editingProvider.value.id}`, body)
      ElMessage.success('已更新')
    } else {
      await request.post('/v1/image-gen/providers', body)
      ElMessage.success('已新增')
    }
    providerDialogVisible.value = false
    loadProviders()
  } finally {
    providerSaving.value = false
  }
}

async function deleteProvider(row: any) {
  try {
    await ElMessageBox.confirm(`确定删除供应商「${row.name}」？`, '提示', { type: 'warning' })
  } catch {
    return // 用户取消
  }
  await request.delete(`/v1/image-gen/providers/${row.id}`)
  ElMessage.success('已删除')
  loadProviders()
}

// ── 生图历史 ──
const history = ref<any[]>([])
const historyLoading = ref(false)
const historyTotal = ref(0)
const historyPage = ref(1)
const historyPageSize = ref(20)
const historyFilter = ref({ status: '', mode: '' })

async function loadHistory(page?: number) {
  if (page) historyPage.value = page
  historyLoading.value = true
  try {
    const data: any = await request.get('/v1/image-gen/history', {
      params: {
        page: historyPage.value,
        page_size: historyPageSize.value,
        status: historyFilter.value.status || undefined,
        mode: historyFilter.value.mode || undefined,
      },
    })
    history.value = data?.items || []
    historyTotal.value = data?.total || 0
  } finally {
    historyLoading.value = false
  }
}

onMounted(() => {
  loadProviders()
  loadHistory(1)
})
</script>

<style scoped>
.toolbar { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; }
.ig-hint { margin-left: 8px; color: var(--text-muted); font-size: 12px; }
.ig-pagination { margin-top: 12px; display: flex; justify-content: flex-end; }
</style>
