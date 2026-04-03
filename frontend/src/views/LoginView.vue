<template>
  <div class="login-page">
    <div class="login-box">
      <!-- Brand -->
      <div class="brand">
        <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="url(#lg)" stroke-width="2.5">
          <defs>
            <linearGradient id="lg" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stop-color="#6366f1"/>
              <stop offset="100%" stop-color="#8b5cf6"/>
            </linearGradient>
          </defs>
          <rect x="2" y="3" width="20" height="14" rx="2"/>
          <path d="M8 21h8M12 17v4"/>
        </svg>
        <span class="brand-name">EchoMatrix</span>
      </div>

      <h1 class="login-title">欢迎回来</h1>
      <p class="login-sub">登录你的控制台</p>

      <div class="form">
        <div class="field">
          <label>账号</label>
          <input
            v-model="form.username"
            type="text"
            placeholder="请输入账号"
            @keyup.enter="submit"
          />
        </div>
        <div class="field">
          <label>密码</label>
          <input
            v-model="form.password"
            :type="showPwd ? 'text' : 'password'"
            placeholder="请输入密码"
            @keyup.enter="submit"
          />
          <button class="eye-btn" type="button" @click="showPwd = !showPwd" tabindex="-1">
            <svg v-if="!showPwd" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
            <svg v-else width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>
          </button>
        </div>
        <button class="submit-btn" :class="{ loading: submitting }" @click="submit" :disabled="submitting">
          <span v-if="!submitting">登录</span>
          <span v-else class="spinner"></span>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { isDuplicateRequestError } from '../api/http'
import { login } from '../api/auth'
import { useAuth } from '../composables/useAuth'

const router = useRouter()
const { setToken } = useAuth()
const submitting = ref(false)
const showPwd = ref(false)
const form = reactive({ username: 'admin', password: '' })

async function submit() {
  if (submitting.value) return
  if (!form.username || !form.password) {
    ElMessage.warning('请输入账号和密码')
    return
  }
  submitting.value = true
  try {
    const result = await login({ username: form.username, password: form.password })
    setToken(result.access_token, result.username, result.is_admin)
    ElMessage.success('登录成功')
    router.replace('/dashboard')
  } catch (error) {
    if (isDuplicateRequestError(error)) return
    ElMessage.error(error?.response?.data?.detail || '登录失败')
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f8fafc;
  font-family: 'Inter', system-ui, sans-serif;
}

.login-box {
  width: min(400px, 92vw);
  background: white;
  border-radius: 20px;
  border: 1px solid #e2e8f0;
  padding: 40px;
  box-shadow: 0 8px 40px rgba(0,0,0,0.07);
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 32px;
}
.brand-name {
  font-size: 18px;
  font-weight: 900;
  letter-spacing: -0.03em;
  color: #0f172a;
}

.login-title {
  font-size: 24px;
  font-weight: 800;
  color: #0f172a;
  letter-spacing: -0.03em;
  margin-bottom: 6px;
}
.login-sub {
  font-size: 14px;
  color: #94a3b8;
  margin-bottom: 32px;
}

.form {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  position: relative;
}
.field label {
  font-size: 13px;
  font-weight: 600;
  color: #475569;
}
.field input {
  height: 44px;
  border: 1.5px solid #e2e8f0;
  border-radius: 10px;
  padding: 0 44px 0 14px;
  font-size: 14px;
  color: #0f172a;
  outline: none;
  transition: border-color 0.2s;
  background: #f8fafc;
  font-family: inherit;
}
.field input:focus {
  border-color: #6366f1;
  background: white;
}
.field input::placeholder { color: #cbd5e1; }

.eye-btn {
  position: absolute;
  right: 12px;
  bottom: 12px;
  background: none;
  border: none;
  cursor: pointer;
  color: #94a3b8;
  padding: 0;
  display: flex;
  align-items: center;
}
.eye-btn:hover { color: #475569; }

.submit-btn {
  height: 46px;
  background: #0f172a;
  color: white;
  border: none;
  border-radius: 10px;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-top: 4px;
  font-family: inherit;
}
.submit-btn:hover:not(:disabled) {
  background: #1d4ed8;
  transform: translateY(-1px);
  box-shadow: 0 6px 20px rgba(29,78,216,0.25);
}
.submit-btn:disabled { opacity: 0.7; cursor: not-allowed; }

.spinner {
  width: 18px;
  height: 18px;
  border: 2px solid rgba(255,255,255,0.3);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
</style>
