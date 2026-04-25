<template>
  <div class="page-container">
    <div class="page-header">
      <h2 class="page-title">权限管理</h2>
      <p class="page-desc">管理本地账号和 CRM 成员的操作权限。管理员始终拥有全部权限，且不会出现在此列表中。</p>
    </div>

    <div class="toolbar">
      <el-input
        v-model="keyword"
        placeholder="搜索用户名 / 显示名称 / 账号来源"
        clearable
        class="search-input"
      />
    </div>

    <div v-if="loading" style="text-align: center; padding: 60px; color: var(--text-muted)">
      <el-icon class="is-loading" :size="24"><Loading /></el-icon>
      <span style="margin-left: 8px">加载中...</span>
    </div>

    <div v-else-if="filteredMembers.length === 0" class="empty-state">
      <span>暂无可配置权限的账号</span>
    </div>

    <div v-else class="members-grid">
      <div v-for="member in filteredMembers" :key="member.id" class="member-card">
        <div class="member-card__header">
          <el-avatar :size="36" style="background-color: #22C55E; flex-shrink: 0">
            {{ member.display_name?.charAt(0) || 'U' }}
          </el-avatar>
          <div class="member-card__info">
            <span class="member-card__name">{{ member.display_name }}</span>
            <span class="member-card__username">{{ member.username }}</span>
            <span class="member-card__meta">{{ member.auth_source === 'crm' ? 'CRM 同步账号' : '本地账号' }}</span>
          </div>
          <el-button size="small" type="primary" text @click="saveMember(member)" :loading="member._saving">
            保存
          </el-button>
        </div>
        <div class="member-card__body">
          <div v-for="group in permissionGroups" :key="group.name" class="perm-group">
            <div class="perm-group__label">{{ group.name }}</div>
            <div class="perm-group__items">
              <el-checkbox
                v-for="perm in group.permissions"
                :key="perm.key"
                :model-value="member.permissions[perm.key]"
                @change="(val: boolean) => togglePerm(member, perm.key, val)"
              >{{ perm.label }}</el-checkbox>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { Loading } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import request from '#/utils/request'

interface Member {
  id: number
  username: string
  display_name: string
  avatar_url: string
  auth_source: string
  role: string
  permissions: Record<string, boolean>
  _saving?: boolean
}

interface PermGroup {
  name: string
  permissions: Array<{ key: string; label: string }>
}

const members = ref<Member[]>([])
const keyword = ref('')
const loading = ref(false)
const permissionGroups = ref<PermGroup[]>([])

const filteredMembers = computed(() => {
  const q = keyword.value.trim().toLowerCase()
  if (!q) return members.value
  return members.value.filter((member) =>
    [
      member.username,
      member.display_name,
      member.auth_source === 'crm' ? 'crm 同步账号' : '本地账号',
      member.auth_source,
    ]
      .filter(Boolean)
      .some((value) => String(value).toLowerCase().includes(q))
  )
})

const fetchSchema = async () => {
  try {
    const res: any = await request.get('/v1/permissions/schema')
    permissionGroups.value = res.groups || []
  } catch {
    permissionGroups.value = []
  }
}

const fetchMembers = async () => {
  loading.value = true
  try {
    const res: any = await request.get('/v1/permissions/members')
    members.value = (res || []).map((m: any) => ({ ...m, _saving: false }))
  } catch (e: any) {
    ElMessage.error('加载成员失败: ' + String(e))
  } finally {
    loading.value = false
  }
}

const togglePerm = (member: Member, key: string, val: boolean) => {
  member.permissions = { ...member.permissions, [key]: val }
}

const saveMember = async (member: Member) => {
  member._saving = true
  try {
    await request.put(`/v1/permissions/members/${member.id}`, {
      permissions: member.permissions,
    })
    ElMessage.success(`${member.display_name} 权限已保存`)
  } catch (e: any) {
    ElMessage.error('保存失败: ' + String(e))
  } finally {
    member._saving = false
  }
}

onMounted(() => {
  fetchSchema()
  fetchMembers()
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
.search-input {
  width: min(360px, 100%);
}
.empty-state {
  text-align: center;
  padding: 60px 20px;
  color: var(--text-muted);
  font-size: 14px;
}
.members-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 16px;
}
.member-card {
  border: 1px solid var(--border-color);
  border-radius: 12px;
  background: var(--card-bg, #fff);
  overflow: hidden;
}
.member-card__header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border-color);
}
.member-card__info {
  flex: 1;
  min-width: 0;
}
.member-card__name {
  display: block;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}
.member-card__username {
  display: block;
  font-size: 12px;
  color: var(--text-muted);
}
.member-card__meta {
  display: inline-flex;
  margin-top: 6px;
  font-size: 11px;
  color: var(--text-muted);
  background: rgba(34, 197, 94, 0.08);
  border-radius: 999px;
  padding: 2px 8px;
}
.member-card__body {
  padding: 16px 20px;
}
.perm-group {
  margin-bottom: 12px;
}
.perm-group:last-child {
  margin-bottom: 0;
}
.perm-group__label {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-muted);
  letter-spacing: 0.05em;
  margin-bottom: 6px;
}
.perm-group__items {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 16px;
}
.perm-group__items :deep(.el-checkbox) {
  height: 28px;
}

@media (max-width: 600px) {
  .members-grid {
    grid-template-columns: 1fr;
  }
  .search-input {
    width: 100%;
  }
  .toolbar {
    justify-content: stretch;
  }
  .member-card__header {
    padding: 12px 14px;
    flex-wrap: wrap;
  }
  .member-card__body {
    padding: 12px 14px;
  }
  .perm-group__items {
    gap: 2px 12px;
  }
}
</style>
