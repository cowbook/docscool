<template>
  <div class="user-permission-page">
    <el-card class="user-permission-card">
      <template #header>
        <div class="card-header">
          <div>
            <div class="card-title">用户权限</div>
            <div class="card-tip">本系统管理的用户权限对应群晖里的docscool用户组，超管权限拥有全部部门和文件夹的访问权限</div>
          </div>
          <el-button-group v-if="canManageUserAddDelete" class="apple-button-group">
            <el-button type="primary" :loading="addingUser" @click="addExistingUser">
              <el-icon><User /></el-icon>
              <span>添加用户</span>
            </el-button>
            <el-button type="success" :loading="createUserSubmitting" @click="openCreateUserDialog">
              <el-icon><Plus /></el-icon>
              <span>创建用户</span>
            </el-button>
          </el-button-group>
          <div v-else class="readonly-hint">当前账号仅可查看和编辑，不可新增或删除用户</div>
        </div>
      </template>

      <el-alert
        v-if="syncWarnings.length"
        title="群晖同步提示"
        type="warning"
        :closable="false"
        show-icon
        class="warning-box"
      >
        <template #default>
          <div v-for="(item, index) in syncWarnings" :key="`${index}-${item}`" class="warning-line">
            {{ item }}
          </div>
        </template>
      </el-alert>

      <el-table
        :data="rows"
        stripe
        v-loading="initialLoading"
        :empty-text="initialLoading ? '数据加载中...' : '暂无数据'"
      >
        <el-table-column label="登录名称" min-width="220">
          <template #default="scope">
            <div class="login-name-cell">
              <el-tooltip
                :content="scope.row.me_added ? '本用户由本系统创建' : '本用户不是由本系统创建'"
                placement="top"
              >
                <span
                  class="login-name-icon"
                  :class="scope.row.me_added ? 'login-name-icon-self-created' : 'login-name-icon-external'"
                  aria-hidden="true"
                >
                  <el-icon><User /></el-icon>
                  <el-icon v-if="scope.row.me_added" class="login-name-icon-badge"><Medal /></el-icon>
                </span>
              </el-tooltip>
              <span class="login-name-text">{{ scope.row.login_name }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="描述" min-width="260">
          <template #default="scope">
            <el-input
              v-model="scope.row.description"
              maxlength="255"
              clearable
              placeholder="请输入描述"
            />
          </template>
        </el-table-column>
        <el-table-column label="权限" min-width="250">
          <template #default="scope">
            <el-radio-group v-model="scope.row.permission">
              <el-radio value="super_admin">超管</el-radio>
              <el-radio value="edit">编辑</el-radio>
              <el-radio value="view">查看</el-radio>
            </el-radio-group>
          </template>
        </el-table-column>
        <el-table-column label="部门" min-width="320">
          <template #default="scope">
            <el-select
              v-model="scope.row.department_list"
              multiple
              filterable
              collapse-tags
              collapse-tags-tooltip
              clearable
              :loading="departmentOptionsLoading"
              loading-text="部门选项加载中..."
              placeholder="请选择部门"
              style="width: 100%"
            >
              <el-option
                v-for="item in departmentOptions"
                :key="item"
                :label="item"
                :value="item"
              >
                <span class="option-with-icon">
                  <el-icon><OfficeBuilding /></el-icon>
                  <span>{{ item }}</span>
                </span>
              </el-option>
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="文件夹" min-width="360">
          <template #default="scope">
            <el-select
              v-model="scope.row.folder_list"
              multiple
              filterable
              collapse-tags
              collapse-tags-tooltip
              clearable
              :loading="folderOptionsLoading"
              loading-text="文件夹选项加载中..."
              placeholder="请选择文件夹"
              style="width: 100%"
            >
              <el-option
                v-for="item in folderOptions"
                :key="item"
                :label="item"
                :value="item"
              >
                <span class="option-with-icon">
                  <el-icon><Folder /></el-icon>
                  <span>{{ item }}</span>
                </span>
              </el-option>
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="320" fixed="right">
          <template #default="scope">
            <el-button type="primary" link :loading="savingRowId === scope.row.id" @click="saveRow(scope.row)">
              保存
            </el-button>
            <el-button
              v-if="canManageUserAddDelete"
              type="warning"
              link
              :loading="removingRowId === scope.row.id"
              @click="removeRow(scope.row)"
            >
              移除
            </el-button>
            <el-button
              v-if="canManageUserAddDelete && scope.row.me_added"
              type="danger"
              link
              :loading="deletingRowId === scope.row.id"
              @click="deleteRow(scope.row)"
            >
              删除
            </el-button>
            <el-button type="warning" link :loading="resettingRowId === scope.row.id" @click="openResetPasswordDialog(scope.row)">
              重设密码
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-dialog
        v-model="resetPasswordDialogVisible"
        title="重设密码"
        width="460px"
        destroy-on-close
      >
        <div class="reset-password-tip">系统会直接重设群晖服务器用户密码</div>
        <el-form label-width="96px" class="reset-password-form">
          <el-form-item label="新密码">
            <el-input
              v-model="resetPasswordForm.password"
              type="password"
              show-password
              autocomplete="new-password"
              placeholder="请输入新密码"
            />
          </el-form-item>
          <el-form-item label="密码验证">
            <el-input
              v-model="resetPasswordForm.passwordConfirm"
              type="password"
              show-password
              autocomplete="new-password"
              placeholder="请再次输入新密码"
            />
          </el-form-item>
        </el-form>

        <template #footer>
          <div class="dialog-footer">
            <el-button @click="closeResetPasswordDialog">取消</el-button>
            <el-button type="primary" :loading="resetPasswordSubmitting" @click="submitResetPassword">确定</el-button>
          </div>
        </template>
      </el-dialog>

      <el-dialog
        v-model="createUserDialogVisible"
        title="创建用户"
        width="540px"
        destroy-on-close
      >
        <div class="reset-password-tip">系统会先在群晖服务器创建用户，再加入 docscool 用户组，最后写入数据库</div>
        <el-form label-width="96px" class="reset-password-form">
          <el-form-item label="登录名" required>
            <el-input
              v-model="createUserForm.login_name"
              maxlength="128"
              autocomplete="off"
              placeholder="仅允许小写字母、数字、下划线"
            />
          </el-form-item>
          <el-form-item label="姓名">
            <el-input
              v-model="createUserForm.name"
              maxlength="255"
              autocomplete="off"
              placeholder="可为空"
            />
          </el-form-item>
          <el-form-item label="密码" required>
            <el-input
              v-model="createUserForm.password"
              type="password"
              show-password
              autocomplete="new-password"
              placeholder="8位以上，包含大小写字母、数字和特殊字符"
            />
          </el-form-item>
          <el-form-item label="密码验证">
            <el-input
              v-model="createUserForm.passwordConfirm"
              type="password"
              show-password
              autocomplete="new-password"
              placeholder="请再次输入密码"
            />
          </el-form-item>
          <el-form-item label="权限" required>
            <el-radio-group v-model="createUserForm.permission" @change="handleCreateUserPermissionChange">
              <el-radio value="super_admin">超管</el-radio>
              <el-radio value="edit">编辑</el-radio>
              <el-radio value="view">查看</el-radio>
            </el-radio-group>
          </el-form-item>
          <el-form-item label="部门" required>
            <el-select
              v-model="createUserForm.department_list"
              multiple
              filterable
              collapse-tags
              collapse-tags-tooltip
              clearable
              :disabled="createUserForm.permission === 'super_admin'"
              :loading="departmentOptionsLoading"
              loading-text="部门选项加载中..."
              placeholder="请选择部门"
              style="width: 100%"
            >
              <el-option
                v-for="item in departmentOptions"
                :key="`create-department-${item}`"
                :label="item"
                :value="item"
              >
                <span class="option-with-icon">
                  <el-icon><OfficeBuilding /></el-icon>
                  <span>{{ item }}</span>
                </span>
              </el-option>
            </el-select>
          </el-form-item>
          <el-form-item label="文件夹" required>
            <el-select
              v-model="createUserForm.folder_list"
              multiple
              filterable
              collapse-tags
              collapse-tags-tooltip
              clearable
              :disabled="createUserForm.permission === 'super_admin'"
              :loading="folderOptionsLoading"
              loading-text="文件夹选项加载中..."
              placeholder="请选择文件夹"
              style="width: 100%"
            >
              <el-option
                v-for="item in folderOptions"
                :key="`create-folder-${item}`"
                :label="item"
                :value="item"
              >
                <span class="option-with-icon">
                  <el-icon><Folder /></el-icon>
                  <span>{{ item }}</span>
                </span>
              </el-option>
            </el-select>
          </el-form-item>
        </el-form>

        <template #footer>
          <div class="dialog-footer">
            <el-button @click="closeCreateUserDialog">取消</el-button>
            <el-button type="primary" :loading="createUserSubmitting" @click="submitCreateUser">确定</el-button>
          </div>
        </template>
      </el-dialog>
    </el-card>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Folder, Medal, OfficeBuilding, Plus, User } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'

