<template>
  <div class="profile-page" v-loading="loading">
    <section class="profile-hero">
      <div class="profile-hero__main">
        <div class="hero-badge">Profile Workspace</div>

        <div class="identity-cluster">
          <el-upload
            class="avatar-uploader"
            :show-file-list="false"
            :auto-upload="false"
            accept=".jpg,.jpeg,.png,.webp,.gif"
            :on-change="handleAvatarSelect"
          >
            <div class="avatar-shell">
              <div class="avatar-shell__ring" />
              <el-avatar :size="108" :src="profile.avatar_url || fallbackAvatar">
                {{ (profile.display_name || profile.username || 'U').charAt(0) }}
              </el-avatar>
              <div class="avatar-shell__overlay">更换头像</div>
            </div>
          </el-upload>

          <div class="identity-copy">
            <h1>{{ profile.display_name || profile.username || '个人中心' }}</h1>
            <p class="identity-copy__subtitle">{{ profile.username }} · {{ roleLabel }}</p>

            <div class="identity-tags">
              <span class="status-pill">{{ profile.status ? '账号正常' : '账号停用' }}</span>
              <span class="status-pill status-pill--soft">{{ authSourceLabel }}</span>
              <span class="status-pill status-pill--soft" v-if="profile.last_login_at">
                最近登录：{{ formatDateTime(profile.last_login_at) }}
              </span>
            </div>
          </div>
        </div>
      </div>

      <div class="profile-hero__rail">
        <div v-for="item in heroStats" :key="item.label" class="hero-stat">
          <span>{{ item.label }}</span>
          <strong>{{ item.value }}</strong>
        </div>
      </div>
    </section>

    <div class="profile-workbench">
      <section class="profile-column profile-column--main">
        <article class="profile-card profile-card--editor">
          <div class="profile-card__header">
            <div>
              <span class="section-kicker">资料设置</span>
              <h3>账号资料</h3>
            </div>
            <el-button type="primary" :loading="profileSaving" @click="saveProfile">
              保存资料
            </el-button>
          </div>

          <div class="profile-editor">
            <div class="profile-editor__grid">
              <div class="field-shell">
                <label>登录账号</label>
                <el-input :model-value="profile.username" disabled />
              </div>
              <div class="field-shell">
                <label>显示名称</label>
                <el-input
                  v-model="profileForm.display_name"
                  maxlength="64"
                  show-word-limit
                  placeholder="用于页面展示的昵称或姓名"
                />
              </div>
              <div class="field-shell">
                <label>账号来源</label>
                <el-input :model-value="authSourceLabel" disabled />
              </div>
              <div class="field-shell">
                <label>注册时间</label>
                <el-input :model-value="profile.created_at ? formatDateTime(profile.created_at) : '与系统初始化记录一致'" disabled />
              </div>
            </div>
          </div>
        </article>

        <article class="profile-card">
          <div class="profile-card__header">
            <div>
              <span class="section-kicker">权限边界</span>
              <h3>权限概览</h3>
            </div>
          </div>

          <div class="permission-list">
            <div v-for="item in permissionCards" :key="item.title" class="permission-item">
              <strong>{{ item.title }}</strong>
              <span>{{ item.desc }}</span>
            </div>
          </div>
        </article>
      </section>

      <aside class="profile-column profile-column--side">
        <article class="profile-card profile-card--security">
          <div class="profile-card__header">
            <div>
              <span class="section-kicker">账号安全</span>
              <h3>密码与认证</h3>
            </div>
          </div>

          <div class="security-mode">
            <span class="security-mode__label">当前模式</span>
            <strong>{{ profile.password_change_available ? '本系统可直接修改密码' : 'CRM 统一管理密码' }}</strong>
            
          </div>

          <el-form
            v-if="profile.password_change_available"
            label-position="top"
            class="security-form"
          >
            <el-form-item label="当前密码">
              <el-input v-model="passwordForm.current_password" type="password" show-password />
            </el-form-item>
            <el-form-item label="新密码">
              <el-input v-model="passwordForm.new_password" type="password" show-password />
            </el-form-item>
            <el-form-item label="确认新密码">
              <el-input v-model="passwordForm.confirm_password" type="password" show-password />
            </el-form-item>
            <el-button type="primary" :loading="passwordSaving" @click="updatePassword">
              更新密码
            </el-button>
          </el-form>

          <div v-else class="security-help">
            <el-alert
              title="当前账号密码由 CRM 统一管理"
              type="info"
              :closable="false"
              show-icon
              description="密码由 CRM 统一管理，如需修改请前往 CRM 后台。"
            />
          </div>
        </article>

        <article class="profile-card profile-card--timeline">
          <div class="profile-card__header">
            <div>
              <span class="section-kicker">账号状态</span>
              <h3>身份摘要</h3>
            </div>
          </div>

          <div class="meta-list">
            <div v-for="item in metaItems" :key="item.label" class="meta-item">
              <span>{{ item.label }}</span>
              <strong>{{ item.value }}</strong>
            </div>
          </div>
        </article>
      </aside>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, type UploadFile } from 'element-plus'
