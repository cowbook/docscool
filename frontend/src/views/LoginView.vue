<template>
  <div class="login-wrap">
    <div class="login-shell">
      <section class="login-illustration">
        <img :src="contractHero" alt="高效办公合同管理插图" class="illustration-image" />
      </section>

      <el-card class="login-card" shadow="never">
        <template #header>
          <div class="card-title">合同管理系统登录</div>
          <div class="card-subtitle">使用 Synology DSM 账号登录</div>
        </template>

        <el-form :model="form" label-position="top" class="login-form" @submit.prevent="submit">
          <el-form-item label="Synology 用户名">
            <el-input v-model="form.username" autocomplete="username" placeholder="请输入 DSM 用户名" />
          </el-form-item>
          <el-form-item label="密码">
            <el-input
              v-model="form.password"
              autocomplete="current-password"
              show-password
              type="password"
              placeholder="请输入密码"
            />
          </el-form-item>
          <el-form-item label="OTP 验证码（可选）">
            <el-input v-model="form.otp_code" placeholder="如启用二步验证，请输入 6 位验证码" />
          </el-form-item>

          <div class="form-options">
            <el-checkbox v-model="form.remember_password">记住密码</el-checkbox>
          </div>

          <el-button :loading="loading" class="submit-button" native-type="submit" type="primary">
            登录
          </el-button>
        </el-form>
      </el-card>
    </div>
  </div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import http from '../api/http'
import contractHero from '../assets/illustrations/contract-hero.svg'

const router = useRouter()
const loading = ref(false)
const REMEMBERED_LOGIN_KEY = 'docscool.remembered-login'
const REMEMBERED_LOGIN_SECRET_KEY = 'docscool.remembered-login.secret'
const REMEMBERED_LOGIN_TTL = 365 * 24 * 60 * 60 * 1000

const form = reactive({
  username: '',
  password: '',
  otp_code: '',
  remember_password: true,
})

const textEncoder = new TextEncoder()
const textDecoder = new TextDecoder()

const bytesToBase64 = (bytes) => window.btoa(String.fromCharCode(...bytes))

const base64ToBytes = (value) => Uint8Array.from(window.atob(value), (char) => char.charCodeAt(0))

const getRememberSecret = () => {
  let secret = localStorage.getItem(REMEMBERED_LOGIN_SECRET_KEY)
  if (!secret) {
    const randomBytes = window.crypto.getRandomValues(new Uint8Array(32))
    secret = bytesToBase64(randomBytes)
    localStorage.setItem(REMEMBERED_LOGIN_SECRET_KEY, secret)
  }
  return secret
}

const getRememberKey = async (username) => {
  const normalizedUsername = String(username || '').trim().toLowerCase()
  const keyMaterial = await window.crypto.subtle.importKey(
    'raw',
    textEncoder.encode(`${window.location.origin}|${normalizedUsername}|${getRememberSecret()}`),
    'PBKDF2',
    false,
    ['deriveKey'],
  )

  return window.crypto.subtle.deriveKey(
    {
      name: 'PBKDF2',
      salt: textEncoder.encode('docscool-login-remember-salt'),
      iterations: 120000,
      hash: 'SHA-256',
    },
    keyMaterial,
    {
      name: 'AES-GCM',
      length: 256,
    },
    false,
    ['encrypt', 'decrypt'],
  )
}

const encryptPassword = async (username, password) => {
  const iv = window.crypto.getRandomValues(new Uint8Array(12))
  const key = await getRememberKey(username)
  const encrypted = await window.crypto.subtle.encrypt(
    { name: 'AES-GCM', iv },
    key,
    textEncoder.encode(password),
  )

  return {
    iv: bytesToBase64(iv),
    cipher: bytesToBase64(new Uint8Array(encrypted)),
  }
}

const decryptPassword = async (username, encryptedPayload) => {
  const key = await getRememberKey(username)
  const decrypted = await window.crypto.subtle.decrypt(
    { name: 'AES-GCM', iv: base64ToBytes(encryptedPayload.iv) },
    key,
    base64ToBytes(encryptedPayload.cipher),
  )

  return textDecoder.decode(decrypted)
}

const clearRememberedLogin = () => {
  localStorage.removeItem(REMEMBERED_LOGIN_KEY)
}