import http from '../api/http'

const router = useRouter()

const rows = ref([])
const departmentOptions = ref([])
const folderOptions = ref([])
const syncWarnings = ref([])
const initialLoading = ref(true)
const addingUser = ref(false)
const savingRowId = ref(0)
const removingRowId = ref(0)
const deletingRowId = ref(0)
const resettingRowId = ref(0)
const departmentOptionsLoading = ref(true)
const folderOptionsLoading = ref(true)
const resetPasswordDialogVisible = ref(false)
const resetPasswordSubmitting = ref(false)
const resetPasswordTargetRow = ref(null)
const resetPasswordForm = ref({
  password: '',
  passwordConfirm: '',
})
const createUserDialogVisible = ref(false)
const createUserSubmitting = ref(false)
const createUserForm = ref({
  login_name: '',
  name: '',
  password: '',
  passwordConfirm: '',
  permission: 'view',
  department_list: [],
  folder_list: [],
})
const currentPermission = ref('view')
const currentLoginName = ref('')
const canManageUserAddDelete = computed(() => {
  if (currentPermission.value === 'super_admin') {
    return true
  }
  return currentLoginName.value.toLowerCase() === 'zhangyan'
})

const normalizeDepartmentList = (value) => {
  if (!Array.isArray(value)) {
    return []
  }
  const normalized = []
  const seen = new Set()
  value.forEach((item) => {
    const text = String(item || '').trim()
    if (!text || seen.has(text)) {
      return
    }
    seen.add(text)
    normalized.push(text)
  })
  return normalized
}

