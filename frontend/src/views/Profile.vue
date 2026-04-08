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
            <p class="identity-copy__desc">
              这里集中维护你的身份资料、账号安全和权限边界，避免运营同学在多个页面之间来回确认。
            </p>

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
          <p>{{ item.hint }}</p>
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
              <p>维护你的对外展示信息，头像和显示名称会同步出现在系统账号区域与协作标识中。</p>
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

            <div class="profile-editor__note">
              <strong>头像与身份说明</strong>
              <p>建议上传清晰的正方形头像，大小不超过 2 MB。上传后会直接替换系统中的个人头像展示。</p>
            </div>
          </div>
        </article>

        <article class="profile-card">
          <div class="profile-card__header">
            <div>
              <span class="section-kicker">权限边界</span>
              <h3>权限概览</h3>
              <p>先看清当前账号能做什么、不能做什么，降低误操作和重复确认成本。</p>
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
              <p>先明确密码由谁管理，再决定是在本系统修改还是跳转到外部 CRM 处理。</p>
            </div>
          </div>

          <div class="security-mode">
            <span class="security-mode__label">当前模式</span>
            <strong>{{ profile.password_change_available ? '本系统可直接修改密码' : 'CRM 统一管理密码' }}</strong>
            <p>
              {{ profile.password_change_available
                ? '修改前需要校验当前密码，建议使用更长的新密码并避免与旧密码重复。'
                : '为了避免本系统与 CRM 用户库的正式密码真值漂移，这里不直接覆盖外部密码。' }}
            </p>
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
              description="如需改密，请前往 CRM 后台处理；本系统保留查看与协作能力，但不会直接改写外部用户库密码。"
            />
          </div>
        </article>

        <article class="profile-card profile-card--timeline">
          <div class="profile-card__header">
            <div>
              <span class="section-kicker">账号状态</span>
              <h3>身份摘要</h3>
              <p>把最关键的账号信息收拢到一列里，减少来回切换视线。</p>
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
    value: authSourceLabel.value,
    hint: '登录链路和密码管理方式都由这里决定。'
  },
  {
    label: '角色权限',
    value: roleLabel.value,
    hint: '直接影响运营配置、审批与系统治理边界。'
  },
  {
    label: '密码模式',
    value: profile.password_change_available ? '本地修改' : 'CRM 管理',
    hint: '避免在错误入口上反复尝试改密。'
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
  grid-template-columns: minmax(0, 1.6fr) minmax(280px, 0.8fr);
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

.identity-copy__desc {
  max-width: 620px;
  margin: 14px 0 0;
  line-height: 1.72;
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

.hero-stat p {
  margin: 10px 0 0;
  color: var(--text-secondary);
  line-height: 1.6;
  font-size: 13px;
}

.profile-workbench {
  display: grid;
  grid-template-columns: minmax(0, 1.45fr) minmax(320px, 0.95fr);
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
  box-shadow: none;
  background: color-mix(in srgb, var(--card-bg) 92%, transparent);
}

:deep(.field-shell .el-input.is-disabled .el-input__wrapper) {
  background: color-mix(in srgb, var(--card-bg) 76%, transparent);
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
</style>
