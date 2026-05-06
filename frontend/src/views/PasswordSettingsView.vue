<template>
  <section class="password-page">
    <div class="password-card">
      <div class="password-header">
        <h2>密码修改</h2>
        <p>请输入当前密码并设置新密码。</p>
      </div>

      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-position="top"
        class="password-form"
      >
        <el-form-item label="当前密码" prop="currentPassword">
          <el-input
            v-model="form.currentPassword"
            type="password"
            show-password
            autocomplete="current-password"
            placeholder="请输入当前密码"
          />
        </el-form-item>

        <el-form-item label="新密码" prop="newPassword">
          <el-input
            v-model="form.newPassword"
            type="password"
            show-password
            autocomplete="new-password"
            placeholder="请输入新密码（至少6位）"
          />
        </el-form-item>

        <el-form-item label="确认新密码" prop="confirmPassword">
          <el-input
            v-model="form.confirmPassword"
            type="password"
            show-password
            autocomplete="new-password"
            placeholder="请再次输入新密码"
            @keyup.enter="submit"
          />
        </el-form-item>

        <el-button type="primary" :loading="submitting" @click="submit">保存修改</el-button>
      </el-form>
    </div>
  </section>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRouter } from 'vue-router'
import http from '../api/http'

const router = useRouter()
const formRef = ref(null)
const submitting = ref(false)

const form = reactive({
  currentPassword: '',
  newPassword: '',
  confirmPassword: '',
})

const validateConfirmPassword = (_rule, value, callback) => {
  if (!value) {
    callback(new Error('请确认新密码'))
    return
  }

  if (value !== form.newPassword) {
    callback(new Error('两次输入的新密码不一致'))
    return
  }

  callback()
}

const rules = {
  currentPassword: [
    { required: true, message: '请输入当前密码', trigger: 'blur' },
  ],
  newPassword: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 6, message: '新密码至少 6 位', trigger: 'blur' },
  ],
  confirmPassword: [
    { validator: validateConfirmPassword, trigger: 'blur' },
  ],
}

const submit = async () => {
  if (!formRef.value) {
    return
  }

  try {
    await formRef.value.validate()
  } catch (_error) {
    return
  }

  submitting.value = true
  try {
    await http.post('/auth/change-password', {
      current_password: form.currentPassword,
      new_password: form.newPassword,
    })

    await ElMessageBox.alert('请使用新密码登录', '密码修改成功', {
      confirmButtonText: '确定',
      closeOnClickModal: false,
      closeOnPressEscape: false,
      showClose: false,
      type: 'success',
    })

    localStorage.removeItem('token')
    localStorage.removeItem('username')
    router.replace('/login')
  } catch (error) {
    if (error === 'cancel' || error === 'close') {
      return
    }
    const message = error?.response?.data?.message || '密码修改失败'
    ElMessage.error(message)
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.password-page {
  min-height: calc(100vh - 180px);
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding-top: 24px;
}

.password-card {
  width: min(520px, 100%);
  border-radius: 16px;
  border: 1px solid rgba(84, 123, 194, 0.18);
  background: rgba(255, 255, 255, 0.66);
  box-shadow: 0 14px 30px rgba(37, 60, 105, 0.08);
  padding: 20px;
}

.password-header h2 {
  margin: 0;
  font-size: 22px;
  color: #1b417b;
}

.password-header p {
  margin: 6px 0 0;
  font-size: 13px;
  color: #6480af;
}

.password-form {
  margin-top: 16px;
}

@media (max-width: 768px) {
  .password-page {
    padding-top: 12px;
  }

  .password-card {
    padding: 16px;
  }
}
</style>
