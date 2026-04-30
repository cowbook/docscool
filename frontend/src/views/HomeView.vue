<template>
  <div class="home-page">
   
      <div class="golden-layout">

        <div v-if="showFullLoading" class="home-loading">
          
          正在加载中...</div>

        <section v-else class="main-column">

          <div class="card-grid">
            <div class="stat-panel">
              <div class="stat-content">
                <span class="stat-icon stat-icon-users" />
                <div>
                  <div class="stat-title">总数量</div>
                  <div class="stat-value">{{ statistics.total_count }}</div>
                </div>
              </div>
            </div>

            <div class="stat-panel">
              <div class="stat-content">
                <span class="stat-icon stat-icon-money" />
                <div>
                  <div class="stat-title">总金额</div>
                  <div class="stat-value stat-value-amount">
                    <span class="stat-value-amount-number">{{ formatAmountCompactParts(statistics.total_amount).value }}</span>
                    <span class="stat-value-amount-unit">{{ formatAmountCompactParts(statistics.total_amount).unit }}</span>
                  </div>
                </div>
              </div>
            </div>

            <div class="stat-panel">
              <div class="stat-content">
                <span class="stat-icon stat-icon-archive" />
                <div>
                  <div class="stat-title">归档数量</div>
                  <div class="stat-value">{{ statistics.archived_count }}</div>
                </div>
              </div>
            </div>

            <div class="stat-panel">
              <div class="stat-content">
                <span class="stat-icon stat-icon-archivemoney" />
                <div>
                  <div class="stat-title">归档金额</div>
                  <div class="stat-value stat-value-amount">
                    <span class="stat-value-amount-number">{{ formatAmountCompactParts(statistics.archived_amount).value }}</span>
                    <span class="stat-value-amount-unit">{{ formatAmountCompactParts(statistics.archived_amount).unit }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div class="charts-area">
            <div class="chart-row chart-row-top">
              <section class="chart-panel chart-pie">
                <div class="chart-title">合同有无附件</div>
                <v-chart :option="optionContractFilePie" autoresize style="height:180px" />
              </section>
              <section class="chart-panel chart-pie">
                <div class="chart-title">存储文件有无合同挂载</div>
                <v-chart :option="optionFileContractPie" autoresize style="height:180px" />
              </section>
            </div>
            <div class="chart-row">
              <section class="chart-panel chart-bar">
                <div class="chart-title">各部门合同与文件数量</div>
                <v-chart :option="optionDeptBar" autoresize style="height:220px" />
              </section>
            </div>
            <div class="chart-row">
              <section class="chart-panel chart-placeholder">
                <div class="chart-title">（预留区域）</div>
              </section>
            </div>
          </div>
        </section>

        <aside class="side-column">

          <div class="side-placeholder">
            <div class="side-header">
              <div class="side-title">最新上传</div>
              <div class="side-subtitle">最近修改的合同文档</div>
            </div>

            <div v-if="latestLoading" class="side-loading">正在加载最新上传...</div>
            <div v-else-if="!latestFiles.length" class="side-empty">暂无可展示的文档</div>
            <div v-else class="latest-wrap">
              <div class="latest-grid">
                <button
                  v-for="item in latestFiles"
                  :key="`${item.file_path}-${item.mtime}`"
                  class="latest-card"
                  type="button"
                  @click="openLatestPreview(item)"
                >
                  <div class="latest-thumb-box">
                    <img
                      v-if="latestThumbMap[item.file_path]"
                      :src="latestThumbMap[item.file_path]"
                      :alt="item.name"
                      class="latest-thumb"
                    >
                    <div v-else class="latest-thumb-fallback">缩略图加载中</div>
                  </div>
                  <div class="latest-meta">
                    <div class="latest-name" :title="item.name">{{ item.name }}</div>
                    <div class="latest-desc">修改人：{{ item.modified_by || '-' }}</div>
                  </div>
                </button>
              </div>
            </div>
          </div>
        </aside>
      </div>

    <el-dialog
      v-model="previewVisible"
      fullscreen
      append-to-body
      destroy-on-close
      class="latest-preview-dialog"
    >
      <template #header>
        <div class="latest-preview-header">
          <span class="latest-preview-title" :title="activePreviewName">{{ activePreviewName }}</span>
        </div>
      </template>

      <div class="latest-preview-body">
        <iframe
          v-if="activePreviewUrl"
          :src="activePreviewUrl"
          class="latest-preview-frame"
          title="文件预览"
        />
        <div v-else class="latest-preview-empty">暂无可预览内容</div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>

import { computed, ref, onMounted, onBeforeUnmount, watch } from 'vue'
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
const latestLoading = ref(false)
const latestFiles = ref([])
const latestThumbMap = ref({})
const previewVisible = ref(false)
const activePreviewUrl = ref('')
const activePreviewName = ref('')

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

const revokeThumbUrls = () => {
  Object.values(latestThumbMap.value).forEach((url) => {
    if (url) {
      URL.revokeObjectURL(url)
    }
  })
  latestThumbMap.value = {}
}

const loadLatestThumbnails = async (rows) => {
  revokeThumbUrls()
  const loaded = {}

  await Promise.all(rows.map(async (item) => {
    try {
      const { data } = await http.get('/folders/file-thumbnail', {
        params: {
          path: item.file_path,
          mtime: item.mtime,
        },
        responseType: 'blob',
      })
      loaded[item.file_path] = URL.createObjectURL(data)
    } catch (_error) {
      loaded[item.file_path] = ''
    }
  }))

  latestThumbMap.value = loaded
}

const resolveErrorMessage = (error, fallbackMessage) => {
  const payload = error?.response?.data
  if (typeof payload === 'string' && payload.trim()) {
    return payload.trim()
  }
  if (payload && typeof payload === 'object' && typeof payload.message === 'string' && payload.message.trim()) {
    return payload.message.trim()
  }
  if (typeof error?.message === 'string' && error.message.trim()) {
    return error.message.trim()
  }
  return fallbackMessage
}

const redirectToLogin = () => {
  localStorage.removeItem('token')
  localStorage.removeItem('username')
  const basePath = (import.meta.env.BASE_URL || '/').replace(/\/$/, '')
  const loginPath = `${basePath}/login` || '/login'
  if (window.location.pathname !== loginPath) {
    window.location.href = loginPath
  }
}

const shouldRedirectToLogin = (statusCode, message) => {
  if (statusCode === 401) {
    return true
  }

  const normalized = String(message || '').toLowerCase()
  const expiredHints = [
    '会话已超时',
    '会话被中断',
    '会话无效',
    '重新登录',
    '凭据',
    'expired',
    'unauthorized',
    'invalid token',
  ]

  return expiredHints.some((hint) => normalized.includes(hint))
}

const loadLatestFiles = async () => {
  latestLoading.value = true
  try {
    const { data } = await http.get('/folders/latest-uploads', {
      params: { limit: 8 },
    })
    const files = Array.isArray(data?.files) ? data.files : []
    latestFiles.value = files
    await loadLatestThumbnails(files)
  } catch (_error) {
    const errorMessage = resolveErrorMessage(_error, '最新上传加载失败')
    if (shouldRedirectToLogin(_error?.response?.status, errorMessage)) {
      ElMessage.error('登录凭据已过期，请重新登录')
      redirectToLogin()
      return
    }

    latestFiles.value = []
    revokeThumbUrls()
    ElMessage.error(`最新上传加载失败：${errorMessage}`)
  } finally {
    latestLoading.value = false
  }
}

const releasePreviewUrl = () => {
  if (activePreviewUrl.value) {
    URL.revokeObjectURL(activePreviewUrl.value)
  }
  activePreviewUrl.value = ''
}

const openLatestPreview = async (item) => {
  try {
    releasePreviewUrl()
    const { data } = await http.get('/folders/file-preview', {
      params: { path: item.file_path },
      responseType: 'blob',
    })
    activePreviewUrl.value = URL.createObjectURL(data)
    activePreviewName.value = item.name || '文件预览'
    previewVisible.value = true
  } catch (_error) {
    ElMessage.error('文件预览失败')
  }
}

watch(previewVisible, (visible) => {
  if (!visible) {
    releasePreviewUrl()
  }
})

function formatAmountCompact(val) {
  const num = Number(val)
  if (!Number.isFinite(num)) return val

  const absNum = Math.abs(num)
  const sign = num < 0 ? '-' : ''

  const formatUnitValue = (value, unit) => {
    const display = value >= 1000 ? Math.round(value).toString() : value.toFixed(1).replace(/\.0$/, '')
    return `${sign}${display}${unit}`
  }

  if (absNum >= 1e8) {
    return formatUnitValue(absNum / 1e8, '亿')
  }

  if (absNum >= 1e4) {
    return formatUnitValue(absNum / 1e4, '万')
  }

  return `${sign}${absNum.toLocaleString()}元`
}

function formatAmountCompactParts(val) {
  const text = String(formatAmountCompact(val) ?? '')
  const unitMatch = text.match(/(亿|万|元)$/)
  if (!unitMatch) {
    return {
      value: text,
      unit: '',
    }
  }

  const unit = unitMatch[1]
  return {
    value: text.slice(0, -unit.length),
    unit,
  }
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
  loadLatestFiles()
})