const normalizeDepartmentOptions = (value) => {
  const source = Array.isArray(value) ? value : []
  const normalized = []
  const seen = new Set(['全部'])
  source.forEach((item) => {
    const text = String(item || '').trim()
    if (!text || seen.has(text)) {
      return
    }
    seen.add(text)
    normalized.push(text)
  })
  return ['全部', ...normalized]
}

const loadUsers = async () => {
  const { data } = await http.get('/settings/users')
  const list = Array.isArray(data?.users) ? data.users : []
  rows.value = list.map((item) => ({
    ...item,
    department_list: normalizeDepartmentList(item.department_list),
    folder_list: normalizeDepartmentList(item.folder_list),
  }))
  syncWarnings.value = Array.isArray(data?.warnings) ? data.warnings : []
}

const loadCurrentPermission = async () => {
  try {
    const { data } = await http.get('/settings/users/current-permission')
    currentPermission.value = String(data?.permission || 'view').trim() || 'view'
    currentLoginName.value = String(data?.login_name || '').trim()
  } catch (_error) {
    currentPermission.value = 'view'
    currentLoginName.value = ''
  }
}

const reloadUsersWithTableLoading = async () => {
  initialLoading.value = true
  try {
    await loadUsers()
  } finally {
    initialLoading.value = false
  }
}

const loadDepartmentOptions = async () => {
  departmentOptionsLoading.value = true
  try {
    const { data } = await http.get('/settings/users/departments')
    departmentOptions.value = normalizeDepartmentOptions(data?.department_options)
  } catch (_error) {
    departmentOptions.value = ['全部']
    ElMessage.warning('部门选项加载失败')
  } finally {
    departmentOptionsLoading.value = false
  }
}

