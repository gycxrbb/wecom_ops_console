<template>
  <div class="page-container">
    <div class="page-header">
      <h2 class="page-title">自动排行推送</h2>
      <p class="page-desc">配置每日自动积分排行推送，每天 00:03 自动生成排行消息并推送到目标群。</p>
    </div>

    <div class="toolbar">
      <el-button type="primary" @click="openDialog()">新建配置</el-button>
    </div>

    <div v-if="loading" style="text-align: center; padding: 60px; color: var(--text-muted)">
      <el-icon class="is-loading" :size="24"><Loading /></el-icon>
      <span style="margin-left: 8px">加载中...</span>
    </div>

    <el-table v-else :data="configs" stripe border style="width: 100%">
      <el-table-column prop="name" label="配置名称" min-width="140" />
      <el-table-column label="CRM 群" min-width="100" align="center">
        <template #default="{ row }">{{ row.crm_group_ids?.length || 0 }} 个</template>
      </el-table-column>
      <el-table-column label="目标群" min-width="120">
        <template #default="{ row }">{{ localGroupName(row.target_local_group_id) }}</template>
      </el-table-column>
      <el-table-column label="必选场景" min-width="140">
        <template #default="{ row }">
          <el-tag v-for="k in row.must_scene_keys" :key="k" size="small" class="scene-tag">{{ sceneLabel(k) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="启用" width="80" align="center">
        <template #default="{ row }">
          <el-switch :model-value="row.enabled" @change="toggleEnabled(row, $event)" />
        </template>
      </el-table-column>
      <el-table-column label="上次执行" min-width="160">
        <template #default="{ row }">
          <template v-if="row.last_run_at">{{ row.last_run_at }}</template>
          <span v-else style="color: var(--text-muted)">未执行</span>
          <div v-if="row.last_error" class="error-hint">{{ row.last_error }}</div>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="140" align="center">
        <template #default="{ row }">
          <el-button size="small" text type="primary" @click="openDialog(row)">编辑</el-button>
          <el-popconfirm title="确定删除此配置？" @confirm="deleteConfig(row.id)">
            <template #reference>
              <el-button size="small" text type="danger">删除</el-button>
            </template>
          </el-popconfirm>
        </template>
      </el-table-column>
    </el-table>

    <!-- 新建/编辑 Dialog -->
    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑配置' : '新建配置'" width="680px" destroy-on-close>
      <el-form :model="form" label-width="120px" label-position="right">
        <el-form-item label="配置名称" required>
          <el-input v-model="form.name" placeholder="如：首钢系列每日排行" />
        </el-form-item>

        <el-form-item label="CRM 群" required>
          <el-select
            v-model="form.crm_group_ids"
            multiple
            filterable
            collapse-tags
            collapse-tags-tooltip
            placeholder="选择要生成排行的 CRM 群"
            style="width: 100%"
          >
            <el-option
              v-for="g in crmGroups"
              :key="g.crm_group_id"
              :label="`${g.crm_group_name} (ID: ${g.crm_group_id})`"
              :value="g.crm_group_id"
            />
          </el-select>
          <div class="form-tip">从已绑定的 CRM 群中选择</div>
        </el-form-item>

        <el-form-item label="推送目标群" required>
          <el-select v-model="form.target_local_group_id" placeholder="选择目标内部群" style="width: 100%">
            <el-option
              v-for="g in localGroups"
              :key="g.id"
              :label="g.name"
              :value="g.id"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="必选场景" required>
          <el-checkbox-group v-model="form.must_scene_keys">
            <el-checkbox v-for="s in insightScenes" :key="s.key" :value="s.key">{{ s.label }}</el-checkbox>
          </el-checkbox-group>
          <div class="form-tip">每次推送必须包含这些场景</div>
        </el-form-item>

        <el-form-item label="可选场景池">
          <el-checkbox-group v-model="form.extra_scene_pool">
            <el-checkbox v-for="s in insightScenes" :key="s.key" :value="s.key">{{ s.label }}</el-checkbox>
          </el-checkbox-group>
          <div class="form-tip">从中随机补充场景，凑齐总场景数</div>
        </el-form-item>

        <el-form-item label="场景总数">
          <el-input-number v-model="form.scene_count" :min="1" :max="6" />
          <span class="form-tip" style="margin-left: 8px">必选 + 随机补齐到此数量</span>
        </el-form-item>

        <el-form-item label="话术风格">
          <el-select v-model="form.speech_style" style="width: 200px">
            <el-option label="专业" value="professional" />
            <el-option label="鼓励" value="encouraging" />
            <el-option label="竞技" value="competitive" />
          </el-select>
        </el-form-item>

        <el-form-item label="周一明细">
          <el-switch v-model="form.include_breakdown_on_monday" active-text="周一自动开启上周积分明细" />
        </el-form-item>

        <el-form-item label="跳过周末">
          <el-switch v-model="form.skip_weekends" />
        </el-form-item>

        <el-form-item label="跳过日期">
          <el-select
            v-model="form.skip_dates"
            multiple
            filterable
            allow-create
            default-first-option
            placeholder="输入日期 YYYY-MM-DD 回车添加"
            style="width: 100%"
          />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveConfig">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { Loading } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import request from '#/utils/request'

interface Config {
  id: number
  name: string
  enabled: boolean
  crm_group_ids: number[]
  target_local_group_id: number
  must_scene_keys: string[]
  extra_scene_pool: string[]
  scene_count: number
  speech_style: string
  include_breakdown_on_monday: boolean
  skip_weekends: boolean
  skip_dates: string[]
  last_run_at: string | null
  last_error: string
}

interface Scene {
  key: string
  label: string
}

interface CrmBinding {
  crm_group_id: number
  crm_group_name: string
}

interface LocalGroup {
  id: number
  name: string
}

const configs = ref<Config[]>([])
const loading = ref(false)
const saving = ref(false)
const dialogVisible = ref(false)
const editingId = ref<number | null>(null)
const insightScenes = ref<Scene[]>([])
const crmGroups = ref<CrmBinding[]>([])
const localGroups = ref<LocalGroup[]>([])

const form = reactive({
  name: '',
  crm_group_ids: [] as number[],
  target_local_group_id: null as number | null,
  must_scene_keys: ['top_leader', 'top_six'] as string[],
  extra_scene_pool: [] as string[],
  scene_count: 3,
  speech_style: 'professional',
  include_breakdown_on_monday: true,
  skip_weekends: false,
  skip_dates: [] as string[],
})

const sceneLabel = (key: string) => insightScenes.value.find(s => s.key === key)?.label || key

const localGroupName = (id: number) => localGroups.value.find(g => g.id === id)?.name || `群 #${id}`

const fetchConfigs = async () => {
  loading.value = true
  try {
    const res: any = await request.get('/v1/crm-points/auto-ranking-configs')
    configs.value = res.items || []
  } catch (e: any) {
    ElMessage.error('加载配置失败: ' + String(e))
  } finally {
    loading.value = false
  }
}

const fetchScenes = async () => {
  try {
    const res: any = await request.get('/v1/crm-points/insight-scenes')
    insightScenes.value = (res || []).map((s: any) => ({ key: s.key, label: s.label }))
  } catch { /* ignore */ }
}

const fetchCrmGroups = async () => {
  try {
    const res: any = await request.get('/v1/crm-points/bindings')
    crmGroups.value = (res.bindings || []).map((b: any) => ({
      crm_group_id: b.crm_group_id,
      crm_group_name: b.crm_group_name || `群 ${b.crm_group_id}`,
    }))
  } catch { /* ignore */ }
}

const fetchLocalGroups = async () => {
  try {
    const res: any = await request.get('/v1/crm-points/local-groups')
    localGroups.value = res.groups || []
  } catch { /* ignore */ }
}

const openDialog = (row?: Config) => {
  if (row) {
    editingId.value = row.id
    form.name = row.name
    form.crm_group_ids = [...row.crm_group_ids]
    form.target_local_group_id = row.target_local_group_id
    form.must_scene_keys = [...row.must_scene_keys]
    form.extra_scene_pool = [...row.extra_scene_pool]
    form.scene_count = row.scene_count
    form.speech_style = row.speech_style
    form.include_breakdown_on_monday = row.include_breakdown_on_monday
    form.skip_weekends = row.skip_weekends
    form.skip_dates = [...row.skip_dates]
  } else {
    editingId.value = null
    form.name = ''
    form.crm_group_ids = []
    form.target_local_group_id = null
    form.must_scene_keys = ['top_leader', 'top_six']
    form.extra_scene_pool = []
    form.scene_count = 3
    form.speech_style = 'professional'
    form.include_breakdown_on_monday = true
    form.skip_weekends = false
    form.skip_dates = []
  }
  dialogVisible.value = true
}

const saveConfig = async () => {
  if (!form.name) return ElMessage.warning('请填写配置名称')
  if (!form.crm_group_ids.length) return ElMessage.warning('请选择 CRM 群')
  if (!form.target_local_group_id) return ElMessage.warning('请选择推送目标群')
  if (!form.must_scene_keys.length) return ElMessage.warning('请选择至少一个必选场景')

  saving.value = true
  try {
    await request.post('/v1/crm-points/auto-ranking-configs', {
      id: editingId.value,
      name: form.name,
      enabled: true,
      crm_group_ids: form.crm_group_ids,
      target_local_group_id: form.target_local_group_id,
      must_scene_keys: form.must_scene_keys,
      extra_scene_pool: form.extra_scene_pool,
      scene_count: form.scene_count,
      speech_style: form.speech_style,
      include_breakdown_on_monday: form.include_breakdown_on_monday,
      skip_weekends: form.skip_weekends,
      skip_dates: form.skip_dates,
    })
    ElMessage.success(editingId.value ? '配置已更新' : '配置已创建')
    dialogVisible.value = false
    fetchConfigs()
  } catch (e: any) {
    ElMessage.error('保存失败: ' + String(e))
  } finally {
    saving.value = false
  }
}

const toggleEnabled = async (row: Config, val: boolean) => {
  try {
    await request.post('/v1/crm-points/auto-ranking-configs', {
      ...row,
      enabled: val,
    })
    row.enabled = val
  } catch (e: any) {
    ElMessage.error('更新失败: ' + String(e))
  }
}

const deleteConfig = async (id: number) => {
  try {
    await request.delete(`/v1/crm-points/auto-ranking-configs/${id}`)
    ElMessage.success('已删除')
    fetchConfigs()
  } catch (e: any) {
    ElMessage.error('删除失败: ' + String(e))
  }
}

onMounted(() => {
  fetchConfigs()
  fetchScenes()
  fetchCrmGroups()
  fetchLocalGroups()
})
</script>

<style scoped>
.page-container {
  max-width: 1200px;
  margin: 0 auto;
}
.page-desc {
  font-size: 13px;
  color: var(--text-muted);
  margin-top: 4px;
}
.toolbar {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 16px;
}
.scene-tag {
  margin: 2px 4px 2px 0;
}
.error-hint {
  font-size: 12px;
  color: var(--el-color-danger);
  margin-top: 4px;
  line-height: 1.4;
}
.form-tip {
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 4px;
}
</style>