onBeforeUnmount(() => {
  revokeThumbUrls()
  releasePreviewUrl()
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

.home-page {
  display: grid;
  min-width: 0;
}

.golden-layout {
  display: grid;
  grid-template-columns: minmax(260px, 0.78fr) minmax(0, 1.22fr);
  gap: 18px;
  align-items: start;
}

.main-column {
  display: grid;
  gap: 14px;
  min-width: 0;
}

.side-column {
  min-width: 0;
  min-height: 100%;
}

.side-placeholder {
  min-height: 500px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.36);
  border: 1px solid rgba(67, 108, 178, 0.18);
  display: flex;
  flex-direction: column;
  align-items: stretch;
  justify-content: flex-start;
  padding: 18px;
  color: #5a74a6;
}

.side-header {
  margin-bottom: 12px;
}

.side-title {
  font-size: 18px;
  font-weight: 650;
  margin-bottom: 2px;
}

.side-subtitle {
  font-size: 13px;
  opacity: 0.75;
}

.side-loading,
.side-empty {
  min-height: 220px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #6077a3;
}

.latest-wrap {
  padding-bottom: 4px;
}

.latest-grid {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  gap: clamp(10px, 0.9vw, 14px);
}

.latest-card {
  display: flex;
  flex-direction: column;
  flex: 0 1 168px;
  gap: clamp(6px, 0.6vw, 10px);
  min-width: 0;
  padding: 0;
  border: none;
  background: transparent;
  text-align: left;
  cursor: pointer;
}

.latest-thumb-box {
  width: min(100%, 168px);
  max-width: 168px;
  max-height: 232px;
  aspect-ratio: 21 / 29;
  border-radius: 12px;
  overflow: hidden;
  background: rgba(231, 238, 250, 0.8);
  border: 1px solid rgba(72, 112, 186, 0.18);
  transition: border-color 0.24s ease, box-shadow 0.24s ease, transform 0.24s ease;
}

.latest-thumb {
  width: 100%;
  height: 100%;
  display: block;
  object-fit: cover;
  transition: transform 0.28s ease;
  transform-origin: center center;
}

.latest-card:hover .latest-thumb,
.latest-card:focus-visible .latest-thumb {
  transform: scale(1.08);
}

.latest-card:hover .latest-thumb-box,
.latest-card:focus-visible .latest-thumb-box {
  border-color: rgba(72, 112, 186, 0.34);
  box-shadow: 0 12px 24px rgba(33, 64, 119, 0.16);
  transform: translateY(-6px);
}

.latest-thumb-fallback {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: clamp(11px, 0.82vw, 13px);
  color: #5f77a3;
}

.latest-meta {
  display: flex;
  flex-direction: column;
  gap: clamp(2px, 0.25vw, 4px);
}

.latest-name {
  font-size: clamp(11px, 0.78vw, 13px);
  font-weight: 600;
  color: #2e4f88;
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 3;
  line-clamp: 3;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: normal;
  line-height: 1.35;
}

.latest-desc {
  font-size: clamp(11px, 0.78vw, 12px);
  line-height: 1.35;
  color: #667da6;
}

.latest-preview-header {
  display: flex;
  align-items: center;
  min-width: 0;
}

.latest-preview-title {
  font-size: 16px;
  font-weight: 600;
  color: #2d4f87;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.latest-preview-body {
  height: calc(100vh - 96px);
}

.latest-preview-frame {
  width: 100%;
  height: 100%;
  border: none;
  border-radius: 8px;
  background: #fff;
}

.latest-preview-empty {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #5c73a0;
}

.charts-area {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.chart-row {
  display: flex;
  gap: 14px;
}

.chart-row-top {
  align-items: stretch;
}

.chart-panel {
  flex: 1;
  min-width: 0;
  min-height: 210px;
  display: flex;
  flex-direction: column;
  align-items: stretch;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.5);
  border: 1px solid rgba(76, 119, 197, 0.14);
  padding: 12px 14px;
}

.chart-title {
  font-weight: 600;
  font-size: 15px;
  margin-bottom: 8px;
  color: #2d4f87;
}

.stat-content {
  display: flex;
  align-items: center;
  gap: 12px;
}

.stat-panel {
  min-height: 108px;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.55);
  border: 1px solid rgba(77, 122, 202, 0.12);
  padding: 12px 14px;
  display: flex;
  align-items: center;
}