const loadFolderOptions = async () => {
  folderOptionsLoading.value = true
  try {
    const { data } = await http.get('/settings/users/folders')
    folderOptions.value = normalizeDepartmentOptions(data?.folder_options)
  } catch (_error) {
    folderOptions.value = ['全部']
    ElMessage.warning('文件夹选项加载失败')
  } finally {
    folderOptionsLoading.value = false
  }
}

const addExistingUser = async () => {
  if (!canManageUserAddDelete.value) {
    ElMessage.warning('当前账号无新增/删除用户权限')
    return
  }

  addingUser.value = true
  try {
    const { value } = await ElMessageBox.prompt('请输入群晖登录名称', '新建用户', {
      confirmButtonText: '确认',
      cancelButtonText: '取消',
      inputPattern: /^[a-zA-Z0-9._-]{1,128}$/,
      inputErrorMessage: '请输入合法登录名称（字母、数字、._-）',
    })
    const loginName = (value || '').trim()
    if (!loginName) {
      ElMessage.warning('登录名称不能为空')
      return
    }

    await http.post('/settings/users', { login_name: loginName })
    ElMessage.success('新建成功')
    await loadUsers()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error?.response?.data?.message || '新建失败')
    }
  } finally {
    addingUser.value = false
  }
}

const openCreateUserDialog = () => {
  createUserForm.value = {
    login_name: '',
    name: '',
    password: '',
    passwordConfirm: '',
    permission: 'view',
    department_list: [],
    folder_list: [],
  }
  createUserDialogVisible.value = true
}

const closeCreateUserDialog = () => {
  createUserDialogVisible.value = false
  createUserSubmitting.value = false
}

const handleCreateUserPermissionChange = (value) => {
  if (String(value || '').trim() !== 'super_admin') {
    return
  }
  createUserForm.value.department_list = ['全部']
  createUserForm.value.folder_list = ['全部']
}

const submitCreateUser = async () => {
  if (!canManageUserAddDelete.value) {
    ElMessage.warning('当前账号无新增/删除用户权限')
    return
  }

  const loginName = String(createUserForm.value.login_name || '').trim()
  const displayName = String(createUserForm.value.name || '').trim()
  const password = String(createUserForm.value.password || '').trim()
  const passwordConfirm = String(createUserForm.value.passwordConfirm || '').trim()
  const permission = String(createUserForm.value.permission || '').trim()

  if (!/^[a-z0-9_]+$/.test(loginName)) {
    ElMessage.warning('登录名仅允许连续的小写英文字母、数字和下划线')
    return
  }
  if (!password) {
    ElMessage.warning('请输入密码')
    return
  }
  if (!/^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z\d\s])[\S]{8,}$/.test(password)) {
    ElMessage.warning('密码必须为8位以上且包含大小写字母、数字和特殊字符')
    return
  }
  if (!passwordConfirm) {
    ElMessage.warning('请输入密码验证')
    return
  }
  if (password !== passwordConfirm) {
    ElMessage.warning('两次输入的密码不一致')
    return
  }
  if (!['super_admin', 'edit', 'view'].includes(permission)) {
    ElMessage.warning('请选择权限')
    return
  }
  if (!Array.isArray(createUserForm.value.department_list) || createUserForm.value.department_list.length === 0) {
    ElMessage.warning('请选择部门')
    return
  }
  if (!Array.isArray(createUserForm.value.folder_list) || createUserForm.value.folder_list.length === 0) {
    ElMessage.warning('请选择文件夹')
    return
  }
  const lowerPassword = password.toLowerCase()
  const loginNameText = loginName.toLowerCase().replace(/\s+/g, '')
  const displayNameText = displayName.toLowerCase().replace(/\s+/g, '')
  if (loginNameText && lowerPassword.replace(/\s+/g, '').includes(loginNameText)) {
    ElMessage.warning('密码不能包含登录名')
    return
  }
  if (displayNameText && lowerPassword.replace(/\s+/g, '').includes(displayNameText)) {
    ElMessage.warning('密码不能包含姓名描述')
    return
  }

  createUserSubmitting.value = true
  try {
    const normalizedDepartments = permission === 'super_admin'
      ? ['全部']
      : normalizeDepartmentList(createUserForm.value.department_list)
    const normalizedFolders = permission === 'super_admin'
      ? ['全部']
      : normalizeDepartmentList(createUserForm.value.folder_list)

    await http.post('/settings/users/create-user', {
      login_name: loginName,
      name: displayName,
      password,
      password_confirm: passwordConfirm,
      permission,
      departments: normalizedDepartments,
      folders: normalizedFolders,
    })
    ElMessage.success('创建成功')
    closeCreateUserDialog()
    await reloadUsersWithTableLoading()
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || '创建失败')
  } finally {
    createUserSubmitting.value = false
  }
}

