<template>
  <div class="login-wrap">
    <div class="login-bg-orb login-bg-orb-a"></div>
    <div class="login-bg-orb login-bg-orb-b"></div>
    <div class="login-grid"></div>

    <div class="login-shell">
      <section class="login-hero">
        <div class="hero-chip">DocsCool Contract Hub</div>
        <h1 class="hero-title">AI合同管理</h1>
     

        <div class="hero-tags">
          <span>合同归档</span>
          <span>PDF 预览</span>
          <span>AI 识别</span>
          <span>NAS 协同</span>
        </div>

        <div class="hero-visual">
          <div class="hero-visual-ring"></div>
          <img :src="contractHero" alt="高效办公合同管理插图" class="hero-image" />
          <div class="hero-stat hero-stat-top">
            <strong>更快录入</strong>
            <span>上传 PDF 后自动抽取字段</span>
          </div>
          <div class="hero-stat hero-stat-bottom">
            <strong>更稳协同</strong>
            <span>文件与 NAS 权限保持一致</span>
          </div>
        </div>
      </section>

      <el-card class="login-card" shadow="never">
        <template #header>
          <div class="card-header">
            <div>
              <div class="eyebrow">Synology DSM 登录</div>
              <div class="title">合同管理系统登录</div>
            </div>
            <div class="header-badge">DocsCool</div>
          </div>
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
            <span class="option-hint">仅保存在当前浏览器</span>
          </div>

          <el-button :loading="loading" class="submit-button" native-type="submit" type="primary">
            登录系统
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
  position: relative;
  overflow: hidden;
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 32px;
  background:
    radial-gradient(circle at top left, rgba(248, 178, 87, 0.22), transparent 32%),
    radial-gradient(circle at bottom right, rgba(29, 161, 242, 0.18), transparent 28%),
    linear-gradient(135deg, #0b132b 0%, #102542 38%, #0f172a 100%);
}

.login-bg-orb {
  position: absolute;
  border-radius: 999px;
  filter: blur(32px);
  opacity: 0.72;
  pointer-events: none;
}

.login-bg-orb-a {
  width: 420px;
  height: 420px;
  top: -120px;
  left: -60px;
  background: rgba(255, 181, 71, 0.22);
}

.login-bg-orb-b {
  width: 480px;
  height: 480px;
  right: -120px;
  bottom: -180px;
  background: rgba(71, 165, 255, 0.2);
}

.login-grid {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(255, 255, 255, 0.06) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255, 255, 255, 0.06) 1px, transparent 1px);
  background-size: 44px 44px;
  mask-image: linear-gradient(180deg, rgba(0, 0, 0, 0.65), transparent 100%);
  pointer-events: none;
}

.login-shell {
  position: relative;
  z-index: 1;
  width: min(1180px, 100%);
  display: grid;
  grid-template-columns: minmax(0, 1.15fr) minmax(360px, 420px);
  gap: 28px;
  align-items: stretch;
}

.login-hero,
.login-card {
  border: 1px solid rgba(255, 255, 255, 0.16);
  box-shadow: 0 28px 80px rgba(3, 8, 20, 0.36);
  backdrop-filter: blur(22px);
}

.login-hero {
  position: relative;
  overflow: hidden;
  border-radius: 28px;
  padding: 32px 32px 20px;
  background: rgba(7, 18, 38, 0.42);
  color: #eef4ff;
}

.login-hero::after {
  content: '';
  position: absolute;
  inset: 14px;
  border-radius: 22px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  pointer-events: none;
}

.hero-chip {
  display: inline-flex;
  align-items: center;
  padding: 8px 14px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.09);
  color: #dbe7ff;
  font-size: 12px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.hero-title {
  margin: 18px 0 14px;
  max-width: 11ch;
  font-size: clamp(34px, 5vw, 58px);
  line-height: 1.04;
  font-weight: 700;
  letter-spacing: -0.04em;
}

.hero-text {
  max-width: 560px;
  margin: 0;
  color: rgba(233, 240, 255, 0.82);
  font-size: 16px;
  line-height: 1.8;
}

.hero-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 22px;
}

