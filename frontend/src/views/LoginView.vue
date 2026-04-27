<template>
  <div class="login-wrap">
    <div class="pipeline-bg" aria-hidden="true">
      <svg class="pipeline-svg" viewBox="0 0 1200 700" aria-hidden="true">
        <path
          class="pipeline-line"
          d="M -40 150 H 252 A 96 96 0 0 1 348 246 V 430 A 48 48 0 0 0 396 478 H 840 A 48 48 0 0 0 888 430 V 260 A 48 48 0 0 1 936 212 H 1240"
        />
        <path
          class="pipeline-line"
          d="M -40 198 H 252 A 48 48 0 0 1 300 246 V 382 A 48 48 0 0 0 348 430 H 792 A 48 48 0 0 0 840 382 V 212 A 48 48 0 0 1 888 164 H 1240"
        />
        <path
          class="pipeline-fluid pipeline-fluid-base"
          d="M -40 174 H 252 A 72 72 0 0 1 324 246 V 406 A 48 48 0 0 0 372 454 H 816 A 48 48 0 0 0 864 406 V 236 A 48 48 0 0 1 912 188 H 1240"
        />
        <path
          class="pipeline-fluid pipeline-fluid-light"
          d="M -40 174 H 252 A 72 72 0 0 1 324 246 V 406 A 48 48 0 0 0 372 454 H 816 A 48 48 0 0 0 864 406 V 236 A 48 48 0 0 1 912 188 H 1240"
        />
        <path
          class="pipeline-fluid pipeline-fluid-dark"
          d="M -40 174 H 252 A 72 72 0 0 1 324 246 V 406 A 48 48 0 0 0 372 454 H 816 A 48 48 0 0 0 864 406 V 236 A 48 48 0 0 1 912 188 H 1240"
        />

        <g class="valve-svg" transform="translate(150 174)">
          <circle class="valve-ring" r="38" />
          <circle class="valve-inner" r="26" />
          <g class="valve-rotor">
            <line class="valve-bar" x1="0" y1="-30" x2="0" y2="30" />
            <path class="valve-wing" d="M -18 -9 L -2 0 L -18 9 Z" />
            <path class="valve-wing" d="M 18 -9 L 2 0 L 18 9 Z" />
          </g>
        </g>

        <g class="valve-svg" transform="translate(324 314)">
          <circle class="valve-ring" r="38" />
          <circle class="valve-inner" r="26" />
          <g class="valve-rotor">
            <line class="valve-bar" x1="0" y1="-30" x2="0" y2="30" />
            <path class="valve-wing" d="M -18 -9 L -2 0 L -18 9 Z" />
            <path class="valve-wing" d="M 18 -9 L 2 0 L 18 9 Z" />
          </g>
        </g>

        <g class="valve-svg" transform="translate(620 454)">
          <circle class="valve-ring" r="38" />
          <circle class="valve-inner" r="26" />
          <g class="valve-rotor">
            <line class="valve-bar" x1="0" y1="-30" x2="0" y2="30" />
            <path class="valve-wing" d="M -18 -9 L -2 0 L -18 9 Z" />
            <path class="valve-wing" d="M 18 -9 L 2 0 L 18 9 Z" />
          </g>
        </g>

        <g class="valve-svg" transform="translate(1080 188)">
          <circle class="valve-ring" r="38" />
          <circle class="valve-inner" r="26" />
          <g class="valve-rotor">
            <line class="valve-bar" x1="0" y1="-30" x2="0" y2="30" />
            <path class="valve-wing" d="M -18 -9 L -2 0 L -18 9 Z" />
            <path class="valve-wing" d="M 18 -9 L 2 0 L 18 9 Z" />
          </g>
        </g>
      </svg>
    </div>

    <div class="login-shell">
      <section class="login-illustration">
        <img :src="contractHero" alt="高效办公合同管理插图" class="illustration-image" />
      </section>

      <section class="login-panel">
        <div class="card-title">合同管理系统登录</div>
        <div class="card-subtitle">使用 Synology DSM 账号登录</div>
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
      </section>
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
  background: linear-gradient(145deg, #f8fafd 0%, #f2f6fb 52%, #eef3f9 100%);
}

