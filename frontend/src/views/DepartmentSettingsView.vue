<template>
  <div class="department-page">
    <el-card>
      <template #header>
        <div class="card-header">
          <div class="card-title">部门设置</div>
        </div>
      </template>

      <div v-if="canManage" class="toolbar">
        <el-input
          v-model="newDepartment"
          maxlength="50"
          show-word-limit
          placeholder="输入部门名称（最多50字）"
          style="max-width: 360px"
          @keyup.enter="addDepartment"
        />
        <el-button type="primary" :loading="saving" @click="addDepartment">新增部门</el-button>
      </div>
      <div v-else class="readonly-hint">当前账号仅有查看权限</div>

      <el-table :data="departments" stripe>
        <el-table-column prop="name" label="部门名称" min-width="200" />
        <el-table-column label="现存" min-width="120">
          <template #default="scope">
            <el-select
              v-if="canManage"
              v-model="scope.row.is_existing"
              style="width: 100px"
            >
              <el-option :value="true" label="是" />
              <el-option :value="false" label="否" />
            </el-select>
            <span v-else>{{ scope.row.is_existing ? '是' : '否' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="现在部门" min-width="240">
          <template #default="scope">
            <el-input
              v-if="canManage"
              v-model="scope.row.current_department_name"
              maxlength="50"
              show-word-limit
              :disabled="scope.row.is_existing"
              placeholder="历史部门对应的当前部门"
            />
            <span v-else>{{ scope.row.current_department_name || '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" min-width="220" />
        <el-table-column v-if="canManage" label="操作" width="180" fixed="right">
          <template #default="scope">
            <el-button
              type="primary"
              size="small"
              :loading="savingRowId === scope.row.id"
              @click="saveDepartment(scope.row)"
            >
              保存
            </el-button>
            <el-button type="danger" size="small" @click="removeDepartment(scope.row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import http from '../api/http'

const departments = ref([])
const newDepartment = ref('')
const saving = ref(false)
const savingRowId = ref(0)
const userRole = ref('admin')
const canManage = computed(() => ['super_admin', 'synology_super_admin'].includes(userRole.value))

const normalizeExistingValue = (value) => {
  if (typeof value === 'boolean') return value
  if (typeof value === 'number') return value !== 0
  const text = String(value ?? '').trim().toLowerCase()
  return text === '1' || text === 'true' || text === 'yes' || text === 'y'
}

const loadDepartments = async () => {
  const { data } = await http.get('/settings/departments')
  departments.value = Array.isArray(data)
    ? data.map((item) => ({
      ...item,
      is_existing: normalizeExistingValue(item?.is_existing),
      current_department_name: String(item?.current_department_name || ''),
    }))
    : []
}

const loadCurrentPermission = async () => {
  try {
    const { data } = await http.get('/settings/users/current-permission')
    userRole.value = String(data?.role || 'admin').trim() || 'admin'
  } catch (_error) {
    userRole.value = 'admin'
  }
}

const addDepartment = async () => {
  if (!canManage.value) {
    ElMessage.warning('当前账号仅有查看权限')
    return
  }

  const name = newDepartment.value.trim()
  if (!name) {
    ElMessage.warning('请输入部门名称')
    return
  }
  if (name.length > 50) {
    ElMessage.warning('部门名称最多50字')
    return
  }

  saving.value = true
  try {
    await http.post('/settings/departments', { name })
    newDepartment.value = ''
    ElMessage.success('新增成功')
    await loadDepartments()
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || '新增失败')
  } finally {
    saving.value = false
  }
}

const saveDepartment = async (row) => {
  if (!canManage.value) {
    ElMessage.warning('当前账号仅有查看权限')
    return
  }

  const isExisting = !!row.is_existing
  const currentDepartmentName = String(row.current_department_name || '').trim()
  if (!isExisting && !currentDepartmentName) {
    ElMessage.warning('历史部门请填写“现在部门”')
    return
  }

  savingRowId.value = row.id
  try {
    await http.put(`/settings/departments/${row.id}`, {
      is_existing: isExisting,
      current_department_name: currentDepartmentName,
    })
    ElMessage.success('保存成功')
    await loadDepartments()
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || '保存失败')
  } finally {
    savingRowId.value = 0
  }
}

const removeDepartment = async (row) => {
  if (!canManage.value) {
    ElMessage.warning('当前账号仅有查看权限')
    return
  }

  try {
    await ElMessageBox.confirm(`确认删除部门：${row.name}？`, '提示', {
      type: 'warning',
    })
    await http.delete(`/settings/departments/${row.id}`)
    ElMessage.success('删除成功')
    await loadDepartments()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error?.response?.data?.message || '删除失败')
    }
  }
}

onMounted(async () => {
  try {
    await Promise.all([loadCurrentPermission(), loadDepartments()])
  } catch (_error) {
    ElMessage.error('部门列表加载失败')
  }
})
</script>

<style scoped>
.department-page {
  display: grid;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.card-title {
  font-size: 18px;
  font-weight: 600;
}

.toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 16px;
}

.readonly-hint {
  margin-bottom: 16px;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
</style>
