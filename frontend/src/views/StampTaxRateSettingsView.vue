<template>
  <div class="stamp-tax-rate-page">
    <el-card>
      <template #header>
        <div class="card-header">
          <div>
            <div class="card-title">印花税率设置</div>
            <div class="card-tip">维护“合同类型 -> 印花税率”映射，合同编辑时选择类型会自动带出对应税率。</div>
          </div>
        </div>
      </template>

      <div v-if="canManage" class="toolbar">
        <el-input
          v-model="newContractType"
          maxlength="64"
          show-word-limit
          placeholder="输入合同类型（最多64字）"
          style="max-width: 300px"
          @keyup.enter="addRow"
        />
        <el-input
          v-model="newTaxRate"
          maxlength="32"
          show-word-limit
          placeholder="输入税率（例如 0.03%）"
          style="max-width: 220px"
          @keyup.enter="addRow"
        />
        <el-button type="primary" :loading="creating" @click="addRow">新增映射</el-button>
      </div>
      <div v-else class="readonly-hint">当前账号仅有查看权限</div>

      <el-table :data="rows" stripe v-loading="loading">
        <el-table-column label="合同类型" min-width="280">
          <template #default="scope">
            <el-input
              v-if="canManage"
              v-model="scope.row.contract_type"
              maxlength="64"
              clearable
              placeholder="合同类型"
            />
            <span v-else>{{ scope.row.contract_type }}</span>
          </template>
        </el-table-column>

        <el-table-column label="印花税率" min-width="220">
          <template #default="scope">
            <el-input
              v-if="canManage"
              v-model="scope.row.tax_rate"
              maxlength="32"
              clearable
              placeholder="例如 0.03%"
            />
            <span v-else>{{ scope.row.tax_rate || '-' }}</span>
          </template>
        </el-table-column>

        <el-table-column prop="created_at" label="创建时间" min-width="220" />
        <el-table-column prop="updated_at" label="更新时间" min-width="220" />

        <el-table-column v-if="canManage" label="操作" width="180" fixed="right">
          <template #default="scope">
            <el-button
              type="primary"
              link
              :loading="savingRowId === scope.row.id"
              @click="saveRow(scope.row)"
            >
              保存
            </el-button>
            <el-button
              type="danger"
              link
              :loading="deletingRowId === scope.row.id"
              @click="removeRow(scope.row)"
            >
              删除
            </el-button>
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

const rows = ref([])
const loading = ref(false)
const creating = ref(false)
const savingRowId = ref(0)
const deletingRowId = ref(0)
const newContractType = ref('')
const newTaxRate = ref('')
const userPermission = ref('view')
const userRole = ref('admin')
const loginName = ref('')

const canManage = computed(() => {
  const normalized = String(loginName.value || '').trim().toLowerCase()
  return normalized === 'zhangyan' || ['super_admin', 'synology_super_admin'].includes(String(userRole.value || '').trim())
})

const loadCurrentPermission = async () => {
  try {
    const { data } = await http.get('/settings/users/current-permission')
    userRole.value = String(data?.role || 'admin').trim() || 'admin'
    loginName.value = String(data?.login_name || '').trim()
  } catch (_error) {
    userRole.value = 'admin'
    loginName.value = ''
  }
}

const loadRows = async () => {
  loading.value = true
  try {
    const { data } = await http.get('/settings/stamp-tax-rates')
    rows.value = Array.isArray(data) ? data : []
  } finally {
    loading.value = false
  }
}

const addRow = async () => {
  if (!canManage.value) {
    ElMessage.warning('当前账号仅有查看权限')
    return
  }

  const contractType = newContractType.value.trim()
  const taxRate = newTaxRate.value.trim()
  if (!contractType) {
    ElMessage.warning('请输入合同类型')
    return
  }

  creating.value = true
  try {
    await http.post('/settings/stamp-tax-rates', {
      contract_type: contractType,
      tax_rate: taxRate,
    })
    newContractType.value = ''
    newTaxRate.value = ''
    ElMessage.success('新增成功')
    await loadRows()
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || '新增失败')
  } finally {
    creating.value = false
  }
}

const saveRow = async (row) => {
  if (!canManage.value) {
    ElMessage.warning('当前账号仅有查看权限')
    return
  }

  const contractType = String(row?.contract_type || '').trim()
  const taxRate = String(row?.tax_rate || '').trim()
  if (!contractType) {
    ElMessage.warning('合同类型不能为空')
    return
  }

  savingRowId.value = Number(row?.id || 0)
  try {
    await http.put(`/settings/stamp-tax-rates/${row.id}`, {
      contract_type: contractType,
      tax_rate: taxRate,
    })
    ElMessage.success('保存成功')
    await loadRows()
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || '保存失败')
  } finally {
    savingRowId.value = 0
  }
}

const removeRow = async (row) => {
  if (!canManage.value) {
    ElMessage.warning('当前账号仅有查看权限')
    return
  }

  try {
    await ElMessageBox.confirm(`确认删除合同类型：${row.contract_type}？`, '提示', { type: 'warning' })
    deletingRowId.value = Number(row?.id || 0)
    await http.delete(`/settings/stamp-tax-rates/${row.id}`)
    ElMessage.success('删除成功')
    await loadRows()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error?.response?.data?.message || '删除失败')
    }
  } finally {
    deletingRowId.value = 0
  }
}

onMounted(async () => {
  try {
    await Promise.all([loadCurrentPermission(), loadRows()])
  } catch (_error) {
    ElMessage.error('印花税率列表加载失败')
  }
})
</script>

<style scoped>
.stamp-tax-rate-page {
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

.card-tip {
  margin-top: 4px;
  color: var(--el-text-color-secondary);
  font-size: 13px;
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
