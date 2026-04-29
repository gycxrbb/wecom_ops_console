<template>
  <div class="login-container">
    <!-- 顶栏 -->
    <div class="login-topbar">
      <span class="login-clock">{{ currentTime }}</span>
      <el-tooltip content="刷新页面" placement="bottom">
        <el-button :icon="RefreshRight" circle class="refresh-btn" @click="handleRefresh" />
      </el-tooltip>
      <ThemeToggle v-model="isDark" @change="handleThemeChange" />
    </div>
    <!-- 登录卡片 -->
    <el-card class="login-card">
      <template #header>
        <div class="card-header">
          <div class="logo-wrapper">
            <img :src="isDark ? '/images/light-logo.svg' : '/images/dark-logo.svg'" alt="logo" class="login-logo" />
          </div>
          <h2>企微运营平台</h2>
        </div>
      </template>
      <el-form :model="form" :rules="rules" ref="formRef" @submit.prevent>
        <el-form-item prop="username">
          <el-input v-model="form.username" placeholder="用户名" />
        </el-form-item>
        <el-form-item prop="password">
          <el-input
            v-model="form.password"
            :type="showPassword ? 'text' : 'password'"
            placeholder="密码（回车快捷登录）"
            @keyup.enter="handleLogin"
          >
            <template #suffix>
              <span class="password-toggle" @click="showPassword = !showPassword">
                <el-icon :size="16"><View v-if="showPassword" /><Hide v-else /></el-icon>
              </span>
            </template>
          </el-input>
        </el-form-item>
        <el-form-item>
          <el-checkbox v-model="rememberMe" style="margin-bottom:4px;">记住登录状态（7天）</el-checkbox>
        </el-form-item>
        <div v-if="lockoutSeconds > 0" class="login-lockout">
          <el-icon :size="16" style="margin-right:6px;"><Warning /></el-icon>
          账号已被临时锁定，请 <strong>{{ lockoutSeconds }}</strong> 秒后重试
        </div>
        <div v-else-if="loginError" class="login-error">{{ loginError }}</div>
        <div class="login-tip">
          admin 继续使用当前本地管理员账号，其他运营成员请使用 CRM 后台账号登录。
        </div>
        <el-form-item>
          <el-button type="primary" class="login-btn" :loading="loading" :disabled="lockoutSeconds > 0" @click="handleLogin">
            登 录
          </el-button>
        </el-form-item>
      </el-form>
      <div class="tips" style="margin-top:20px; text-align:center; color:#999; font-size:12px;">
        <div>管理员账号：admin / 当前本地密码</div>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { View, Hide, RefreshRight, Warning } from '@element-plus/icons-vue'
import ThemeToggle from '#/components/ThemeToggle.vue'
import request from '#/utils/request'
import { useUserStore } from '#/stores/user'
import JSEncrypt from 'jsencrypt'

const isDark = ref(localStorage.getItem('theme') === 'dark' || !localStorage.getItem('theme'))

const handleThemeChange = (val: boolean) => {
  if (val) {
    document.documentElement.classList.add('dark')
    localStorage.setItem('theme', 'dark')
  } else {
    document.documentElement.classList.remove('dark')
    localStorage.setItem('theme', 'light')
  }
}

onMounted(() => {
  if (isDark.value) {
    document.documentElement.classList.add('dark')
  } else {
    document.documentElement.classList.remove('dark')
  }
  // 初次访问自动刷新一次，确保加载最新资源
  if (!sessionStorage.getItem('login_refreshed')) {
    sessionStorage.setItem('login_refreshed', '1')
    window.location.reload()
  }
})