.pipeline-bg {
  position: absolute;
  inset: 0;
  pointer-events: none;
  z-index: 0;
}

.pipeline-svg {
  position: absolute;
  width: 1200px;
  height: 700px;
  left: 50%;
  top: 50%;
  transform: translate(-50%, -50%) scaleY(-1);
}

.pipeline-bg {
  --pipeline-ink: rgba(124, 138, 156, 0.34);
}

.pipeline-line {
  fill: none;
  stroke: var(--pipeline-ink);
  stroke-width: 2.5;
  stroke-linecap: butt;
  stroke-linejoin: miter;
}

.pipeline-fluid {
  fill: none;
  stroke-linecap: butt;
  stroke-linejoin: miter;
}

.pipeline-fluid-base {
  stroke: rgba(148, 163, 184, 0.12);
  stroke-width: 34;
}

.pipeline-fluid-light {
  stroke: rgba(248, 250, 252, 0.58);
  stroke-width: 18;
  stroke-dasharray: 140 180;
  animation: fluidMove 7.2s linear infinite;
}

.pipeline-fluid-dark {
  stroke: rgba(100, 116, 139, 0.14);
  stroke-width: 24;
  stroke-dasharray: 220 260;
  animation: fluidMoveSoft 11s linear infinite;
}

.valve-svg {
  filter: drop-shadow(0 1px 0 rgba(15, 23, 42, 0.08));
}

.valve-ring {
  fill: rgba(248, 250, 252, 0.92);
  stroke: var(--pipeline-ink);
  stroke-width: 3;
}

.valve-inner {
  fill: rgba(248, 250, 252, 0.96);
  stroke: var(--pipeline-ink);
  stroke-width: 2.2;
}

.valve-rotor {
  animation: valveSpin 2.4s linear infinite;
  transform-origin: center center;
  transform-box: fill-box;
}

.valve-bar {
  stroke: var(--pipeline-ink);
  stroke-width: 7;
  stroke-linecap: round;
}

.valve-wing {
  fill: none;
  stroke: var(--pipeline-ink);
  stroke-width: 4;
  stroke-linejoin: round;
}

.login-shell {
  width: min(980px, 100%);
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(340px, 400px);
  gap: 24px;
  align-items: center;
  position: relative;
  z-index: 1;
}

.login-illustration {
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 12px;
}

.illustration-image {
  width: min(100%, 520px);
  max-height: 560px;
  object-fit: contain;
  filter: drop-shadow(0 10px 28px rgba(15, 23, 42, 0.06));
}

.login-panel {
  width: 100%;
  padding: 50px 30px;
  border-radius: 25px;
  background: rgba(0, 0, 0, 0.08);
  backdrop-filter: blur(1px);
  -webkit-backdrop-filter: blur(1px);
  color: #0f172a;
}

.login-panel :deep(.el-form-item__label) {
  color: #1e293b;
  font-weight: 600;
}

.login-panel :deep(.el-input__wrapper) {
  min-height: 46px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.8);
  box-shadow: 0 0 0 1px rgba(148, 163, 184, 0.16) inset;
}

.card-title {
  font-size: 23px;
  font-weight: 700;
  color: #0f172a;
}

.card-subtitle {
  margin-top: 4px;
  margin-bottom: 10px;
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
  background: #fb923c;
  box-shadow: none;
}

.submit-button:hover {
  filter: brightness(1.04);
}

@keyframes valveSpin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

@keyframes fluidMove {
  from {
    stroke-dashoffset: 0;
  }
  to {
    stroke-dashoffset: -320;
  }
}

@keyframes fluidMoveSoft {
  from {
    stroke-dashoffset: 0;
  }
  to {
    stroke-dashoffset: -520;
  }
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

  .pipeline-svg {
    left: 45%;
  }
}

@media (max-width: 640px) {
  .login-wrap {
    padding: 16px;
  }

  .login-panel {
    padding: 8px 2px;
  }

  .pipeline-svg {
    left: 40%;
  }
}
</style>
