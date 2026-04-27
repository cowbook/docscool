<template>
  <div class="home-page">
    <div v-if="showFullLoading" class="home-loading">正在加载中...</div>
    <template v-else>
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

      <div class="charts-area">
        <div class="chart-row">
          <el-card class="chart-card chart-pie">
            <div class="chart-title">合同有无附件</div>
            <v-chart :option="optionContractFilePie" autoresize style="height:180px" />
          </el-card>
          <el-card class="chart-card chart-pie">
            <div class="chart-title">存储文件有无合同挂载</div>
            <v-chart :option="optionFileContractPie" autoresize style="height:180px" />
          </el-card>
          <el-card class="chart-card chart-bar">
            <div class="chart-title">各部门合同与文件数量</div>
            <v-chart :option="optionDeptBar" autoresize style="height:220px" />
          </el-card>
        </div>
        <div class="chart-row">
          <el-card class="chart-card">
            <div class="chart-title">（预留区域）</div>
          </el-card>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>

import { computed, ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import http from '../api/http'
import VChart from 'vue-echarts'
import * as echarts from 'echarts/core'
import { PieChart, BarChart } from 'echarts/charts'
import { TitleComponent, TooltipComponent, LegendComponent, GridComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([PieChart, BarChart, TitleComponent, TooltipComponent, LegendComponent, GridComponent, CanvasRenderer])

// 注册全局组件
const vChart = VChart

// 图表数据占位
const optionContractFilePie = ref({
  tooltip: { trigger: 'item' },
  legend: { bottom: 0 },
  series: [
    {
      name: '合同附件',
      type: 'pie',
      radius: '60%',
      data: [
        { value: 0, name: '有附件' },
        { value: 0, name: '无附件' },
      ],
      label: { formatter: '{b}: {d}%' },
    },
  ],
})

const optionFileContractPie = ref({
  tooltip: { trigger: 'item' },
  legend: { bottom: 0 },
  series: [
    {
      name: '文件挂载',
      type: 'pie',
      radius: '60%',
      data: [
        { value: 0, name: '已挂合同' },
        { value: 0, name: '未挂合同' },
      ],
      label: { formatter: '{b}: {d}%' },
    },
  ],
})

const optionDeptBar = ref({
  tooltip: { trigger: 'axis' },
  legend: { top: 0 },
  grid: { left: 40, right: 20, bottom: 30, top: 40 },
  xAxis: { type: 'category', data: [] },
  yAxis: { type: 'value' },
  series: [
    { name: '合同数量', type: 'bar', data: [] },
    { name: '文件数量', type: 'bar', data: [] },
  ],
})

const statistics = ref({
  total_count: 0,
  total_amount: '0',
  archived_count: 0,
  archived_amount: '0',
})

const HOME_DASHBOARD_CACHE_KEY = 'docscool.home.dashboard'
const HOME_DASHBOARD_CACHE_TTL = 5 * 60 * 1000

const backendLoading = ref(false)
const hasReadyData = ref(false)

const showFullLoading = computed(() => backendLoading.value && !hasReadyData.value)

const applyDashboardData = (stat, charts) => {
  if (stat) {
    statistics.value = {
      ...statistics.value,
      ...stat,
    }
  }

  if (charts) {
    optionContractFilePie.value.series[0].data = [
      { value: charts.contract_file_pie?.with_file ?? 0, name: '有附件' },
      { value: charts.contract_file_pie?.without_file ?? 0, name: '无附件' },
    ]
    optionFileContractPie.value.series[0].data = [
      { value: charts.file_contract_pie?.with_contract ?? 0, name: '已挂合同' },
      { value: charts.file_contract_pie?.without_contract ?? 0, name: '未挂合同' },
    ]
    optionDeptBar.value.xAxis.data = charts.dept_bar?.departments || []
    optionDeptBar.value.series[0].data = charts.dept_bar?.contract_counts || []
    optionDeptBar.value.series[1].data = charts.dept_bar?.file_counts || []
  }
}

const readDashboardCache = () => {
  try {
    const raw = localStorage.getItem(HOME_DASHBOARD_CACHE_KEY)
    if (!raw) {
      return null
    }
    const cached = JSON.parse(raw)
    const isExpired = !cached?.savedAt || Date.now() - cached.savedAt > HOME_DASHBOARD_CACHE_TTL
    if (isExpired) {
      localStorage.removeItem(HOME_DASHBOARD_CACHE_KEY)
      return null
    }
    if (!cached?.stat && !cached?.charts) {
      return null
    }
    return cached
  } catch (_error) {
    localStorage.removeItem(HOME_DASHBOARD_CACHE_KEY)
    return null
  }
}

const saveDashboardCache = (stat, charts) => {
  try {
    localStorage.setItem(
      HOME_DASHBOARD_CACHE_KEY,
      JSON.stringify({
        savedAt: Date.now(),
        stat,
        charts,
      }),
    )
  } catch (_error) {
    // Ignore storage failures (private mode/quota exceeded).
  }
}

function formatAmount(val) {
  // Add thousands separator and two decimals
  const num = Number(val)
  if (isNaN(num)) return val
  return num.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

const loadStatistics = async () => {
  backendLoading.value = true
  try {
    const [{ data: stat }, { data: charts }] = await Promise.all([
      http.get('/contracts/statistics'),
      http.get('/contracts/dashboard-charts'),
    ])
    applyDashboardData(stat, charts)
    hasReadyData.value = true
    saveDashboardCache(stat, charts)
  } catch (_error) {
    ElMessage.error('统计数据加载失败')
  } finally {
    backendLoading.value = false
  }
}

onMounted(() => {
  const cached = readDashboardCache()
  if (cached) {
    applyDashboardData(cached.stat, cached.charts)
    hasReadyData.value = true
  }

  loadStatistics()
})
</script>

<style scoped>
.home-loading {
  min-height: 60vh;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #6b7280;
  font-size: 22px;
  font-weight: 600;
  letter-spacing: 0.04em;
}

.charts-area {
  margin-top: 24px;
  display: flex;
  flex-direction: column;
  gap: 24px;
}
.chart-row {
  display: flex;
  gap: 24px;
}
.chart-card {
  flex: 1;
  min-width: 0;
  min-height: 220px;
  display: flex;
  flex-direction: column;
  align-items: stretch;
}
.chart-title {
  font-weight: 600;
  font-size: 16px;
  margin-bottom: 8px;
}
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