const saveRow = async (row) => {
  savingRowId.value = row.id
  try {
    await http.put(`/settings/users/${row.id}`, {
      permission: row.permission,
      description: String(row.description || '').trim(),
      departments: normalizeDepartmentList(row.department_list),
      folders: normalizeDepartmentList(row.folder_list),
    })
    await reloadUsersWithTableLoading()
    ElMessage.success('保存成功')
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || '保存失败')
  } finally {
    savingRowId.value = 0
  }
}

const deleteRow = async (row) => {
  if (!canManageUserAddDelete.value) {
    ElMessage.warning('当前账号无新增/删除用户权限')
    return
  }

  try {
    await ElMessageBox.confirm(
      `确认删除用户 ${row.login_name} 吗？该操作会彻底删除群晖服务器上的用户，并同时删除数据库中的用户权限记录。`,
      '删除确认',
      {
        confirmButtonText: '确认删除',
        cancelButtonText: '取消',
        type: 'warning',
      },
    )
  } catch (_error) {
    return
  }

  deletingRowId.value = row.id
  try {
    const { data } = await http.delete(`/settings/users/${row.id}`)
    syncWarnings.value = Array.isArray(data?.warnings) ? data.warnings : []
    await reloadUsersWithTableLoading()
    ElMessage.success('删除成功')
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || '删除失败')
  } finally {
    deletingRowId.value = 0
  }
}

const removeRow = async (row) => {
  if (!canManageUserAddDelete.value) {
    ElMessage.warning('当前账号无新增/删除用户权限')
    return
  }

  try {
    await ElMessageBox.confirm(
      `确认从 docscool 用户组移除用户 ${row.login_name} 吗？该操作不会删除群晖账号，只会先从用户组移除，再删除数据库中的用户权限记录。`,
      '移除确认',
      {
        confirmButtonText: '确认移除',
        cancelButtonText: '取消',
        type: 'warning',
      },
    )
  } catch (_error) {
    return
  }

  removingRowId.value = row.id
  try {
    await http.post(`/settings/users/${row.id}/remove`)
    await reloadUsersWithTableLoading()
    ElMessage.success('移除成功')
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || '移除失败')
  } finally {
    removingRowId.value = 0
  }
}

const openResetPasswordDialog = (row) => {
  resetPasswordTargetRow.value = row
  resetPasswordForm.value = {
    password: '',
    passwordConfirm: '',
  }
  resetPasswordDialogVisible.value = true
}

const closeResetPasswordDialog = () => {
  resetPasswordDialogVisible.value = false
  resetPasswordSubmitting.value = false
}

const submitResetPassword = async () => {
  const target = resetPasswordTargetRow.value
  if (!target?.id) {
    ElMessage.warning('未选择目标用户')
    return
  }

  const password = String(resetPasswordForm.value.password || '').trim()
  const passwordConfirm = String(resetPasswordForm.value.passwordConfirm || '').trim()
  if (!password) {
    ElMessage.warning('请输入新密码')
    return
  }
  if (!passwordConfirm) {
    ElMessage.warning('请输入密码验证')
    return
  }
  if (password !== passwordConfirm) {
    ElMessage.warning('两次输入的新密码不一致')
    return
  }

  resetPasswordSubmitting.value = true
  resettingRowId.value = target.id
  try {
    await http.post(`/settings/users/${target.id}/reset-password`, {
      password,
      password_confirm: passwordConfirm,
    })
    ElMessage.success(`用户 ${target.login_name} 密码已重设`)
    closeResetPasswordDialog()
    localStorage.removeItem('token')
    localStorage.removeItem('username')
    router.replace('/login')
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || '重设密码失败')
  } finally {
    resetPasswordSubmitting.value = false
    resettingRowId.value = 0
  }
}

