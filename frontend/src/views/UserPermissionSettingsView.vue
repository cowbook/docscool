<template>
  <div class="user-permission-page">
    <el-card>
      <template #header>
        <div class="card-header">
          <div>
            <div class="card-title">用户权限</div>
            <div class="card-tip">本系统管理的用户权限对应群晖里的docscool用户组</div>
          </div>
          <el-button-group class="apple-button-group">
            <el-button type="primary" :loading="creating" @click="createUser">新建用户</el-button>
          </el-button-group>
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

      <el-table :data="rows" stripe>
        <el-table-column prop="login_name" label="登录名称" min-width="180" />
        <el-table-column prop="description" label="描述" min-width="220" show-overflow-tooltip />
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
              placeholder="请选择部门"
              style="width: 100%"
            >
              <el-option
                v-for="item in departmentOptions"
                :key="item"
                :label="item"
                :value="item"
              />
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
              placeholder="请选择文件夹"
              style="width: 100%"
            >
              <el-option
                v-for="item in folderOptions"
                :key="item"
                :label="item"
                :value="item"
              />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="scope">
            <el-button type="primary" link :loading="savingRowId === scope.row.id" @click="saveRow(scope.row)">
              保存
            </el-button>
            <el-button type="danger" link :loading="deletingRowId === scope.row.id" @click="deleteRow(scope.row)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import http from '../api/http'

const rows = ref([])
const departmentOptions = ref([])
const folderOptions = ref([])
const syncWarnings = ref([])
const creating = ref(false)
const savingRowId = ref(0)
const deletingRowId = ref(0)

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
  departmentOptions.value = normalizeDepartmentOptions(data?.department_options)
  folderOptions.value = normalizeDepartmentOptions(data?.folder_options)
  syncWarnings.value = Array.isArray(data?.warnings) ? data.warnings : []
}

const createUser = async () => {
  creating.value = true
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
    creating.value = false
  }
}

const saveRow = async (row) => {
  savingRowId.value = row.id
  try {
    await http.put(`/settings/users/${row.id}`, {
      permission: row.permission,
      departments: normalizeDepartmentList(row.department_list),
      folders: normalizeDepartmentList(row.folder_list),
    })
    ElMessage.success('保存成功')
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || '保存失败')
  } finally {
    savingRowId.value = 0
  }
}

const deleteRow = async (row) => {
  try {
    await ElMessageBox.confirm(
      `确认删除用户 ${row.login_name} 吗？该操作会删除数据库中的用户权限记录。`,
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
    ElMessage.success('删除成功')
    await loadUsers()
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || '删除失败')
  } finally {
    deletingRowId.value = 0
  }
}

onMounted(async () => {
  try {
    await loadUsers()
  } catch (_error) {
    ElMessage.error('用户权限列表加载失败')
  }
})
</script>

<style scoped>
.user-permission-page {
  display: grid;
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

.apple-button-group {
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.82);
  border: 1px solid rgba(148, 163, 184, 0.35);
  box-shadow: 0 8px 20px rgba(15, 23, 42, 0.12);
  overflow: hidden;
}

.apple-button-group :deep(.el-button) {
  border: none;
  border-radius: 0;
  padding: 0 16px;
  height: 36px;
  font-weight: 600;
}

.apple-button-group :deep(.el-button:hover),
.apple-button-group :deep(.el-button:focus-visible) {
  background: rgba(37, 99, 235, 0.12);
}

.apple-button-group :deep(.el-button:active) {
  transform: translateY(1px);
}

@media (max-width: 900px) {
  .card-header {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
