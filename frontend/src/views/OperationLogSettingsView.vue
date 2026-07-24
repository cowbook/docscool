<template>
  <div class="operation-log-page">
    <el-card>
      <template #header>
        <div class="card-header">
          <div>
            <div class="card-title">操作日志</div>
            <div class="card-tip">默认展示本月日志，可按时间段筛选查看用户操作记录。</div>
          </div>
        </div>
      </template>

      <div class="toolbar">
        <el-date-picker
          v-model="dateRange"
          type="daterange"
          unlink-panels
          range-separator="至"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          value-format="YYYY-MM-DD"
        />
        <el-button type="primary" :loading="loading" @click="loadLogs">查询</el-button>
        <el-button :disabled="loading" @click="resetToCurrentMonth">本月</el-button>
      </div>

      <el-table
        :data="rows"
        stripe
        v-loading="loading"
        :empty-text="loading ? '日志加载中...' : '暂无日志'"
      >
        <el-table-column prop="record_time" label="记录时间" min-width="190" />
        <el-table-column prop="login_name" label="用户" min-width="140" />
        <el-table-column prop="operation_module" label="操作模块" min-width="120" />
        <el-table-column prop="operation_target" label="操作对象" min-width="180" show-overflow-tooltip />
        <el-table-column prop="operation_type" label="操作类型" min-width="100" />
        <el-table-column prop="detail" label="详细描述" min-width="520" show-overflow-tooltip />
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'

import http from '../api/http'

const loading = ref(false)
const rows = ref([])
const dateRange = ref([])

const pad2 = (value) => String(value).padStart(2, '0')

const toDateText = (date) => {
  const year = date.getFullYear()
  const month = pad2(date.getMonth() + 1)
  const day = pad2(date.getDate())
  return `${year}-${month}-${day}`
}

const resetToCurrentMonth = () => {
  const now = new Date()
  const monthStart = new Date(now.getFullYear(), now.getMonth(), 1)
  dateRange.value = [toDateText(monthStart), toDateText(now)]
}

const loadLogs = async () => {
  if (!Array.isArray(dateRange.value) || dateRange.value.length !== 2) {
    ElMessage.warning('请选择完整的开始和结束日期')
    return
  }

  loading.value = true
  try {
    const { data } = await http.get('/settings/user-logs', {
      params: {
        start_date: dateRange.value[0],
        end_date: dateRange.value[1],
      },
    })
    rows.value = Array.isArray(data?.rows) ? data.rows : []
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || '日志加载失败')
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  resetToCurrentMonth()
  await loadLogs()
})
</script>

<style scoped>
.operation-log-page {
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
  color: #6b7280;
  font-size: 13px;
}

.toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 16px;
}
</style>