onMounted(async () => {
  try {
    await Promise.all([
      loadCurrentPermission(),
      reloadUsersWithTableLoading(),
    ])
    loadDepartmentOptions()
    loadFolderOptions()
  } catch (_error) {
    ElMessage.error('用户权限列表加载失败')
  }
})
</script>

<style scoped>
.user-permission-page {
  display: grid;
}

.user-permission-card {
  border-radius: 24px;
  overflow: hidden;
}

.user-permission-card :deep(.el-card__body) {
  padding: 20px 20px 18px;
}

.user-permission-card :deep(.el-table) {
  border-radius: 18px;
  overflow: hidden;
}

.user-permission-card :deep(.el-table__inner-wrapper) {
  border-radius: 18px;
  overflow: hidden;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.card-title {
  font-size: 18px;
  font-weight: 600;
}

.card-tip {
  margin-top: 6px;
  font-size: 12px;
  color: #6b7280;
}

.warning-box {
  margin-bottom: 16px;
}

.warning-line {
  line-height: 1.5;
}

.readonly-hint {
  color: #6b7280;
  font-size: 13px;
}

.apple-button-group {
  display: inline-flex;
  border-radius: 19px;
  padding: 2px;
  background: rgba(255, 255, 255, 0.9);
  border: 1px solid rgba(15, 23, 42, 0.08);
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.12), 0 2px 6px rgba(15, 23, 42, 0.08);
}

.apple-button-group :deep(.el-button) {
  border: none;
  border-radius: 0;
  min-height: 34px;
  padding: 0 16px;
  position: relative;
  color: #1f2937;
  font-weight: 600;
  background: linear-gradient(180deg, #ffffff 0%, #f9fefa 100%);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.95);
  transition: background 0.2s ease, color 0.2s ease, transform 0.2s ease;
}

.apple-button-group :deep(.el-button + .el-button) {
  margin-left: 0;
}

.apple-button-group :deep(.el-button + .el-button::before) {
  content: '';
  position: absolute;
  left: 0;
  top: 6px;
  bottom: 6px;
  width: 1px;
  background: rgba(15, 23, 42, 0.12);
  pointer-events: none;
}

.apple-button-group :deep(.el-button:first-child) {
  border-top-left-radius: 12px;
  border-bottom-left-radius: 12px;
}

.apple-button-group :deep(.el-button:last-child) {
  border-top-right-radius: 12px;
  border-bottom-right-radius: 12px;
}

.apple-button-group :deep(.el-button:not(.is-disabled):hover),
.apple-button-group :deep(.el-button:not(.is-disabled):focus-visible) {
  background: linear-gradient(180deg, #ffffff 0%, #e9eef8 100%);
  color: #1d4ed8;
}

.apple-button-group :deep(.el-button:not(.is-disabled):active) {
  transform: translateY(1px);
}

.option-with-icon {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.login-name-cell {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.login-name-icon {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  flex: 0 0 22px;
  font-size: 17px;
}

.login-name-icon-self-created {
  color: #2563eb;
}

.login-name-icon-external {
  color: #9ca3af;
}

.login-name-icon-badge {
  position: absolute;
  right: -4px;
  bottom: -3px;
  font-size: 11px;
  color: #2563eb;
  background: #ffffff;
  border-radius: 999px;
}

.login-name-text {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.reset-password-tip {
  margin-bottom: 12px;
  color: #6b7280;
  font-size: 13px;
}

.reset-password-form {
  margin-top: 8px;
}

@media (max-width: 900px) {
  .card-header {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
