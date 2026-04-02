<template>
  <div class="login-wrap">
    <el-card class="login-card">
      <template #header>
        <div class="title">合同管理系统登录</div>
      </template>

      <el-form :model="form" label-position="top" @submit.prevent="submit">
        <el-form-item label="Synology 用户名">
          <el-input v-model="form.username" placeholder="请输入 DSM 用户名" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="form.password" show-password type="password" placeholder="请输入密码" />
        </el-form-item>
        <el-form-item label="OTP 验证码（可选）">
          <el-input v-model="form.otp_code" placeholder="如启用二步验证，请输入 6 位验证码" />
        </el-form-item>
        <el-button :loading="loading" type="primary" style="width: 100%" @click="submit">
          登录
        </el-button>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import http from '../api/http'

const router = useRouter()
const loading = ref(false)
const form = reactive({
  username: '',
  password: '',
  otp_code: '',
})

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
</script>

<style scoped>
.login-wrap {
  min-height: 100vh;
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 24px;
}

.login-card {
  width: 420px;
  max-width: 100%;
}

.title {
  font-size: 18px;
  font-weight: 600;
}
</style>
