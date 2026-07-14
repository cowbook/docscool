<template>
  <div class="user-permission-page">
    <el-card class="user-permission-card">
      <template #header>
        <div class="card-header">
          <div>
            <div class="card-title">用户权限</div>
            <div class="card-tip">如下列表的所有用户，将被加到群晖的docscool用户组，<b>超管</b> 默认拥有群晖合同管理部门、文件夹、参数设置，设置权限；
              金色图标是<b>群晖超管</b>，在群晖系统里拥有管理员权限，可对本用户权限页面进行设置。
              带胸章图标是本系统创建的用户。
            </div>

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
                :content="getLoginNameTooltip(scope.row)"
                placement="top"
              >
                <span
                  class="login-name-icon"
                  :class="getLoginNameIconClass(scope.row)"
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
        <el-table-column label="角色" width="140">
          <template #default="scope">
            <el-tag :type="getRoleTagType(scope.row.role)">
              {{ getRoleText(scope.row.role) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="描述" min-width="260" prop="description" />
        <el-table-column label="权限配置列表" min-width="760">
          <template #default="scope">
            <div class="permission-text-list">
              <div
                v-for="(item, index) in scope.row.permission_list"
                :key="`${scope.row.id}-${index}`"
                class="permission-text-item"
              >
                {{ index + 1 }}. {{ formatPermissionText(item) }}
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="320" fixed="right">
          <template #default="scope">
            <el-button type="primary" link @click="openPermissionEditDialog(scope.row)">
              编辑
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
        :title="isEditingUserDialog ? '编辑用户' : '创建用户'"
        width="810px"
        class="create-user-dialog"
        destroy-on-close
      >
        <div class="reset-password-tip">
          {{ isEditingUserDialog ? '当前为编辑模式，登录名不可修改' : '系统会先在群晖服务器创建用户，再加入 docscool 用户组，最后写入数据库' }}
        </div>
        <el-form label-width="96px" class="reset-password-form">
          <el-form-item label="登录名" required>
            <el-input
              v-model="createUserForm.login_name"
              maxlength="128"
              autocomplete="off"
              placeholder="仅允许小写字母、数字、下划线"
              :disabled="isEditingUserDialog"
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
          <el-form-item v-if="!isEditingUserDialog" label="密码" required>
            <el-input
              v-model="createUserForm.password"
              type="password"
              show-password
              autocomplete="new-password"
              placeholder="8位以上，包含大小写字母、数字和特殊字符"
            />
          </el-form-item>
          <el-form-item v-if="!isEditingUserDialog" label="密码验证">
            <el-input
              v-model="createUserForm.passwordConfirm"
              type="password"
              show-password
              autocomplete="new-password"
              placeholder="请再次输入密码"
            />
          </el-form-item>
          <el-form-item label="角色" required>
            <el-radio-group v-model="createUserForm.role" @change="handleCreateUserRoleChange">
              <el-radio value="synology_super_admin">群晖超管</el-radio>
              <el-radio value="super_admin">超管</el-radio>
              <el-radio value="admin">管理员</el-radio>
            </el-radio-group>
          </el-form-item>
          <div class="permission-edit-header create-permission-header">
            <el-button
              type="primary"
              link
              @click="createUserForm.permission_list = addPermissionBinding(createUserForm.permission_list)"
            >
              <el-icon><Plus /></el-icon>
              <span>新增权限</span>
            </el-button>
          </div>
          <el-table
            :data="createUserForm.permission_list"
            size="small"
            border
            class="permission-nested-table"
          >
            <el-table-column label="权限" width="180">
              <template #default="permissionScope">
                  <el-select
                    v-model="permissionScope.row.permission"
                    placeholder="请选择权限"
                    style="width: 100%"
                  >
                    <el-option label="编辑" value="edit" />
                    <el-option label="查看" value="view" />
                  </el-select>
              </template>
            </el-table-column>
            <el-table-column label="部门" min-width="260">
              <template #default="permissionScope">
                <el-select
                  :model-value="getPermissionBindingSingleValue(permissionScope.row.departments)"
                  @update:model-value="(value) => setPermissionBindingSingleValue(permissionScope.row, 'departments', value)"
                  filterable
                  clearable
                  :loading="departmentOptionsLoading"
                  placeholder="请选择部门"
                  style="width: 100%"
                >
                  <el-option
                    v-for="item in departmentOptions"
                    :key="`create-department-${item}`"
                    :label="item"
                    :value="item"
                  />
                </el-select>
              </template>
            </el-table-column>
            <el-table-column label="文件夹" min-width="280">
              <template #default="permissionScope">
                <el-select
                  :model-value="getPermissionBindingSingleValue(permissionScope.row.folders)"
                  @update:model-value="(value) => setPermissionBindingSingleValue(permissionScope.row, 'folders', value)"
                  filterable
                  clearable
                  :loading="folderOptionsLoading"
                  placeholder="请选择文件夹"
                  style="width: 100%"
                >
                  <el-option
                    v-for="item in folderOptions"
                    :key="`create-folder-${item}`"
                    :label="item"
                    :value="item"
                  />
                </el-select>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="90">
              <template #default="permissionScope">
                <el-button
                  type="danger"
                  link
                  @click="createUserForm.permission_list = removePermissionBinding(createUserForm.permission_list, permissionScope.$index)"
                >
                  删除
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-form>

        <template #footer>
          <div class="dialog-footer">
            <el-button @click="closeCreateUserDialog">取消</el-button>
            <el-button type="primary" :loading="createUserSubmitting" @click="submitCreateUser">
              {{ isEditingUserDialog ? '保存' : '确定' }}
            </el-button>
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

const ROLE_SUPER_ADMIN = 'super_admin'
const ROLE_ADMIN = 'admin'
const ROLE_SYNOLOGY_SUPER_ADMIN = 'synology_super_admin'
const SUPER_ROLE_SET = new Set([ROLE_SUPER_ADMIN, ROLE_SYNOLOGY_SUPER_ADMIN])

const rows = ref([])
const departmentOptions = ref([])
const folderOptions = ref([])
const syncWarnings = ref([])
const initialLoading = ref(true)
const addingUser = ref(false)
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
const userDialogMode = ref('create')
const editingUserId = ref(0)
const createUserForm = ref({
  login_name: '',
  name: '',
  password: '',
  passwordConfirm: '',
  role: 'admin',
  permission_list: [
    {
      permission: 'view',
      departments: [],
      folders: [],
    },
  ],
})
const currentPermission = ref('view')
const currentRole = ref('admin')
const currentLoginName = ref('')
const canManageUserAddDelete = computed(() => {
  if (SUPER_ROLE_SET.has(currentRole.value)) {
    return true
  }
  return currentLoginName.value.toLowerCase() === 'zhangyan'
})
const isEditingUserDialog = computed(() => userDialogMode.value === 'edit')

const normalizeDepartmentList = (value) => {
  const source = Array.isArray(value)
    ? value
    : (String(value || '').trim() ? [String(value || '').trim()] : [])
  const normalized = []
  const seen = new Set()
  source.forEach((item) => {
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

const normalizePermissionList = (value) => {
  const source = Array.isArray(value) ? value : []
  const normalized = source
    .map((item) => {
      const permission = String(item?.permission || '').trim()
      if (!['edit', 'view'].includes(permission)) {
        return null
      }
      const departments = normalizeDepartmentList(item?.departments)
      const folders = normalizeDepartmentList(item?.folders)
      return {
        permission,
        departments,
        folders,
      }
    })
    .filter(Boolean)

  if (normalized.length) {
    return normalized
  }

  return [{
    permission: 'view',
    departments: [],
    folders: [],
  }]
}

const getPermissionBindingSingleValue = (value) => {
  const normalized = normalizeDepartmentList(value)
  return normalized[0] || ''
}

const setPermissionBindingSingleValue = (row, field, value) => {
  const text = String(value || '').trim()
  row[field] = text ? [text] : []
}

const formatPermissionLabel = (permission) => {
  if (permission === 'edit') {
    return '编辑'
  }
  return '查看'
}

const formatPermissionText = (item) => {
  const permission = formatPermissionLabel(String(item?.permission || '').trim())
  const departments = normalizeDepartmentList(item?.departments)
  const folders = normalizeDepartmentList(item?.folders)
  const departmentText = departments.length ? departments.join('、') : '无'
  const folderText = folders.length ? folders.join('、') : '无'
  return `${permission} | 部门: ${departmentText} | 文件夹: ${folderText}`
}

const normalizeRoleValue = (role) => {
  const value = String(role || '').trim()
  if ([ROLE_SUPER_ADMIN, ROLE_ADMIN, ROLE_SYNOLOGY_SUPER_ADMIN].includes(value)) {
    return value
  }
  return ROLE_ADMIN
}

const getRoleText = (role) => {
  const value = normalizeRoleValue(role)
  if (value === ROLE_SUPER_ADMIN) {
    return '超管'
  }
  if (value === ROLE_SYNOLOGY_SUPER_ADMIN) {
    return '群晖超管'
  }
  return '管理员'
}

const getRoleTagType = (role) => {
  const value = normalizeRoleValue(role)
  if (value === ROLE_SUPER_ADMIN) {
    return 'danger'
  }
  if (value === ROLE_SYNOLOGY_SUPER_ADMIN) {
    return 'success'
  }
  return 'warning'
}

const getLoginNameIconClass = (row) => {
  if (row?.is_synology_admin) {
    return 'login-name-icon-synology-admin'
  }
  return row?.me_added ? 'login-name-icon-self-created' : 'login-name-icon-external'
}

const getLoginNameTooltip = (row) => {
  const baseText = row?.me_added ? '本用户由本系统创建' : '本用户不是由本系统创建'
  return row?.is_synology_admin ? `${baseText}（群晖管理员）` : baseText
}

const loadUsers = async () => {
  const { data } = await http.get('/settings/users')
  const list = Array.isArray(data?.users) ? data.users : []
  rows.value = list.map((item) => ({
    ...item,
    role: normalizeRoleValue(item?.role),
    department_list: normalizeDepartmentList(item.department_list),
    folder_list: normalizeDepartmentList(item.folder_list),
    permission_list: normalizePermissionList(item.permission_list),
  }))
  syncWarnings.value = Array.isArray(data?.warnings) ? data.warnings : []
}

const loadCurrentPermission = async () => {
  try {
    const { data } = await http.get('/settings/users/current-permission')
    currentPermission.value = String(data?.permission || 'view').trim() || 'view'
    currentRole.value = normalizeRoleValue(data?.role)
    currentLoginName.value = String(data?.login_name || '').trim()
  } catch (_error) {
    currentPermission.value = 'view'
    currentRole.value = ROLE_ADMIN
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
  userDialogMode.value = 'create'
  editingUserId.value = 0
  createUserForm.value = {
    login_name: '',
    name: '',
    password: '',
    passwordConfirm: '',
    role: ROLE_ADMIN,
    permission_list: [
      {
        permission: 'view',
        departments: [],
        folders: [],
      },
    ],
  }
  createUserDialogVisible.value = true
}

const closeCreateUserDialog = () => {
  createUserDialogVisible.value = false
  createUserSubmitting.value = false
  userDialogMode.value = 'create'
  editingUserId.value = 0
}

const enforceSuperRolePermissionList = (permissionList) => {
  return [{
    permission: 'edit',
    departments: ['全部'],
    folders: ['全部'],
  }]
}

const handleCreateUserRoleChange = (value) => {
  if (!SUPER_ROLE_SET.has(String(value || '').trim())) {
    return
  }
  createUserForm.value.permission_list = enforceSuperRolePermissionList(createUserForm.value.permission_list)
}

const submitCreateUser = async () => {
  if (!isEditingUserDialog.value && !canManageUserAddDelete.value) {
    ElMessage.warning('当前账号无新增/删除用户权限')
    return
  }

  const loginName = String(createUserForm.value.login_name || '').trim()
  const displayName = String(createUserForm.value.name || '').trim()
  const password = String(createUserForm.value.password || '').trim()
  const passwordConfirm = String(createUserForm.value.passwordConfirm || '').trim()
  const role = String(createUserForm.value.role || '').trim()

  if (!isEditingUserDialog.value) {
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
  }
  if (![ROLE_SUPER_ADMIN, ROLE_ADMIN, ROLE_SYNOLOGY_SUPER_ADMIN].includes(role)) {
    ElMessage.warning('请选择角色')
    return
  }
  const permissionList = SUPER_ROLE_SET.has(role)
    ? enforceSuperRolePermissionList(createUserForm.value.permission_list)
    : normalizePermissionList(createUserForm.value.permission_list)
  if (SUPER_ROLE_SET.has(role)) {
    createUserForm.value.permission_list = permissionList
  }
  if (!permissionList.length) {
    ElMessage.warning('请至少添加一条权限绑定')
    return
  }
  if (!isEditingUserDialog.value) {
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
  }

  createUserSubmitting.value = true
  try {
    if (isEditingUserDialog.value) {
      if (!editingUserId.value) {
        ElMessage.warning('未选择目标用户')
        return
      }
      await http.put(`/settings/users/${editingUserId.value}`, {
        description: displayName,
        role,
        permission_list: permissionList,
      })
      ElMessage.success('权限更新成功')
    } else {
      await http.post('/settings/users/create-user', {
        login_name: loginName,
        name: displayName,
        password,
        password_confirm: passwordConfirm,
        role,
        permission_list: permissionList,
      })
      ElMessage.success('创建成功')
    }
    closeCreateUserDialog()
    await reloadUsersWithTableLoading()
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || (isEditingUserDialog.value ? '权限更新失败' : '创建失败'))
  } finally {
    createUserSubmitting.value = false
  }
}

const openPermissionEditDialog = (row) => {
  userDialogMode.value = 'edit'
  editingUserId.value = Number(row?.id || 0)
  createUserForm.value = {
    login_name: String(row?.login_name || '').trim(),
    name: String(row?.description || '').trim(),
    password: '',
    passwordConfirm: '',
    role: normalizeRoleValue(row?.role),
    permission_list: normalizePermissionList(row?.permission_list),
  }
  if (SUPER_ROLE_SET.has(createUserForm.value.role)) {
    createUserForm.value.permission_list = enforceSuperRolePermissionList(createUserForm.value.permission_list)
  }
  createUserDialogVisible.value = true
}

const addPermissionBinding = (permissionList) => {
  const current = normalizePermissionList(permissionList)
  current.push({
    permission: 'view',
    departments: [],
    folders: [],
  })
  return current
}

const removePermissionBinding = (permissionList, index) => {
  const current = normalizePermissionList(permissionList)
  if (current.length <= 1) {
    ElMessage.warning('至少保留一条权限绑定')
    return current
  }
  current.splice(index, 1)
  return current
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
  font-size: 14px;
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

.permission-text-list {
  display: grid;
  gap: 6px;
}

.permission-text-item {
  line-height: 1.55;
  color: #374151;
}

.permission-nested-table {
  width: 100%;
}

.permission-edit-header {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 8px;
}

.permission-edit-header :deep(.el-button) {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

:deep(.create-user-dialog .el-dialog) {
  min-height: 90vh;
  margin-top: 5vh;
  display: flex;
  flex-direction: column;
}

:deep(.create-user-dialog .el-dialog__body) {
  flex: 1;
  overflow-y: auto;
}

.permission-role-form {
  margin-top: 10px;
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

.login-name-icon-synology-admin {
  color: #d4af37;
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

.login-name-icon-synology-admin .login-name-icon-badge {
  color: #d4af37;
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
