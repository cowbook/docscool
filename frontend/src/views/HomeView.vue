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
              <section class="chart-placeholder">
                <div class="chart-title">（预留区域）</div>
              </section>
            </div>
          </div>
        </section>

        <aside class="side-column">

          
          <div class="side-placeholder side-placeholder-compact">
            <div class="side-header">
              <div class="side-title">扫描仪</div>
              <div class="side-subtitle">扫描存储里最新的 PDF 文件</div>
            </div>

            <div v-if="scannerLoading" class="side-loading side-loading-compact">正在加载扫描文件...</div>
            <div v-else-if="!scannerFiles.length" class="side-empty side-empty-compact">暂无可展示的扫描文件</div>
            <div v-else class="scanner-wrap">
              <div class="scanner-row">
                <button
                  v-for="item in scannerDisplayFiles"
                  :key="`scan-${item.file_path}-${item.mtime || 'guide'}`"
                  class="latest-card scanner-card"
                  type="button"
                  @click="openScannerFile(item)"
                  @mouseenter="handleScannerCardEnter(item)"
                  @mouseleave="handleScannerCardLeave(item)"
                  @focus="handleScannerCardEnter(item)"
                  @blur="handleScannerCardLeave(item)">

                  <div class="latest-thumb-box scanner-thumb-box">
                    <img
                      v-if="scannerThumbMap[item.file_path] || item.preview_src"
                      :src="scannerThumbMap[item.file_path] || item.preview_src"
                      :alt="item.name"
                      class="latest-thumb">
                    <div v-else class="latest-thumb-fallback">缩略图加载中</div>
                  </div>

                  <div class="latest-meta scanner-meta">
                    <div class="latest-desc">{{ item.guide_text || formatLatestModifiedTime(item.uploaded_at || item.mtime) }}</div>
                  </div>
                
                </button>
              </div>
            </div>

            <transition name="scanner-guide-preview-fade">
              <div
                v-if="hoveredScannerGuide"
                class="scanner-guide-preview"
                aria-hidden="true"
              >
                <img
                  :src="scanGuideImage"
                  alt="扫描文件夹引导大图"
                  class="scanner-guide-preview-image"
                >
              </div>
            </transition>
          </div>

          <div class="side-placeholder">
            <div class="side-header">
              <div class="side-title">最新上传</div>
              <div class="side-subtitle">按文件上传时间排序的文档</div>
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
                    <span
                      v-if="item.has_contract_binding"
                      class="latest-contract-badge"
                      aria-label="已绑定合同"
                      title="已绑定合同"
                      @click.stop="openBoundContract(item)"
                    />
                    <img
                      v-if="latestThumbMap[item.file_path]"
                      :src="latestThumbMap[item.file_path]"
                      :alt="item.name"
                      class="latest-thumb"
                    >
                    <div v-else class="latest-thumb-fallback">缩略图加载中</div>
                  </div>
                  <div class="latest-meta">
                    <div class="latest-name" :title="item.name">
                      <span class="latest-file-icon" :class="getLatestFileTypeClass(item)" aria-hidden="true" />
                      <span>{{ item.name }}</span>
                    </div>
                    <div class="latest-desc">{{ item.modified_by || '-' }} · {{ formatLatestModifiedTime(item.uploaded_at || item.mtime) }}</div>
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
          <div class="latest-preview-title-wrap">
            <span class="latest-preview-title" :title="activePreviewName">{{ activePreviewName }}</span>
            <span class="latest-preview-breadcrumb" :title="activePreviewBreadcrumb">目录：{{ activePreviewBreadcrumb }}</span>
          </div>
        </div>
      </template>

      <div class="latest-preview-body">
        <div v-if="previewLoading" class="latest-preview-loading">
          <span class="latest-preview-spinner" aria-hidden="true" />
          <span>正在加载预览...</span>
        </div>
        <iframe
          v-else-if="activePreviewUrl"
          :src="activePreviewUrl"
          class="latest-preview-frame"
          title="文件预览"
        />
        <div v-else class="latest-preview-empty">暂无可预览内容</div>
      </div>
    </el-dialog>

    <ContractItem
      ref="contractItemRef"
      :departments="contractEditorDepartments"
      :options="contractEditorOptions"
      v-model:aiParsing="contractItemAiParsing"
      :show-file-actions="false"
      @saved="handleHomeContractSaved"
    />
  </div>
