<template>
  <div class="home-page">

    <div class="card-grid">
      <el-card class="stat-card">
        <div class="stat-content">
          <span class="stat-icon stat-icon-users" />
          <div>
            <div class="stat-title">总数量</div>
            <div class="stat-value">{{ statistics.total_count }}</div>
          </div>
        </div>
      </el-card>
      <el-card class="stat-card">
        <div class="stat-content">
          <span class="stat-icon stat-icon-money" />
          <div>
            <div class="stat-title">总金额</div>
            <div class="stat-value">{{ formatAmount(statistics.total_amount) }}</div>
          </div>
        </div>
      </el-card>
      <el-card class="stat-card">
        <div class="stat-content">
          <span class="stat-icon stat-icon-archive" />
          <div>
            <div class="stat-title">归档数量</div>
            <div class="stat-value">{{ statistics.archived_count }}</div>
          </div>
        </div>
      </el-card>
      <el-card class="stat-card">
        <div class="stat-content">
          <span class="stat-icon stat-icon-archivemoney" />
          <div>
            <div class="stat-title">归档金额</div>
            <div class="stat-value">{{ formatAmount(statistics.archived_amount) }}</div>
          </div>
        </div>
      </el-card>
    </div>

    <el-card class="empty-card">
      <template #header>
        <div class="empty-title">首页内容</div>
      </template>
      <div class="empty-text">预留区域</div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import http from '../api/http'

const statistics = ref({
  total_count: 0,
  total_amount: '0',
  archived_count: 0,
  archived_amount: '0',
})

function formatAmount(val) {
  // Add thousands separator and two decimals
  const num = Number(val)
  if (isNaN(num)) return val
  return num.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

const loadStatistics = async () => {
  try {
    const { data } = await http.get('/contracts/statistics')
    statistics.value = data || statistics.value
  } catch (_error) {
    ElMessage.error('统计数据加载失败')
  }
}

onMounted(loadStatistics)
</script>

<style scoped>
.stat-content {
  display: flex;
  align-items: center;
  gap: 16px;
}

.stat-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 56px;
  height: 56px;
  min-width: 56px;
  min-height: 56px;
  background: #f3f4f6;
  border-radius: 16px;
  margin-right: 8px;
}
.stat-icon-users::before {
  content: '';
  display: block;
  width: 48px;
  height: 48px;
  background-image: url('data:image/svg+xml;utf8,<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M12 12c2.761 0 5-2.239 5-5s-2.239-5-5-5-5 2.239-5 5 2.239 5 5 5zm0 2c-3.314 0-10 1.657-10 5v3h20v-3c0-3.343-6.686-5-10-5z" fill="%234F8EF7"/></svg>');
  background-size: contain;
  background-repeat: no-repeat;
}
.stat-icon-money::before {
  content: '';
  display: block;
  width: 48px;
  height: 48px;
  background-image: url('data:image/svg+xml;utf8,<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><rect x="2" y="6" width="20" height="12" rx="2" fill="%2334C759"/><path d="M12 8v8m0 0a2 2 0 100-4 2 2 0 000 4z" stroke="%23fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>');
  background-size: contain;
  background-repeat: no-repeat;
}
.stat-icon-archive::before {
  content: '';
  display: block;
  width: 48px;
  height: 48px;
  background-image: url('data:image/svg+xml;utf8,<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><rect x="3" y="4" width="18" height="4" rx="2" fill="%23F7B731"/><rect x="5" y="8" width="14" height="12" rx="2" fill="%23F7B731"/><path d="M9 12h6" stroke="%23fff" stroke-width="2" stroke-linecap="round"/></svg>');
  background-size: contain;
  background-repeat: no-repeat;
}
.stat-icon-archivemoney::before {
  content: '';
  display: block;
  width: 48px;
  height: 48px;
  background-image: url('data:image/svg+xml;utf8,<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><rect x="3" y="4" width="18" height="4" rx="2" fill="%23A259F7"/><rect x="5" y="8" width="14" height="12" rx="2" fill="%23A259F7"/><path d="M12 14v-2m0 0a2 2 0 100 4 2 2 0 000-4z" stroke="%23fff" stroke-width="2" stroke-linecap="round"/></svg>');
  background-size: contain;
  background-repeat: no-repeat;
}
.home-page {
  display: grid;
  gap: 16px;
}

.card-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
}

.stat-card {
  min-height: 120px;
  display: flex;
  align-items: center;
}

.stat-title {
  color: #6b7280;
  font-size: 14px;
  margin-bottom: 8px;
}

.stat-value {
  font-size: 30px;
  font-weight: 700;
  color: #111827;
}

.empty-title {
  font-weight: 600;
}

.empty-text {
  min-height: 180px;
  color: #9ca3af;
  display: flex;
  align-items: center;
  justify-content: center;
}

@media (max-width: 768px) {
  .card-grid {
    grid-template-columns: 1fr;
  }
}
</style>