// 时钟
const currentTime = ref('')
let clockTimer: ReturnType<typeof setInterval> | null = null
const updateClock = () => {
  const now = new Date()
  const pad = (n: number) => String(n).padStart(2, '0')
  currentTime.value = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())} ${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`
}
updateClock()
clockTimer = setInterval(updateClock, 1000)
onBeforeUnmount(() => {
  if (clockTimer) clearInterval(clockTimer)
  if (lockoutTimer) clearInterval(lockoutTimer)
})

const handleRefresh = () => { window.location.reload() }

const router = useRouter()
const userStore = useUserStore()
const formRef = ref()
const loading = ref(false)
const showPassword = ref(false)
const loginError = ref('')
const lockoutSeconds = ref(0)
let lockoutTimer: ReturnType<typeof setInterval> | null = null

const form = reactive({
  username: '',
  password: ''
})
const rememberMe = ref(localStorage.getItem('remember_me') === '1')

const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }]
}

// RSA 公钥缓存：服务重启前不变，避免每次登录多一次 RTT
let cachedPublicKey: string | null = null
const fetchPublicKey = async (): Promise<string | null> => {
  if (cachedPublicKey) return cachedPublicKey
  try {
    const keyRes: any = await request.get('/v1/auth/public-key')
    cachedPublicKey = keyRes?.public_key || null
  } catch {
    cachedPublicKey = null
  }
  return cachedPublicKey
}
// 页面加载时预取公钥，与用户输入并行
fetchPublicKey()

const handleLogin = async () => {
  if (!formRef.value) return
  loginError.value = ''
  try {
    await formRef.value.validate()
  } catch {
    return
  }
  loading.value = true
  try {
    const publicKey = await fetchPublicKey()

    let finalPassword = form.password
    if (publicKey) {
      const encryptor = new JSEncrypt()
      encryptor.setPublicKey(publicKey)
      const encrypted = encryptor.encrypt(form.password)
      if (encrypted) {
        finalPassword = encrypted
      }
    }

    // 3. 提交加密后的密码
    const res: any = await request.post('/v1/auth/login', { username: form.username, password: finalPassword, remember_me: rememberMe.value })
    localStorage.setItem('access_token', res.access_token)
    localStorage.setItem('refresh_token', res.refresh_token)
    localStorage.setItem('remember_me', rememberMe.value ? '1' : '0')
    ElMessage.success('登录成功')
    await userStore.fetchUser()
    router.push('/')
  } catch (error: any) {
    const retryAfter = error?.serverData?.retry_after
    if (retryAfter && retryAfter > 0) {
      loginError.value = ''
      lockoutSeconds.value = retryAfter
      if (lockoutTimer) clearInterval(lockoutTimer)
      lockoutTimer = setInterval(() => {
        lockoutSeconds.value--
        if (lockoutSeconds.value <= 0) {
          if (lockoutTimer) clearInterval(lockoutTimer)
          lockoutTimer = null
        }
      }, 1000)
    } else {
      const data = error?.serverData
      const baseMsg = error?.message || '登录失败，请检查账号密码或稍后重试'
      if (data?.failed_attempts && data?.max_attempts) {
        const remaining = data.max_attempts - data.failed_attempts
        if (remaining > 0) {
          loginError.value = `${baseMsg}（已失败 ${data.failed_attempts} 次，还剩 ${remaining} 次机会将被锁定）`
        } else {
          loginError.value = `${baseMsg}（已达 ${data.max_attempts} 次上限，账号即将被锁定）`
        }
      } else {
        loginError.value = baseMsg
      }
    }
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100vh;
  background-color: var(--bg-color);
  position: relative;
}

/* 顶栏 */
.login-topbar {
  position: absolute;
  top: 0;
  right: 0;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 24px;
  z-index: 10;
}
.login-clock {
  font-size: 13px;
  font-family: 'SF Mono', 'Cascadia Code', 'Menlo', monospace;
  color: var(--text-muted);
  letter-spacing: 0.02em;
  white-space: nowrap;
  user-select: none;
}
.refresh-btn {
  border: none;
  background: transparent;
  color: var(--text-secondary);
  transition: all 0.2s;
}
.refresh-btn:hover {
  color: var(--primary-color);
  background: rgba(34, 197, 94, 0.08);
}

.login-tip {
  margin: -4px 0 12px;
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.6;
}
.login-card {
  width: 400px;
  max-width: calc(100vw - 32px);
}
.card-header {
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}
.logo-wrapper {
  width: 80px;
  height: 80px;
  border-radius: 12px;
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 8px;
  box-sizing: border-box;
}
:global(html.dark) .logo-wrapper {
  background: radial-gradient(circle, rgba(255,255,255,0.85) 0%, rgba(255,255,255,0) 70%);
}
.login-logo {
  width: 100%;
  height: 100%;
  object-fit: contain;
}
:global(html.dark) .login-logo {
  filter: drop-shadow(0px 0px 8px rgba(255, 255, 255, 0.6)) drop-shadow(0px 0px 2px rgba(255, 255, 255, 1));
}
.login-btn {
  width: 100%;
}

.login-error {
  margin-bottom: 12px;
  padding: 8px 12px;
  border-radius: 8px;
  background: #fef0f0;
  border: 1px solid #fde2e2;
  color: #f56c6c;
  font-size: 13px;
  line-height: 1.5;
}
:global(html.dark) .login-error {
  background: rgba(245, 108, 108, 0.12);
  border-color: rgba(245, 108, 108, 0.3);
}
.login-lockout {
  margin-bottom: 12px;
  padding: 10px 12px;
  border-radius: 8px;
  background: #fdf6ec;
  border: 1px solid #faecd8;
  color: #e6a23c;
  font-size: 13px;
  line-height: 1.5;
  display: flex;
  align-items: center;
}
.login-lockout strong {
  margin: 0 3px;
  font-size: 15px;
  color: #f56c6c;
}
:global(html.dark) .login-lockout {
  background: rgba(230, 162, 60, 0.12);
  border-color: rgba(230, 162, 60, 0.3);
}

.password-toggle {
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  color: var(--text-secondary);
}
.password-toggle:hover {
  color: var(--text-primary);
}

/* 清除浏览器自动填充背景色 */
:deep(.el-input__wrapper) {
  /* ... */
}
:deep(.el-input__inner:-webkit-autofill),
:deep(.el-input__inner:-webkit-autofill:hover),
:deep(.el-input__inner:-webkit-autofill:focus),
:deep(.el-input__inner:-webkit-autofill:active) {
  -webkit-text-fill-color: var(--text-primary) !important;
  transition: background-color 5000s ease-in-out 0s;
}
:global(html.dark) :deep(.el-input__wrapper) {
  background-color: var(--bg-color);
}
:global(html.dark) :deep(.el-input__inner:-webkit-autofill),
:global(html.dark) :deep(.el-input__inner:-webkit-autofill:hover),
:global(html.dark) :deep(.el-input__inner:-webkit-autofill:focus),
:global(html.dark) :deep(.el-input__inner:-webkit-autofill:active) {
  -webkit-text-fill-color: var(--text-primary) !important;
  -webkit-box-shadow: 0 0 0px 1000px var(--bg-color) inset !important;
  transition: background-color 5000s ease-in-out 0s;
}
</style>