</template>

<script setup>

import { computed, ref, onMounted, onBeforeUnmount, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import http from '../api/http'
import ContractItem from '../components/ContractItem.vue'
import scanGuideImage from '../assets/scan.jpg'
import VChart from 'vue-echarts'
import * as echarts from 'echarts/core'
import { PieChart, BarChart } from 'echarts/charts'
import { TitleComponent, TooltipComponent, LegendComponent, GridComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([PieChart, BarChart, TitleComponent, TooltipComponent, LegendComponent, GridComponent, CanvasRenderer])

// 注册全局组件
const vChart = VChart
const router = useRouter()

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
const scannerLoading = ref(false)
const scannerFiles = ref([])
const scannerThumbMap = ref({})
const hoveredScannerGuide = ref(false)
const previewVisible = ref(false)
const previewLoading = ref(false)
const activePreviewUrl = ref('')
const activePreviewName = ref('')
const activePreviewPath = ref('')
const previewRequestId = ref(0)
const contractItemRef = ref(null)
const contractItemAiParsing = ref(false)
const currentUserPermission = ref('view')
const currentUserRole = ref('admin')
const contractEditorDepartments = ref([])
const contractEditorOptions = ref({
  contract_form: [],
  contract_determination_method: [],
  contract_type: [],
  purchase_type: [],
  stamp_tax_rate_by_contract_type: {},
  pricing_method: [],
  is_archived: [],
  project: [],
})
const contractEditorReady = ref(false)
const contractEditorLoading = ref(false)

const showFullLoading = computed(() => backendLoading.value && !hasReadyData.value)
const scannerDisplayFiles = computed(() => {
  return [
    {
      file_path: '__scan_guide__',
      name: '扫描文件夹引导',
      preview_src: scanGuideImage,
      guide_text: '点击进入扫描页',
      isGuideCard: true,
    },
    ...scannerFiles.value,
  ]
})

const isViewPermissionUser = computed(() => {
  const role = String(currentUserRole.value || '').trim()
  if (['super_admin', 'synology_super_admin'].includes(role)) {
    return false
  }
  return String(currentUserPermission.value || '').trim() === 'view'
})

const isSuperAdminUser = computed(() => {
  const role = String(currentUserRole.value || '').trim()
  return ['super_admin', 'synology_super_admin'].includes(role)
})

const isArchivedValue = (value) => {
  const text = String(value ?? '').trim().toLowerCase()
  return ['已归档', '是', 'yes', 'true', '1', 'y'].includes(text)
}

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

const clearThumbMap = () => {
  latestThumbMap.value = {}
}

const clearScannerThumbMap = () => {
  scannerThumbMap.value = {}
}

const getApiAssetBase = () => (import.meta.env.PROD ? '/docs/api' : '/api')

const buildThumbUrl = (item, source = '') => {
  const thumbKey = String(item?.thumbnail_key || '').trim()
  if (thumbKey) {
    const params = new URLSearchParams()
    params.set('key', thumbKey)
    if (source) {
      params.set('source', source)
    }
    return `${getApiAssetBase()}/folders/file-thumbnail?${params.toString()}`
  }

  const path = String(item?.file_path || '').trim()
  if (!path) {
    return ''
  }

  const params = new URLSearchParams()
  params.set('path', path)
  params.set('mtime', String(item?.mtime ?? 0))
  if (source) {
    params.set('source', source)
  }

  const token = (localStorage.getItem('token') || '').trim()
  if (token) {
    params.set('token', token)
  }

  return `${getApiAssetBase()}/folders/file-thumbnail?${params.toString()}`
}

const loadLatestThumbnails = (rows) => {
  const loaded = {}
  rows.forEach((item) => {
    loaded[item.file_path] = buildThumbUrl(item)
  })
  latestThumbMap.value = loaded
}

const loadScannerThumbnails = (rows) => {
  const loaded = {}
  rows.forEach((item) => {
    loaded[item.file_path] = buildThumbUrl(item, 'scan')
  })
  scannerThumbMap.value = loaded
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

const parseDateFromUnknown = (value) => {
  if (value instanceof Date) {
    return Number.isFinite(value.getTime()) ? value : null
  }

  if (typeof value === 'number' && Number.isFinite(value)) {
    const ms = value < 1e12 ? value * 1000 : value
    const date = new Date(ms)
    return Number.isFinite(date.getTime()) ? date : null
  }

  if (typeof value !== 'string') {
    return null
  }

  const text = value.trim()
  if (!text) {
    return null
  }

  if (/^\d+$/.test(text)) {
    const numeric = Number(text)
    if (Number.isFinite(numeric)) {
      if (numeric <= 0) {
        return null
      }
      const ms = numeric < 1e12 ? numeric * 1000 : numeric
      const date = new Date(ms)
      return Number.isFinite(date.getTime()) ? date : null
    }
  }

  const isoLike = text.includes(' ') ? text.replace(' ', 'T') : text
  let date = new Date(isoLike)
  if (Number.isFinite(date.getTime())) {
    return date
  }

  date = new Date(text.replace(/-/g, '/'))
  return Number.isFinite(date.getTime()) ? date : null
}

const formatLatestModifiedTime = (value) => {
  const date = parseDateFromUnknown(value)
  if (!date) {
    return '-'
  }

  const now = new Date()
  const diffMs = Math.max(0, now.getTime() - date.getTime())
  const oneHourMs = 60 * 60 * 1000
  const oneMinuteMs = 60 * 1000

  const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const yesterdayStart = new Date(todayStart)
  yesterdayStart.setDate(yesterdayStart.getDate() - 1)

  if (date >= todayStart) {
    if (diffMs < oneHourMs) {
      const minutes = Math.max(1, Math.floor(diffMs / oneMinuteMs))
      return `${minutes}分钟前`
    }
    const hours = Math.max(1, Math.floor(diffMs / oneHourMs))
    return `${hours}小时前`
  }

  if (date >= yesterdayStart && date < todayStart) {
    return `昨天${date.getHours()}点`
  }

  if (date.getFullYear() === now.getFullYear()) {
    return `${date.getMonth() + 1}月${date.getDate()}日`
  }

  if (date.getFullYear() === now.getFullYear() - 1) {
    return `去年${date.getMonth() + 1}月`
  }

  return `${String(date.getFullYear()).slice(-2)}年${date.getMonth() + 1}月`
}

const getFileExtension = (nameOrPath) => {
  const text = String(nameOrPath || '').trim()
  if (!text) {
    return ''
  }

  const fileName = text.split(/[\\/]/).pop() || text
  const dotIndex = fileName.lastIndexOf('.')
  if (dotIndex < 0 || dotIndex === fileName.length - 1) {
    return ''
  }
  return fileName.slice(dotIndex + 1).toLowerCase()
}

const getLatestFileTypeClass = (item) => {
  const ext = getFileExtension(item?.name || item?.file_path)
  if (ext === 'doc' || ext === 'docx') {
    return 'latest-file-icon-doc'
  }
  if (ext === 'xls' || ext === 'xlsx') {
    return 'latest-file-icon-xls'
  }
  if (ext === 'pdf') {
    return 'latest-file-icon-pdf'
  }
  if (ext === 'txt') {
    return 'latest-file-icon-txt'
  }
  if (ext === 'md') {
    return 'latest-file-icon-md'
  }
  return 'latest-file-icon-file'
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

const normalizePath = (value) => String(value || '').replace(/\\/g, '/').replace(/^\/+|\/+$/g, '')

const getParentPath = (value) => {
  const path = normalizePath(value)
  if (!path) {
    return ''
  }
  const idx = path.lastIndexOf('/')
  return idx >= 0 ? path.slice(0, idx) : ''
}

const activePreviewBreadcrumb = computed(() => {
  const parentPath = getParentPath(activePreviewPath.value)
  return parentPath ? `/${parentPath}` : '/'
})

const loadCurrentUserPermission = async () => {
  try {
    const { data } = await http.get('/settings/users/current-permission')
    currentUserPermission.value = String(data?.permission || 'view').trim() || 'view'
    currentUserRole.value = String(data?.role || 'admin').trim() || 'admin'
  } catch (_error) {
    currentUserPermission.value = 'view'
    currentUserRole.value = 'admin'
  }
}

const ensureContractEditorResources = async () => {
  if (contractEditorReady.value || contractEditorLoading.value) {
    return
  }

  contractEditorLoading.value = true
  try {
    const [{ data: departments }, { data: options }] = await Promise.all([
      http.get('/settings/departments'),
      http.get('/options/contract-fields'),
    ])

    contractEditorDepartments.value = (Array.isArray(departments) ? departments : []).map((item) => item.name)
    contractEditorOptions.value = {
      contract_form: options?.contract_form || [],
      contract_determination_method: options?.contract_determination_method || [],
      contract_type: options?.contract_type || [],
      purchase_type: options?.purchase_type || [],
      stamp_tax_rate_by_contract_type: options?.stamp_tax_rate_by_contract_type || {},
      pricing_method: options?.pricing_method || [],
      is_archived: options?.is_archived || [],
      project: options?.project || [],
    }
    contractEditorReady.value = true
  } catch (_error) {
    ElMessage.warning('加载合同编辑配置失败')
  } finally {
    contractEditorLoading.value = false
  }
}

const openBoundContract = async (item) => {
  const directContractId = Number(item?.contract_id || item?.matched_contract_id || 0)
  const targetPath = normalizePath(item?.file_path)

  if (directContractId > 0) {
    try {
      await ensureContractEditorResources()
      const readOnly = isViewPermissionUser.value || (isArchivedValue(item?.is_archived) && !isSuperAdminUser.value)
      await contractItemRef.value?.openEdit({ id: directContractId }, { readOnly })
      return
    } catch (_error) {
      ElMessage.error('打开合同失败')
      return
    }
  }

  if (!targetPath) {
    ElMessage.warning('当前文件路径无效')
    return
  }

  try {
    const { data } = await http.get('/contracts', {
      params: {
        keyword: targetPath,
        has_file: true,
      },
    })

    const rows = Array.isArray(data) ? data : []
    const matched = rows.find((row) => normalizePath(row?.file_path) === targetPath) || rows[0]
    if (!matched?.id) {
      ElMessage.warning('未找到对应合同')
      return
    }

    await ensureContractEditorResources()
    const readOnly = isViewPermissionUser.value || (isArchivedValue(matched?.is_archived) && !isSuperAdminUser.value)
    await contractItemRef.value?.openEdit({ id: matched.id }, { readOnly })
  } catch (_error) {
    ElMessage.error('打开合同失败')
  }
}

const loadLatestFiles = async () => {
  latestLoading.value = true
  try {
    const { data } = await http.get('/folders/latest-uploads', {
      params: { limit: 8 },
    })
    const files = Array.isArray(data?.files) ? data.files : []
    latestFiles.value = files
    loadLatestThumbnails(files)
  } catch (_error) {
    const errorMessage = resolveErrorMessage(_error, '最新上传加载失败')
    if (shouldRedirectToLogin(_error?.response?.status, errorMessage)) {
      ElMessage.error('登录凭据已过期，请重新登录')
      redirectToLogin()
      return
    }

    latestFiles.value = []
    clearThumbMap()
    ElMessage.error(`最新上传加载失败：${errorMessage}`)
  } finally {
    latestLoading.value = false
  }
}

const loadScannerFiles = async () => {
  scannerLoading.value = true
  try {
    const { data } = await http.get('/folders/scan-files', {
      params: { limit: 10 },
    })
    const files = Array.isArray(data?.files) ? data.files : []
    scannerFiles.value = files
    loadScannerThumbnails(files)
  } catch (_error) {
    const errorMessage = resolveErrorMessage(_error, '扫描文件加载失败')
    if (shouldRedirectToLogin(_error?.response?.status, errorMessage)) {
      ElMessage.error('登录凭据已过期，请重新登录')
      redirectToLogin()
      return
    }

    scannerFiles.value = []
    clearScannerThumbMap()
    ElMessage.error(`扫描文件加载失败：${errorMessage}`)
  } finally {
    scannerLoading.value = false
  }
}

const openScannerFile = async (item) => {
  if (item?.isGuideCard) {
    await router.push({ path: '/contracts/scan' })
    return
  }

  const targetFilePath = normalizePath(item?.file_path)
  if (!targetFilePath) {
    ElMessage.warning('当前扫描文件路径无效')
    return
  }

  await router.push({
    path: '/contracts/scan',
    query: { file: targetFilePath },
  })
}

const handleScannerCardEnter = (item) => {
  hoveredScannerGuide.value = !!item?.isGuideCard
}

const handleScannerCardLeave = (item) => {
  if (item?.isGuideCard) {
    hoveredScannerGuide.value = false
  }
}

const releasePreviewUrl = () => {
  if (activePreviewUrl.value) {
    URL.revokeObjectURL(activePreviewUrl.value)
  }
  activePreviewUrl.value = ''
}

const openLatestPreview = async (item) => {
  const requestId = Date.now()
  previewRequestId.value = requestId

  activePreviewName.value = item.name || '文件预览'
  activePreviewPath.value = item.file_path || ''
  previewVisible.value = true
  previewLoading.value = true

  try {
    releasePreviewUrl()
    const { data } = await http.get('/folders/file-preview', {
      params: { path: item.file_path },
      responseType: 'blob',
    })
    if (previewRequestId.value !== requestId) {
      return
    }
    activePreviewUrl.value = URL.createObjectURL(data)
  } catch (_error) {
    if (previewRequestId.value === requestId) {
      ElMessage.error('文件预览失败')
    }
  } finally {
    if (previewRequestId.value === requestId) {
      previewLoading.value = false
    }
  }
}

watch(previewVisible, (visible) => {
  if (!visible) {
    previewRequestId.value = 0
    previewLoading.value = false
    activePreviewPath.value = ''
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

const handleHomeContractSaved = async () => {
  await Promise.all([
    loadLatestFiles(),
    loadScannerFiles(),
  ])
}

onMounted(() => {
  const cached = readDashboardCache()
  if (cached) {
    applyDashboardData(cached.stat, cached.charts)
    hasReadyData.value = true
  }

  loadCurrentUserPermission()
  loadStatistics()
  loadLatestFiles()
  loadScannerFiles()
})

onBeforeUnmount(() => {
  clearThumbMap()
  clearScannerThumbMap()
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
  display: flex;
  flex-direction: column;
  gap: 18px;
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

.side-placeholder-compact {
  min-height: auto;
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

.side-loading-compact,
.side-empty-compact {
  min-height: 120px;
}

.latest-wrap {
  padding-bottom: 4px;
}

.scanner-wrap {
  padding-bottom: 4px;
}

.latest-grid {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  gap: clamp(10px, 0.9vw, 14px);
}

.scanner-row {
  display: flex;
  flex-wrap: nowrap;
  gap: clamp(10px, 0.9vw, 14px);
  overflow-x: auto;
  overflow-y: hidden;
  padding-top: 8px;
  padding-bottom: 6px;
  margin-top: -8px;
  scrollbar-width: thin;
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

.scanner-card {
  flex: 0 0 148px;
}

.latest-thumb-box {
  width: min(100%, 168px);
  max-width: 168px;
  max-height: 232px;
  aspect-ratio: 21 / 29;
  position: relative;
  border-radius: 12px;
  overflow: hidden;
  background: rgba(231, 238, 250, 0.8);
  border: 1px solid rgba(72, 112, 186, 0.18);
  transition: border-color 0.24s ease, box-shadow 0.24s ease, transform 0.24s ease;
}

.scanner-thumb-box {
  width: 148px;
  max-width: 148px;
  max-height: 206px;
}

.latest-contract-badge {
  position: absolute;
  top: 0;
  right: 0;
  z-index: 2;
  width: 26%;
  aspect-ratio: 1 / 1;
  background: linear-gradient(145deg, rgba(47, 114, 230, 0.68), rgba(39, 95, 203, 0.68));
  clip-path: polygon(100% 0, 0 0, 100% 100%);
}

.latest-contract-badge::before {
  content: '';
  position: absolute;
  top: 36%;
  left: 70%;
  width: 46%;
  height: 46%;
  transform: translate(-50%, -50%);
  background-image: url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none"><rect x="3.5" y="4.5" width="17" height="15" rx="2" stroke="%23fff" stroke-width="1.7"/><path d="M3.5 9h17M3.5 13.5h17M8.5 4.5v15" stroke="%23fff" stroke-width="1.7" stroke-linecap="round"/></svg>');
  background-size: contain;
  background-repeat: no-repeat;
  background-position: center;
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

.scanner-meta {
  width: 148px;
}

.scanner-guide-preview-fade-enter-active,
.scanner-guide-preview-fade-leave-active {
  transition: opacity 0.18s ease;
}

.scanner-guide-preview-fade-enter-from,
.scanner-guide-preview-fade-leave-to {
  opacity: 0;
}

.scanner-guide-preview {
  position: fixed;
  inset: 4vh 5vw;
  z-index: 60;
  display: flex;
  align-items: center;
  justify-content: center;
  pointer-events: none;
}

.scanner-guide-preview::before {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: 28px;
  background: rgba(15, 23, 42, 0.18);
  backdrop-filter: blur(6px);
  box-shadow: 0 30px 80px rgba(15, 23, 42, 0.22);
}

.scanner-guide-preview-image {
  position: relative;
  display: block;
  max-width: min(92vw, 1100px);
  max-height: 88vh;
  width: auto;
  height: auto;
  object-fit: contain;
  border-radius: 22px;
  box-shadow: 0 30px 80px rgba(15, 23, 42, 0.28);
}

.latest-name {
  font-size: clamp(11px, 0.78vw, 13px);
  font-weight: 600;
  color: #2e4f88;
  display: block;
  white-space: normal;
  word-break: break-all;
  overflow-wrap: anywhere;
  line-height: 1.35;
}

.scanner-name {
  font-size: 12px;
}

.latest-file-icon {
  width: 16px;
  height: 16px;
  display: inline-block;
  margin-right: 6px;
  vertical-align: -2px;
  flex: 0 0 16px;
  background-repeat: no-repeat;
  background-size: contain;
  background-position: center;
}

.latest-file-icon-file {
  background-image: url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><path d="M3 1h6l4 4v10H3z" fill="%23f6f8fc" stroke="%23c6d0e1"/><path d="M9 1v4h4" fill="%23e8eef8"/><path d="M5 8h6M5 10h6M5 12h4" stroke="%2398a9c3" stroke-width="1"/></svg>');
}

.latest-file-icon-doc {
  background-image: url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><path d="M3 1h6l4 4v10H3z" fill="%23eef4ff" stroke="%2392b2ea"/><path d="M9 1v4h4" fill="%23dce9ff"/><rect x="4" y="8" width="8" height="5" rx="1" fill="%232a63c7"/><path d="M5.3 11.8V9.2h1.1c.8 0 1.3.5 1.3 1.3 0 .8-.5 1.3-1.3 1.3zM9.9 9.2h1.6v.7h-.8v.3h.7v.7h-.7v.9h-.8z" fill="%23fff"/></svg>');
}

.latest-file-icon-xls {
  background-image: url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><path d="M3 1h6l4 4v10H3z" fill="%23ebf8f0" stroke="%238dc8a6"/><path d="M9 1v4h4" fill="%23dbf0e3"/><rect x="4" y="8" width="8" height="5" rx="1" fill="%232e8b57"/><path d="M5 9.2h1l.5.8.5-.8h1l-1 1.3 1 1.3h-1l-.5-.8-.5.8H5l1-1.3zm3.3 0h2.7v.7h-.9v1.9h-.9V9.9h-.9z" fill="%23fff"/></svg>');
}

.latest-file-icon-pdf {
  background-image: url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><path d="M3 1h6l4 4v10H3z" fill="%23fff1f0" stroke="%23df9c99"/><path d="M9 1v4h4" fill="%23ffe1df"/><rect x="4" y="8" width="8" height="5" rx="1" fill="%23c43d36"/><path d="M5 11.8V9.2h1.2c.6 0 1 .4 1 1s-.4 1-1 1h-.4v.6zm3.2 0V9.2h2.2v.7H9v.3h1.2v.7H9v.9zm3.1 0V9.2h.8v2.6z" fill="%23fff"/></svg>');
}

.latest-file-icon-txt {
  background-image: url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><path d="M3 1h6l4 4v10H3z" fill="%23f5f7fb" stroke="%23b9c5db"/><path d="M9 1v4h4" fill="%23e7edf8"/><path d="M5 8h6M5 10h6M5 12h5" stroke="%23687993" stroke-width="1"/></svg>');
}

.latest-file-icon-md {
  background-image: url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><path d="M3 1h6l4 4v10H3z" fill="%23f3f4f7" stroke="%23b3b8c5"/><path d="M9 1v4h4" fill="%23e5e8f0"/><rect x="4" y="8" width="8" height="5" rx="1" fill="%23666f86"/><path d="M5 11.8V9.2h.8l.7 1 .7-1H8v2.6h-.8v-1.2l-.7 1-.7-1v1.2zm4.3-2.6h.8v1.1l.8-.8h1.1l-1.2 1.1 1.2 1.2h-1.1l-.8-.8v.8h-.8z" fill="%23fff"/></svg>');
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

.latest-preview-title-wrap {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.latest-preview-title {
  font-size: 16px;
  font-weight: 600;
  color: #2d4f87;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.latest-preview-breadcrumb {
  min-width: 0;
  color: #6b7280;
  font-size: 12px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.latest-preview-body {
  height: calc(100vh - 96px);
}

.latest-preview-loading {
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  color: #5c73a0;
  font-size: 14px;
}

.latest-preview-spinner {
  width: 26px;
  height: 26px;
  border-radius: 50%;
  border: 3px solid rgba(92, 115, 160, 0.22);
  border-top-color: #4d6fa8;
  animation: latest-preview-spin 0.7s linear infinite;
}

@keyframes latest-preview-spin {
  to {
    transform: rotate(360deg);
  }
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
  width: 32px;
  height: 32px;
  min-width: 32px;
  min-height: 32px;
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
  font-size: 21px;
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


@media (max-width: 1600px) {
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
