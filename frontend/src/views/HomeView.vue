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

const parseDecimalParts = (value) => {
  const normalized = String(value ?? '')
    .trim()
    .replace(/[，,\s]/g, '')
    .replace(/。/g, '.')

  const match = normalized.match(/^([+-]?)(\d+)(?:\.(\d+))?$/)
  if (!match) {
    return null
  }

  return {
    negative: match[1] === '-',
    integer: match[2],
    fraction: match[3] || '',
  }
}

const sumDecimalStrings = (values) => {
  const parsedValues = values
    .map(parseDecimalParts)
    .filter(Boolean)

  if (!parsedValues.length) {
    return { total: 0n, scale: 0 }
  }

  const scale = parsedValues.reduce((maxScale, item) => Math.max(maxScale, item.fraction.length), 0)
  const total = parsedValues.reduce((sum, item) => {
    const digits = `${item.integer}${item.fraction.padEnd(scale, '0')}`
    const scaled = BigInt(digits || '0')
    return item.negative ? sum - scaled : sum + scaled
  }, 0n)

  return { total, scale }
}

const formatScaledDecimal = (total, scale) => {
  const negative = total < 0n
  const absolute = negative ? -total : total
  const raw = absolute.toString().padStart(scale + 1, '0')
  const integerPart = scale > 0 ? raw.slice(0, -scale) : raw
  const fractionPart = scale > 0 ? raw.slice(-scale) : ''
  const groupedInteger = integerPart.replace(/\B(?=(\d{3})+(?!\d))/g, ',')

  if (!fractionPart) {
    return `${negative ? '-' : ''}${groupedInteger}.00`
  }

  const trimmedFraction = fractionPart.replace(/0+$/, '')
  if (!trimmedFraction) {
    return `${negative ? '-' : ''}${groupedInteger}.00`
  }
  if (trimmedFraction.length === 1) {
    return `${negative ? '-' : ''}${groupedInteger}.${trimmedFraction}0`
  }

  return `${negative ? '-' : ''}${groupedInteger}.${trimmedFraction}`
}

const totalCount = computed(() => contracts.value.length)
const totalAmountState = computed(() => sumDecimalStrings(
  contracts.value.map((item) => item.contract_amount_wan ?? item.amount),
))
const totalAmountText = computed(() => formatScaledDecimal(totalAmountState.value.total, totalAmountState.value.scale))

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