import request from '@/utils/request'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()
const loading = ref(false)
const profileSaving = ref(false)
const passwordSaving = ref(false)

const profile = reactive({
  id: 0,
  username: '',
  display_name: '',
  avatar_url: '',
  role: '',
  status: true,
  auth_source: 'local',
  last_login_at: '',
  created_at: '',
  password_change_available: false
})

const profileForm = reactive({
  display_name: ''
})

const passwordForm = reactive({
  current_password: '',
  new_password: '',
  confirm_password: ''
})

const fallbackAvatar = computed(() => (profile.role === 'admin' ? '/images/admain.jpg' : ''))
const roleLabel = computed(() => (profile.role === 'admin' ? '系统管理员' : '运营成员'))
const authSourceLabel = computed(() => (profile.auth_source === 'crm' ? 'CRM 账号同步' : '本地账号'))

const heroStats = computed(() => [
  {
    label: '账号来源',
    value: authSourceLabel.value
  },
  {
    label: '角色权限',
    value: roleLabel.value
  },
  {
    label: '密码模式',
    value: profile.password_change_available ? '本地修改' : 'CRM 管理'
  }
])

const metaItems = computed(() => [
  { label: '显示名称', value: profile.display_name || '未设置' },
  { label: '登录账号', value: profile.username || '-' },
  { label: '最近登录', value: profile.last_login_at ? formatDateTime(profile.last_login_at) : '暂无记录' },
  { label: '账号状态', value: profile.status ? '正常可用' : '已停用' }
])

const permissionCards = computed(() => {
  if (profile.role === 'admin') {
    return [
      { title: '系统级权限', desc: '可查看全局业务数据、维护账号与系统配置。' },
      { title: '运营配置权限', desc: '可维护模板、素材、运营编排与发送链路。' },
      { title: '审核与治理权限', desc: '可处理审批、排查问题并修复配置。' }
    ]
  }
  return [
    { title: '运营执行权限', desc: '可维护个人运营编排、模板、素材和发送任务。' },
    { title: '协作权限', desc: '可发起测试、预览、审批申请并查看个人相关数据。' },
    { title: '账号治理边界', desc: '系统级用户配置与部分敏感设置仍由管理员统一维护。' }
  ]
})

const formatDateTime = (value: string) => {
  if (!value) return ''
  return value.replace('T', ' ').slice(0, 16)
}

const syncProfileState = (payload: any) => {
  profile.id = payload.id
  profile.username = payload.username || ''
  profile.display_name = payload.display_name || ''
  profile.avatar_url = payload.avatar_url || ''
  profile.role = payload.role || ''
  profile.status = payload.status !== false
  profile.auth_source = payload.auth_source || 'local'
  profile.last_login_at = payload.last_login_at || ''
  profile.created_at = payload.created_at || ''
  profile.password_change_available = !!payload.password_change_available
  profileForm.display_name = profile.display_name
  userStore.user = {
    ...(userStore.user || {}),
    ...payload
  }
}

const fetchProfile = async () => {
  loading.value = true
  try {
    const res: any = await request.get('/v1/profile')
    syncProfileState(res)
  } finally {
    loading.value = false
  }
}

const saveProfile = async () => {
  profileSaving.value = true
  try {
    const res: any = await request.put('/v1/profile', {
      display_name: profileForm.display_name
    })
    syncProfileState(res)
    ElMessage.success('个人资料已更新')
  } finally {
    profileSaving.value = false
  }
}