.stat-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 48px;
  height: 48px;
  min-width: 48px;
  min-height: 48px;
  background: rgba(243, 246, 252, 0.92);
  border-radius: 12px;
  margin-right: 4px;
}

.stat-icon-users::before {
  content: '';
  display: block;
  width: 40px;
  height: 40px;
  background-image: url('data:image/svg+xml;utf8,<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M12 12c2.761 0 5-2.239 5-5s-2.239-5-5-5-5 2.239-5 5 2.239 5 5 5zm0 2c-3.314 0-10 1.657-10 5v3h20v-3c0-3.343-6.686-5-10-5z" fill="%234F8EF7"/></svg>');
  background-size: contain;
  background-repeat: no-repeat;
}

.stat-icon-money::before {
  content: '';
  display: block;
  width: 40px;
  height: 40px;
  background-image: url('data:image/svg+xml;utf8,<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><rect x="2" y="6" width="20" height="12" rx="2" fill="%2334C759"/><path d="M12 8v8m0 0a2 2 0 100-4 2 2 0 000 4z" stroke="%23fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>');
  background-size: contain;
  background-repeat: no-repeat;
}

.stat-icon-archive::before {
  content: '';
  display: block;
  width: 40px;
  height: 40px;
  background-image: url('data:image/svg+xml;utf8,<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><rect x="3" y="4" width="18" height="4" rx="2" fill="%23F7B731"/><rect x="5" y="8" width="14" height="12" rx="2" fill="%23F7B731"/><path d="M9 12h6" stroke="%23fff" stroke-width="2" stroke-linecap="round"/></svg>');
  background-size: contain;
  background-repeat: no-repeat;
}

