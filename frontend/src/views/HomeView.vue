<template>
  <div class="home-page">
    <div class="card-grid">
      <el-card class="stat-card">
        <div class="stat-title">总数量</div>
        <div class="stat-value">{{ totalCount }}</div>
      </el-card>
      <el-card class="stat-card">
        <div class="stat-title">总金额</div>
        <div class="stat-value">{{ totalAmountText }}</div>
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
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'

import http from '../api/http'

const contracts = ref([])

const totalCount = computed(() => contracts.value.length)
const totalAmount = computed(() => contracts.value.reduce((sum, item) => {
  const value = Number(item.contract_amount_wan ?? item.amount)
  return sum + (Number.isFinite(value) ? value : 0)
}, 0))
const totalAmountText = computed(() => new Intl.NumberFormat('zh-CN', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
}).format(totalAmount.value))

const loadData = async () => {
  try {
    const { data } = await http.get('/contracts')
    contracts.value = Array.isArray(data) ? data : []
  } catch (_error) {
    ElMessage.error('首页数据加载失败')
  }
}

onMounted(loadData)
</script>

<style scoped>
.home-page {
  display: grid;
  gap: 16px;
}

.card-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
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