const handleAvatarSelect = async (file: UploadFile) => {
  if (!file.raw) return
  const formData = new FormData()
  formData.append('file', file.raw)
  try {
    const res: any = await request.post('/v1/profile/avatar', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    syncProfileState(res.profile)
    ElMessage.success('头像已更新')
  } catch (error) {
    console.error(error)
    ElMessage.error('头像上传失败，请检查图片格式或大小')
  }
}

const updatePassword = async () => {
  if (!passwordForm.current_password || !passwordForm.new_password || !passwordForm.confirm_password) {
    ElMessage.warning('请完整填写密码信息')
    return
  }
  passwordSaving.value = true
  try {
    await request.post('/v1/profile/password', { ...passwordForm })
    passwordForm.current_password = ''
    passwordForm.new_password = ''
    passwordForm.confirm_password = ''
    ElMessage.success('密码已更新，请使用新密码重新登录')
  } finally {
    passwordSaving.value = false
  }
}

onMounted(fetchProfile)
</script>

<style scoped>
.profile-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
  --profile-surface: rgba(255, 255, 255, 0.9);
  --profile-surface-strong: rgba(255, 255, 255, 0.98);
  --profile-muted-surface: rgba(148, 163, 184, 0.08);
  --profile-tint: rgba(34, 197, 94, 0.12);
  --profile-blue-tint: rgba(59, 130, 246, 0.12);
  --profile-shadow: 0 20px 40px rgba(15, 23, 42, 0.08);
}

.profile-hero {
  display: grid;
  grid-template-columns: minmax(0, 1.6fr) minmax(200px, 0.8fr);
  gap: 18px;
  padding: 28px;
  border: 1px solid color-mix(in srgb, var(--border-color) 88%, transparent);
  border-radius: 28px;
  background:
    radial-gradient(circle at top left, rgba(34, 197, 94, 0.16), transparent 32%),
    radial-gradient(circle at right center, rgba(59, 130, 246, 0.08), transparent 28%),
    linear-gradient(135deg, var(--profile-surface-strong), var(--profile-surface));
  box-shadow: var(--profile-shadow);
}

.profile-hero__main {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.hero-badge {
  width: fit-content;
  padding: 7px 12px;
  border-radius: 999px;
  background: var(--profile-tint);
  color: var(--primary-color);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.identity-cluster {
  display: flex;
  gap: 22px;
  align-items: center;
}

.identity-copy {
  min-width: 0;
}

.identity-copy h1 {
  margin: 0;
  font-size: 34px;
  line-height: 1.1;
  color: var(--text-primary);
}

.identity-copy__subtitle {
  margin: 10px 0 0;
  font-size: 16px;
  color: var(--text-secondary);
}


.avatar-shell {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}

.avatar-shell__ring {
  position: absolute;
  inset: -8px;
  border-radius: 999px;
  background: conic-gradient(from 160deg, rgba(34, 197, 94, 0.34), rgba(59, 130, 246, 0.22), rgba(34, 197, 94, 0.12));
}

:deep(.avatar-shell .el-avatar) {
  position: relative;
  z-index: 1;
  border: 4px solid rgba(255, 255, 255, 0.92);
  box-shadow: 0 14px 34px rgba(15, 23, 42, 0.16);
}

.avatar-shell__overlay {
  position: absolute;
  inset: auto 10px 10px 10px;
  z-index: 2;
  padding: 8px 10px;
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.72);
  backdrop-filter: blur(10px);
  color: #fff;
  font-size: 12px;
  text-align: center;
  opacity: 0;
  transition: opacity 0.2s ease;
}

.avatar-shell:hover .avatar-shell__overlay {
  opacity: 1;
}

.identity-tags {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 14px;
}

.status-pill {
  padding: 8px 12px;
  border-radius: 999px;
  background: var(--profile-tint);
  color: #15803d;
  font-size: 12px;
  font-weight: 600;
}

.status-pill--soft {
  background: var(--profile-blue-tint);
  color: #2563eb;
}

.profile-hero__rail {
  display: grid;
  gap: 14px;
}

.hero-stat {
  min-height: 110px;
  padding: 18px 18px 16px;
  border-radius: 22px;
  border: 1px solid color-mix(in srgb, var(--border-color) 88%, transparent);
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.48), rgba(255, 255, 255, 0.2)),
    var(--profile-muted-surface);
}

.hero-stat span {
  display: block;
  margin-bottom: 10px;
  color: var(--text-muted);
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

.hero-stat strong {
  color: var(--text-primary);
  font-size: 20px;
  line-height: 1.3;
}


.profile-workbench {
  display: grid;
  grid-template-columns: minmax(0, 1.45fr) minmax(240px, 0.95fr);
  gap: 18px;
}

.profile-column {
  display: grid;
  gap: 18px;
  align-content: start;
}

.profile-column--side {
  position: sticky;
  top: 20px;
}

.profile-card {
  padding: 22px;
  border: 1px solid color-mix(in srgb, var(--border-color) 88%, transparent);
  border-radius: 24px;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.55), rgba(255, 255, 255, 0)),
    var(--profile-surface);
  box-shadow: 0 14px 30px rgba(15, 23, 42, 0.05);
}