const persistRememberedLogin = async () => {
  if (!form.remember_password) {
    clearRememberedLogin()
    return
  }

  if (!window.crypto?.subtle) {
    ElMessage.warning('当前浏览器不支持加密存储，将以明文方式记住密码')
    localStorage.setItem(
      REMEMBERED_LOGIN_KEY,
      JSON.stringify({
        username: form.username,
        password: form.password,
        iv: '',
        plaintext: true,
        expiresAt: Date.now() + REMEMBERED_LOGIN_TTL,
      }),
    )
    return
  }

  const encryptedPayload = await encryptPassword(form.username, form.password)
  localStorage.setItem(
    REMEMBERED_LOGIN_KEY,
    JSON.stringify({
      username: form.username,
      password: encryptedPayload.cipher,
      iv: encryptedPayload.iv,
        plaintext: false,
      expiresAt: Date.now() + REMEMBERED_LOGIN_TTL,
    }),
  )
}

const restoreRememberedLogin = async () => {
  const raw = localStorage.getItem(REMEMBERED_LOGIN_KEY)
  if (!raw) {
    return
  }

  try {
    const saved = JSON.parse(raw)
    if (!saved?.username || !saved?.expiresAt || saved.expiresAt < Date.now()) {
      clearRememberedLogin()
      return
    }

    form.username = saved.username
    form.remember_password = true

    if (saved.plaintext) {
      form.password = saved.password || ''
      return
    }

    if (!saved.password || !saved.iv || !window.crypto?.subtle) {
      return
    }

    form.password = await decryptPassword(saved.username, {
      cipher: saved.password,
      iv: saved.iv,
    })
  } catch (_error) {
    clearRememberedLogin()
  }
}

const handlePageVisible = async () => {
  if (document.visibilityState === 'visible') {
    await restoreRememberedLogin()
  }
}

const submit = async () => {
  if (!form.username || !form.password) {
    ElMessage.warning('请填写用户名和密码')
    return
  }

  loading.value = true
  try {
    const { data } = await http.post('/auth/login', {
      username: form.username,
      password: form.password,
      otp_code: form.otp_code,
    })
    await persistRememberedLogin()
    localStorage.setItem('token', data.token)
    localStorage.setItem('username', data.username)
    ElMessage.success('登录成功')
    router.push('/home')
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || '登录失败')
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await restoreRememberedLogin()
  document.addEventListener('visibilitychange', handlePageVisible)
})

onBeforeUnmount(() => {
  document.removeEventListener('visibilitychange', handlePageVisible)
})

restoreRememberedLogin()
</script>

<style scoped>
.login-wrap {
  min-height: 100vh;
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 32px;
  background: linear-gradient(135deg, #f4f7fb 0%, #edf2f9 100%);
}

.login-shell {
  width: min(980px, 100%);
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(340px, 400px);
  gap: 24px;
  align-items: center;
}

.login-illustration {
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 18px;
  border-radius: 24px;
  background: #ffffff;
  border: 1px solid #e2e8f0;
  box-shadow: 0 16px 42px rgba(15, 23, 42, 0.08);
}

.illustration-image {
  width: min(100%, 520px);
  max-height: 560px;
  object-fit: contain;
}

.login-card {
  width: 100%;
  border-radius: 20px;
  background: #ffffff;
  border: 1px solid #e2e8f0;
  box-shadow: 0 16px 42px rgba(15, 23, 42, 0.08);
  color: #0f172a;
}

.login-card :deep(.el-card__header) {
  padding-bottom: 10px;
  background: transparent;
  border-bottom-color: #e2e8f0;
}

.login-card :deep(.el-card__body) {
  padding-top: 18px;
}

.login-card :deep(.el-form-item__label) {
  color: #1e293b;
  font-weight: 600;
}

.login-card :deep(.el-input__wrapper) {
  min-height: 46px;
  border-radius: 12px;
  box-shadow: 0 0 0 1px rgba(148, 163, 184, 0.2) inset;
}

.card-title {
  font-size: 24px;
  font-weight: 700;
  color: #0f172a;
}

.card-subtitle {
  margin-top: 6px;
  color: #64748b;
  font-size: 13px;
}

.login-form {
  display: flex;
  flex-direction: column;
}

.form-options {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  margin: 2px 0 18px;
}

.submit-button {
  width: 100%;
  min-height: 46px;
  border: none;
  border-radius: 12px;
  background: #f97316;
  box-shadow: none;
}

.submit-button:hover {
  filter: brightness(1.02);
}

@media (max-width: 1024px) {
  .login-shell {
    width: min(460px, 100%);
    grid-template-columns: 1fr;
    justify-content: center;
  }

  .login-illustration {
    display: none;
  }
}

@media (max-width: 640px) {
  .login-wrap {
    padding: 16px;
  }
}
</style>