.stat-icon-archivemoney::before {
  content: '';
  display: block;
  width: 40px;
  height: 40px;
  background-image: url('data:image/svg+xml;utf8,<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><rect x="3" y="4" width="18" height="4" rx="2" fill="%23A259F7"/><rect x="5" y="8" width="14" height="12" rx="2" fill="%23A259F7"/><path d="M12 14v-2m0 0a2 2 0 100 4 2 2 0 000-4z" stroke="%23fff" stroke-width="2" stroke-linecap="round"/></svg>');
  background-size: contain;
  background-repeat: no-repeat;
}

.card-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
}

.stat-title {
  color: #6b7280;
  font-size: 13px;
  margin-bottom: 6px;
}

.stat-value {
  font-size: 34px;
  font-weight: 700;
  color: #183765;
  line-height: 1;
}

.stat-value-amount {
  font-size: 21px;
  line-height: 1.15;
}

.stat-value-amount-number {
  font-size: inherit;
}

.stat-value-amount-unit {
  margin-left: 2px;
  font-size: 14px;
  font-weight: 500;
  color: #90a0ba;
}

.chart-placeholder {
  min-height: 120px;
  justify-content: center;
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

@media (max-width: 1366px) {
  .golden-layout {
    grid-template-columns: minmax(240px, 0.72fr) minmax(0, 1.28fr);
  }

  .card-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .side-placeholder {
    padding: 16px;
  }

  .stat-value {
    font-size: 30px;
  }

  .stat-value-amount {
    font-size: 18px;
  }
}

@media (max-width: 1024px) {
  .golden-layout {
    grid-template-columns: minmax(220px, 0.64fr) minmax(0, 1.36fr);
    gap: 14px;
  }

  .side-placeholder {
    min-height: 260px;
    padding: 16px;
  }

  .chart-row-top {
    flex-direction: column;
  }

  .latest-grid {
    gap: 12px;
  }
}

@media (max-width: 768px) {
  .golden-layout {
    grid-template-columns: 1fr;
  }

  .side-column {
    min-height: 160px;
  }

  .card-grid {
    grid-template-columns: 1fr;
  }

  .latest-grid {
    gap: 10px;
  }

  .stat-panel {
    min-height: 96px;
  }

  .stat-icon {
    width: 44px;
    height: 44px;
    min-width: 44px;
    min-height: 44px;
  }

  .stat-icon-users::before,
  .stat-icon-money::before,
  .stat-icon-archive::before,
  .stat-icon-archivemoney::before {
    width: 34px;
    height: 34px;
  }

  .chart-row {
    flex-direction: column;
  }

  .stat-value {
    font-size: 28px;
  }

  .stat-value-amount {
    font-size: 17px;
  }
}

@media (max-width: 390px) {
  .side-placeholder {
    padding: 12px;
  }

  .latest-grid {
    gap: 10px;
  }

  .latest-card {
    gap: 6px;
  }

  .latest-name {
    font-size: 12px;
  }

  .latest-desc {
    font-size: 11px;
  }

  .chart-panel {
    padding: 10px 12px;
  }

  .chart-title {
    font-size: 14px;
  }
}
</style>