.profile-card--editor {
  background:
    radial-gradient(circle at top right, rgba(34, 197, 94, 0.08), transparent 28%),
    linear-gradient(180deg, rgba(255, 255, 255, 0.6), rgba(255, 255, 255, 0)),
    var(--profile-surface);
}

.profile-card__header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
  margin-bottom: 20px;
}

.section-kicker {
  display: inline-block;
  margin-bottom: 8px;
  color: var(--primary-color);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.profile-card__header h3 {
  margin: 0 0 6px;
  color: var(--text-primary);
  font-size: 22px;
}

.profile-card__header p {
  margin: 0;
  max-width: 620px;
  color: var(--text-secondary);
  line-height: 1.6;
}

.profile-editor {
  display: grid;
  gap: 16px;
}

.profile-editor__grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.field-shell {
  padding: 16px;
  border-radius: 18px;
  border: 1px solid color-mix(in srgb, var(--border-color) 88%, transparent);
  background: var(--profile-muted-surface);
}

.field-shell label {
  display: block;
  margin-bottom: 10px;
  color: var(--text-muted);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.profile-editor__note,
.security-mode {
  padding: 16px 18px;
  border-radius: 18px;
  border: 1px solid color-mix(in srgb, var(--border-color) 88%, transparent);
  background:
    linear-gradient(180deg, rgba(34, 197, 94, 0.06), rgba(34, 197, 94, 0)),
    var(--profile-muted-surface);
}

.profile-editor__note strong,
.security-mode strong,
.permission-item strong,
.meta-item strong {
  display: block;
  margin-bottom: 8px;
  color: var(--text-primary);
  font-size: 16px;
}

.security-mode__label {
  display: block;
  margin-bottom: 8px;
  color: var(--text-muted);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.profile-editor__note p,
.security-mode p,
.permission-item span {
  margin: 0;
  color: var(--text-secondary);
  line-height: 1.6;
}

:deep(.field-shell .el-input__wrapper),
:deep(.security-form .el-input__wrapper) {
  border-radius: 14px;
  box-shadow: 0 0 0 1px var(--border-color) inset;
  background: var(--bg-color);
}

:deep(.field-shell .el-input.is-disabled .el-input__wrapper) {
  background: color-mix(in srgb, var(--bg-color) 60%, var(--card-bg));
}

.security-form {
  display: grid;
  gap: 2px;
}

:deep(.security-form .el-form-item__label) {
  padding-bottom: 6px;
  font-weight: 600;
}

.security-help {
  margin-top: 2px;
}

.permission-list,
.meta-list {
  display: grid;
  gap: 14px;
}

.permission-item,
.meta-item {
  padding: 16px 18px;
  border-radius: 18px;
  border: 1px solid color-mix(in srgb, var(--border-color) 88%, transparent);
  background: var(--profile-muted-surface);
}

.meta-item span {
  display: block;
  margin-bottom: 8px;
  color: var(--text-muted);
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

:global(html.dark) .profile-page {
  --profile-surface: rgba(29, 30, 31, 0.92);
  --profile-surface-strong: rgba(35, 36, 38, 0.98);
  --profile-muted-surface: rgba(255, 255, 255, 0.03);
  --profile-tint: rgba(34, 197, 94, 0.16);
  --profile-blue-tint: rgba(59, 130, 246, 0.14);
  --profile-shadow: 0 24px 42px rgba(0, 0, 0, 0.3);
}

:global(html.dark) .profile-hero {
  background:
    radial-gradient(circle at top left, rgba(34, 197, 94, 0.18), transparent 32%),
    radial-gradient(circle at right center, rgba(59, 130, 246, 0.1), transparent 28%),
    linear-gradient(135deg, rgba(32, 33, 35, 0.98), rgba(24, 25, 28, 0.96));
  box-shadow: 0 22px 38px rgba(0, 0, 0, 0.34);
}

:global(html.dark) .status-pill {
  color: #86efac;
}

:global(html.dark) .status-pill--soft {
  color: #93c5fd;
}

:global(html.dark) .hero-stat,
:global(html.dark) .profile-card,
:global(html.dark) .field-shell,
:global(html.dark) .profile-editor__note,
:global(html.dark) .security-mode,
:global(html.dark) .permission-item,
:global(html.dark) .meta-item {
  border-color: rgba(255, 255, 255, 0.08);
}

:global(html.dark) :deep(.avatar-shell .el-avatar) {
  border-color: rgba(35, 36, 38, 0.92);
}

@media (max-width: 1180px) {
  .profile-hero,
  .profile-workbench,
  .profile-editor__grid {
    grid-template-columns: 1fr;
  }

  .profile-column--side {
    position: static;
  }
}

@media (max-width: 720px) {
  .profile-hero {
    padding: 22px 18px;
  }

  .identity-cluster {
    flex-direction: column;
    align-items: flex-start;
  }

  .profile-card {
    padding: 18px;
  }

  .profile-card__header {
    flex-direction: column;
    align-items: stretch;
  }
}

@media (max-width: 480px) {
  .profile-hero {
    padding: 16px 12px;
    border-radius: 16px;
  }
  .profile-card {
    padding: 14px;
  }
  .profile-page {
    gap: 12px;
  }
}
</style>

<style>
/* ===== 暗黑模式 — 非 scoped 确保命中 ===== */
html.dark .profile-page {
  --profile-surface: rgba(29, 30, 31, 0.92) !important;
  --profile-surface-strong: rgba(35, 36, 38, 0.98) !important;
  --profile-muted-surface: rgba(255, 255, 255, 0.03) !important;
  --profile-tint: rgba(34, 197, 94, 0.16) !important;
  --profile-blue-tint: rgba(59, 130, 246, 0.14) !important;
  --profile-shadow: 0 24px 42px rgba(0, 0, 0, 0.3) !important;
}

html.dark .profile-hero {
  background:
    radial-gradient(circle at top left, rgba(34, 197, 94, 0.18), transparent 32%),
    radial-gradient(circle at right center, rgba(59, 130, 246, 0.1), transparent 28%),
    linear-gradient(135deg, rgba(32, 33, 35, 0.98), rgba(24, 25, 28, 0.96)) !important;
  border-color: rgba(255, 255, 255, 0.08) !important;
  box-shadow: 0 22px 38px rgba(0, 0, 0, 0.34) !important;
}

html.dark .hero-stat {
  background:
    linear-gradient(180deg, rgba(39, 40, 42, 0.6), rgba(29, 30, 31, 0.4)),
    rgba(255, 255, 255, 0.03) !important;
  border-color: rgba(255, 255, 255, 0.08) !important;
}

html.dark .profile-card {
  background:
    linear-gradient(180deg, rgba(39, 40, 42, 0.55), rgba(29, 30, 31, 0)),
    rgba(29, 30, 31, 0.92) !important;
  border-color: rgba(255, 255, 255, 0.08) !important;
  box-shadow: 0 14px 30px rgba(0, 0, 0, 0.2) !important;
}

html.dark .profile-card--editor {
  background:
    radial-gradient(circle at top right, rgba(34, 197, 94, 0.1), transparent 28%),
    linear-gradient(180deg, rgba(39, 40, 42, 0.6), rgba(29, 30, 31, 0)),
    rgba(29, 30, 31, 0.92) !important;
}

html.dark .field-shell {
  border-color: rgba(255, 255, 255, 0.08) !important;
}

html.dark .profile-editor__note,
html.dark .security-mode {
  border-color: rgba(255, 255, 255, 0.08) !important;
}

html.dark .permission-item,
html.dark .meta-item {
  border-color: rgba(255, 255, 255, 0.08) !important;
}

html.dark .status-pill {
  color: #86efac !important;
}

html.dark .status-pill--soft {
  color: #93c5fd !important;
}

html.dark .avatar-shell .el-avatar {
  border-color: rgba(35, 36, 38, 0.92) !important;
}

html.dark .avatar-shell__overlay {
  background: rgba(0, 0, 0, 0.72);
}

html.dark .field-shell .el-input__wrapper,
html.dark .security-form .el-input__wrapper {
  background: rgba(20, 20, 22, 0.8) !important;
  box-shadow: 0 0 0 1px rgba(255, 255, 255, 0.1) inset !important;
}

html.dark .field-shell .el-input.is-disabled .el-input__wrapper {
  background: rgba(20, 20, 22, 0.5) !important;
}
</style>