.hero-tags span {
  padding: 10px 14px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.08);
  color: #f8fbff;
  font-size: 13px;
}

.hero-visual {
  position: relative;
  margin-top: 28px;
  min-height: 420px;
  border-radius: 24px;
  padding: 30px 20px 8px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.08), rgba(255, 255, 255, 0.03));
  overflow: hidden;
}

.hero-visual-ring {
  position: absolute;
  width: 72%;
  aspect-ratio: 1;
  left: 50%;
  top: 52%;
  transform: translate(-50%, -50%);
  border-radius: 999px;
  background: radial-gradient(circle, rgba(88, 166, 255, 0.36), rgba(88, 166, 255, 0) 68%);
  filter: blur(10px);
}

.hero-image {
  position: relative;
  z-index: 1;
  display: block;
  width: min(100%, 470px);
  margin: 0 auto;
  color: #ffb347;
  filter: drop-shadow(0 24px 40px rgba(8, 13, 23, 0.38));
}

.hero-stat {
  position: absolute;
  z-index: 2;
  max-width: 220px;
  padding: 14px 16px;
  border: 1px solid rgba(255, 255, 255, 0.14);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.12);
  backdrop-filter: blur(18px);
  box-shadow: 0 18px 36px rgba(4, 12, 26, 0.2);
}

.hero-stat strong {
  display: block;
  margin-bottom: 6px;
  font-size: 14px;
  color: #ffffff;
}

.hero-stat span {
  display: block;
  color: rgba(244, 248, 255, 0.82);
  font-size: 12px;
  line-height: 1.6;
}

.hero-stat-top {
  top: 30px;
  right: 18px;
}

.hero-stat-bottom {
  left: 14px;
  bottom: 14px;
}

.login-card {
  width: 100%;
  border-radius: 28px;
  background: rgba(248, 250, 252, 0.88);
  border-color: rgba(255, 255, 255, 0.34);
  color: #0f172a;
}

.login-card :deep(.el-card__header) {
  padding-bottom: 12px;
  background: transparent;
  border-bottom-color: rgba(15, 23, 42, 0.08);
}

.login-card :deep(.el-card__body) {
  padding-top: 22px;
}

.login-card :deep(.el-form-item__label) {
  color: #1e293b;
  font-weight: 600;
}

.login-card :deep(.el-input__wrapper) {
  min-height: 46px;
  border-radius: 14px;
  box-shadow: 0 0 0 1px rgba(148, 163, 184, 0.25) inset;
}

.card-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.eyebrow {
  color: #ea580c;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.title {
  margin-top: 6px;
  font-size: 26px;
  line-height: 1.2;
  font-weight: 700;
  color: #0f172a;
}

.header-badge {
  padding: 8px 12px;
  border-radius: 999px;
  background: #fff4e8;
  color: #c2410c;
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
}

.login-form {
  display: flex;
  flex-direction: column;
}

.form-options {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin: 2px 0 18px;
}

.option-hint {
  color: #64748b;
  font-size: 12px;
  text-align: right;
}

.submit-button {
  width: 100%;
  min-height: 46px;
  border: none;
  border-radius: 16px;
  background: linear-gradient(135deg, #ff8a3d 0%, #ff5e3a 45%, #f97316 100%);
  box-shadow: 0 18px 36px rgba(249, 115, 22, 0.26);
}

.submit-button:hover {
  filter: brightness(1.02);
}

@media (max-width: 1100px) {
  .login-shell {
    width: min(460px, 100%);
    grid-template-columns: 1fr;
    justify-content: center;
  }

  .login-hero {
    display: none;
  }

  .login-card {
    margin: 0 auto;
  }
}

@media (max-width: 640px) {
  .login-wrap {
    padding: 18px;
  }

  .login-hero,
  .login-card {
    border-radius: 22px;
  }

  .login-hero {
    padding: 24px 20px 18px;
  }

  .hero-visual {
    min-height: 320px;
    padding-top: 20px;
  }

  .hero-stat {
    position: static;
    max-width: none;
    margin-top: 14px;
  }

  .card-header,
  .form-options {
    flex-direction: column;
    align-items: flex-start;
  }

  .option-hint {
    text-align: left;
  }
}
</style>
