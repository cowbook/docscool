<template>
  <div class="scan-page">
    <div class="scan-layout">
      <section class="scan-list-panel">
        <div class="scan-panel-header">
          <div>
            <div class="scan-panel-title">合同扫描</div>
            <div class="scan-panel-subtitle">扫描目录中的 PDF 首页缩略图</div>
          </div>
          <el-button @click="loadScanFiles" :loading="scanLoading">刷新</el-button>
        </div>

        <div v-if="scanLoading && !scanFiles.length" class="scan-panel-loading">正在加载扫描文件...</div>
        <div v-else-if="!scanFiles.length" class="scan-panel-empty">扫描目录中暂无 PDF 文件</div>
        <div v-else class="scan-grid">
          <button
            v-for="item in scanFiles"
            :key="`${item.file_path}-${item.mtime}`"
            type="button"
            class="scan-card"
            :class="{ 'is-active': activeFilePath === item.file_path }"
            @click="selectScanFile(item)"
          >
            <div class="scan-thumb-box">
              <img
                v-if="scanThumbMap[item.file_path]"
                :src="scanThumbMap[item.file_path]"
                :alt="item.name"
                class="scan-thumb"
              >
              <div v-else class="scan-thumb-fallback">缩略图加载中</div>
            </div>
            <div class="scan-card-meta">
              <div class="scan-card-name" :title="item.name">{{ item.name }}</div>
              <div class="scan-card-desc">{{ formatLatestModifiedTime(item.uploaded_at || item.mtime) }}</div>
            </div>
          </button>
        </div>
      </section>

      <aside class="scan-preview-panel">
        <div class="scan-panel-header scan-preview-header">
          <div>
            <div class="scan-panel-title">文件预览</div>
            <div class="scan-panel-subtitle">先选择扫描文件，再导入为合同</div>
          </div>
          <el-button
            type="primary"
            :disabled="!activeScanFile || isViewPermissionUser || importingScan"
            :loading="importingScan"
            @click="openImportFolderDialog"
          >
            {{ importingScan ? '导入中...' : '导入合同' }}
          </el-button>
        </div>

        <div class="scan-preview-body">
          <div v-if="previewLoading" class="scan-preview-loading">正在加载预览...</div>
          <iframe
            v-else-if="activePreviewUrl"
            :src="activePreviewUrl"
            class="scan-preview-frame"
            title="扫描文件预览"
          />
          <div v-else class="scan-preview-empty">请选择左侧 PDF 文件</div>
        </div>
      </aside>
    </div>

    <el-dialog
      v-model="importFolderDialogVisible"
      title="选择导入目录"
      width="min(760px, 96vw)"
      :close-on-click-modal="false"
    >
      <div class="ai-folder-dialog-tip">请先选择导入到合同存储空间中的目标目录。</div>
      <div class="ai-folder-dialog-selected">当前选择：{{ importFolderSelectedPath || '未选择' }}</div>

      <div class="ai-folder-tree-wrap" v-loading="folderTreeLoading">
        <el-tree
          :key="folderTreeRenderKey"
          :data="folderTreeData"
          node-key="path"
          :props="folderTreeProps"
          lazy
          :load="loadFolderChildren"
          :expand-on-click-node="true"
          highlight-current
          @node-click="onFolderNodeClick"
        >
          <template #default="{ node, data }">
            <span class="ai-folder-tree-node" :title="normalizeFolderPath(data.path || '')">
              <span class="ai-folder-tree-icon" aria-hidden="true">{{ node.expanded ? '📂' : '📁' }}</span>
              <span class="ai-folder-tree-label">{{ data.name }}</span>
            </span>
          </template>
        </el-tree>
      </div>

      <template #footer>
        <el-button @click="importFolderDialogVisible = false">取消</el-button>
        <el-button type="primary" :disabled="!importFolderSelectedPath" @click="importCurrentScanFile">开始导入</el-button>
      </template>
    </el-dialog>

    <AiMatchDialog
      v-model="aiMatchDialogVisible"
      :candidates="aiMatchCandidates"
      :loading="aiMatchLoading"
      :processing="aiMatchProcessing"
      :file="null"
      :preview-url="aiPreviewUrl"
      @confirm-selection="proceedAiMatchSelection"
      @cancel="closeAiMatchDialog"
    />

    <ContractItem
      ref="contractItemRef"
      :departments="departments"
      :options="options"
      v-model:aiParsing="aiParsing"
      :show-file-actions="false"
      @saved="handleContractSaved"
    />
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import http from '../api/http'
import AiMatchDialog from '../components/AiMatchDialog.vue'
import ContractItem from '../components/ContractItem.vue'

const AI_NEW_CONTRACT_VALUE = '__new_contract__'
const appBasePrefix = import.meta.env.BASE_URL || '/'
const route = useRoute()

const scanLoading = ref(false)
const scanFiles = ref([])
const scanThumbMap = ref({})
const activeScanFile = ref(null)
const activeFilePath = ref('')
const previewLoading = ref(false)
const activePreviewUrl = ref('')
const previewRequestId = ref(0)
const importingScan = ref(false)
const importFolderDialogVisible = ref(false)
const folderTreeLoading = ref(false)
const folderTreeData = ref([])
const folderTreeRenderKey = ref(0)
const importFolderSelectedPath = ref('')
const importTargetFolderPath = ref('')
const contractItemRef = ref(null)
const aiParsing = ref(false)
const aiMatchDialogVisible = ref(false)
const aiMatchLoading = ref(false)
const aiMatchProcessing = ref(false)
const aiMatchCandidates = ref([])
const aiParsedFields = ref(null)
const aiUploadedFilePath = ref('')
const aiPreviewUrl = ref('')
const currentUserPermission = ref('view')
const currentUserRole = ref('admin')
const currentUserPermissionList = ref([])
const departments = ref([])
const options = reactive({
  contract_determination_method: [],
  contract_type: [],
  purchase_type: [],
  stamp_tax_rate_by_contract_type: {},
  pricing_method: [],
  is_archived: [],
  project: [],
})

const folderTreeProps = {
  label: 'name',
  children: 'children',
  isLeaf: () => false,
}

const SUPER_ROLE_SET = new Set(['super_admin', 'synology_super_admin'])

const getRequestedFilePath = () => normalizeFolderPath(route.query.file || '')

const isViewPermissionUser = computed(() => {
  if (SUPER_ROLE_SET.has(String(currentUserRole.value || '').trim())) {
    return false
  }
  return String(currentUserPermission.value || '').trim() === 'view'
})

const normalizeFolderPath = (value) => String(value || '').replace(/\\/g, '/').replace(/^\/+|\/+$/g, '')

const getApiAssetBase = () => (import.meta.env.PROD ? '/docs/api' : '/api')

const buildThumbUrl = (item) => {
  const thumbKey = String(item?.thumbnail_key || '').trim()
  if (thumbKey) {
    const params = new URLSearchParams()
    params.set('key', thumbKey)
    params.set('source', 'scan')
    return `${getApiAssetBase()}/folders/file-thumbnail?${params.toString()}`
  }

  const path = String(item?.file_path || '').trim()
  if (!path) {
    return ''
  }

  const params = new URLSearchParams()
  params.set('path', path)
  params.set('mtime', String(item?.mtime ?? 0))
  params.set('source', 'scan')

  const token = (localStorage.getItem('token') || '').trim()
  if (token) {
    params.set('token', token)
  }

  return `${getApiAssetBase()}/folders/file-thumbnail?${params.toString()}`
}

const loadScanThumbnails = (rows) => {
  const loaded = {}
  rows.forEach((item) => {
    loaded[item.file_path] = buildThumbUrl(item)
  })
  scanThumbMap.value = loaded
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
  const expiredHints = ['会话已超时', '会话被中断', '会话无效', '重新登录', '凭据', 'expired', 'unauthorized', 'invalid token']
  return expiredHints.some((hint) => normalized.includes(hint))
}

const normalizeTextList = (value) => {
  if (Array.isArray(value)) {
    return value.map((item) => String(item || '').trim()).filter(Boolean)
  }
  return String(value || '').split(',').map((item) => item.trim()).filter(Boolean)
}

const normalizeCurrentPermissionList = (value) => {
  if (!Array.isArray(value)) {
    return []
  }
  return value.map((item) => ({
    permission: String(item?.permission || '').trim(),
    departments: normalizeTextList(item?.departments),
  }))
}

const releasePreviewUrl = () => {
  if (activePreviewUrl.value) {
    URL.revokeObjectURL(activePreviewUrl.value)
  }
  activePreviewUrl.value = ''
}

const loadCurrentUserPermission = async () => {
  try {
    const { data } = await http.get('/settings/users/current-permission')
    currentUserRole.value = String(data?.role || 'admin').trim() || 'admin'
    currentUserPermission.value = String(data?.permission || 'view').trim() || 'view'
    currentUserPermissionList.value = normalizeCurrentPermissionList(data?.permission_list)
  } catch (_error) {
    currentUserRole.value = 'admin'
    currentUserPermission.value = 'view'
    currentUserPermissionList.value = []
  }
}

const loadDepartments = async () => {
  const { data } = await http.get('/settings/departments')
  departments.value = (Array.isArray(data) ? data : []).map((item) => item.name)
}

const loadFieldOptions = async () => {
  const { data } = await http.get('/options/contract-fields')
  options.contract_determination_method = data?.contract_determination_method || []
  options.contract_type = data?.contract_type || []
  options.purchase_type = data?.purchase_type || []
  options.stamp_tax_rate_by_contract_type = data?.stamp_tax_rate_by_contract_type || {}
  options.pricing_method = data?.pricing_method || []
  options.is_archived = data?.is_archived || []
  options.project = data?.project || []
}

const loadScanFiles = async () => {
  scanLoading.value = true
  try {
    const { data } = await http.get('/folders/scan-files')
    const files = Array.isArray(data?.files) ? data.files : []
    scanFiles.value = files
    loadScanThumbnails(files)
    if (!files.length) {
      activeScanFile.value = null
      activeFilePath.value = ''
      releasePreviewUrl()
      previewLoading.value = false
      return
    }

    const requestedFilePath = getRequestedFilePath()
    const requested = requestedFilePath
      ? files.find((item) => normalizeFolderPath(item.file_path) === requestedFilePath)
      : null
    const stillActive = files.find((item) => item.file_path === activeFilePath.value)
    await selectScanFile(requested || stillActive || files[0])
  } catch (error) {
    const errorMessage = resolveErrorMessage(error, '扫描文件加载失败')
    if (shouldRedirectToLogin(error?.response?.status, errorMessage)) {
      ElMessage.error('登录凭据已过期，请重新登录')
      redirectToLogin()
      return
    }
    scanFiles.value = []
    scanThumbMap.value = {}
    activeScanFile.value = null
    activeFilePath.value = ''
    releasePreviewUrl()
    ElMessage.error(`扫描文件加载失败：${errorMessage}`)
  } finally {
    scanLoading.value = false
  }
}

const applyRouteSelectedFile = async () => {
  const requestedFilePath = getRequestedFilePath()
  if (!requestedFilePath || !scanFiles.value.length) {
    return
  }

  if (normalizeFolderPath(activeFilePath.value) === requestedFilePath) {
    return
  }

  const matched = scanFiles.value.find((item) => normalizeFolderPath(item.file_path) === requestedFilePath)
  if (matched) {
    await selectScanFile(matched)
  }
}

const selectScanFile = async (item) => {
  if (!item?.file_path) {
    return
  }

  activeScanFile.value = item
  activeFilePath.value = item.file_path
  previewLoading.value = true
  const requestId = Date.now()
  previewRequestId.value = requestId

  try {
    releasePreviewUrl()
    const { data } = await http.get('/folders/file-preview', {
      params: {
        path: item.file_path,
        source: 'scan',
      },
      responseType: 'blob',
    })
    if (previewRequestId.value !== requestId) {
      return
    }
    activePreviewUrl.value = URL.createObjectURL(data)
  } catch (error) {
    if (previewRequestId.value === requestId) {
      ElMessage.error(resolveErrorMessage(error, '文件预览失败'))
    }
  } finally {
    if (previewRequestId.value === requestId) {
      previewLoading.value = false
    }
  }
}

const dedupeFolderNodes = (nodes) => {
  const list = Array.isArray(nodes) ? nodes : []
  const seen = new Set()
  const result = []
  list.forEach((item) => {
    const name = String(item?.name || '').trim()
    const path = normalizeFolderPath(item?.path || '')
    if (!name && !path) {
      return
    }
    const key = `${path}::${name}`
    if (seen.has(key)) {
      return
    }
    seen.add(key)
    result.push({ ...item, name, path })
  })
  return result
}

const loadFolderChildren = async (node, resolve) => {
  if (node?.level === 0) {
    folderTreeLoading.value = true
  }
  const parentPath = node?.level === 0 ? '' : normalizeFolderPath(node?.data?.path || '')
  try {
    const { data } = await http.get('/folders/children', {
      params: { parent_path: parentPath },
    })
    resolve(dedupeFolderNodes(data?.children))
  } catch (error) {
    ElMessage.error(resolveErrorMessage(error, '读取子目录失败'))
    resolve([])
  } finally {
    if (node?.level === 0) {
      folderTreeLoading.value = false
    }
  }
}

const onFolderNodeClick = (node) => {
  importFolderSelectedPath.value = normalizeFolderPath(node?.path || '')
}

const openImportFolderDialog = () => {
  if (!activeScanFile.value?.file_path) {
    ElMessage.warning('请先选择扫描文件')
    return
  }
  importFolderSelectedPath.value = normalizeFolderPath(importTargetFolderPath.value)
  folderTreeData.value = []
  folderTreeRenderKey.value += 1
  folderTreeLoading.value = false
  importFolderDialogVisible.value = true
}

const resetAiMatchState = () => {
  aiMatchCandidates.value = []
  aiParsedFields.value = null
  aiUploadedFilePath.value = ''
  aiPreviewUrl.value = ''
}

const closeAiMatchDialog = () => {
  aiMatchDialogVisible.value = false
  resetAiMatchState()
}

const hasDepartmentEditPermissionForContract = (row) => {
  const role = String(currentUserRole.value || '').trim()
  if (SUPER_ROLE_SET.has(role)) {
    return true
  }
  if (String(currentUserPermission.value || '').trim() === 'view') {
    return false
  }
  const department = String(row?.handling_department || row?.department || '').trim()
  return currentUserPermissionList.value.some((item) => {
    if (String(item?.permission || '').trim() !== 'edit') {
      return false
    }
    const departments = normalizeTextList(item?.departments)
    if (departments.includes('全部')) {
      return true
    }
    if (!department) {
      return false
    }
    return departments.includes(department)
  })
}

const openEditWithSupplementalFields = async (row, fields) => {
  await contractItemRef.value?.openEditWithSupplementalFields(row, fields, {
    readOnly: !hasDepartmentEditPermissionForContract(row),
  })
}

const proceedAiMatchSelection = async (selectedValue) => {
  if (aiMatchLoading.value) {
    ElMessage.info('数据加载中，请稍候')
    return
  }

  const uploadedFilePath = normalizeFolderPath(aiUploadedFilePath.value)
  const parsedFields = aiParsedFields.value || {}
  if (!uploadedFilePath) {
    ElMessage.error('导入后的文件路径丢失，请重试')
    closeAiMatchDialog()
    return
  }

  aiMatchProcessing.value = true
  try {
    if (selectedValue === AI_NEW_CONTRACT_VALUE) {
      aiMatchDialogVisible.value = false
      await contractItemRef.value?.openCreateWithFilePath(uploadedFilePath, parsedFields)
      resetAiMatchState()
      return
    }

    const selectedId = Number(selectedValue)
    const matchedRow = aiMatchCandidates.value.find((item) => item.id === selectedId)
    if (!matchedRow) {
      ElMessage.warning('请选择要关联的已有合同，或选择“这是新合同”')
      return
    }

    await http.put(`/contracts/${selectedId}`, {
      file_path: uploadedFilePath,
    })
    const mergedRow = {
      ...matchedRow,
      file_path: uploadedFilePath,
    }

    aiMatchDialogVisible.value = false
    await openEditWithSupplementalFields(mergedRow, parsedFields)
    ElMessage.success('已关联到已有合同，请确认补充字段后保存')
    resetAiMatchState()
  } finally {
    aiMatchProcessing.value = false
  }
}

const importCurrentScanFile = async () => {
  const selected = activeScanFile.value
  const targetFolderPath = normalizeFolderPath(importFolderSelectedPath.value)
  if (!selected?.file_path) {
    ElMessage.warning('请先选择扫描文件')
    return
  }
  if (!targetFolderPath) {
    ElMessage.warning('请选择导入目录')
    return
  }

  importingScan.value = true
  aiParsing.value = true
  aiMatchDialogVisible.value = true
  aiMatchLoading.value = true
  importTargetFolderPath.value = targetFolderPath
  importFolderDialogVisible.value = false
  resetAiMatchState()

  try {
    const importResponse = await http.post('/folders/scan-import', {
      file_path: selected.file_path,
      target_folder_path: targetFolderPath,
    }, {
      timeout: 300000,
    })

    const importedPath = normalizeFolderPath(importResponse?.data?.file_path || '')
    if (!importedPath) {
      throw new Error('导入成功但未返回文件路径')
    }
    aiUploadedFilePath.value = importedPath
    aiPreviewUrl.value = activePreviewUrl.value

    const { data } = await http.post('/contracts/ai-parse', {
      file_path: importedPath,
    }, {
      timeout: 300000,
    })

    const parsedFullbody = data?.fullbody || ''
    aiParsedFields.value = {
      ...(data?.fields || {}),
      fullbody: parsedFullbody,
    }
    aiMatchCandidates.value = Array.isArray(data?.match_candidates) ? data.match_candidates : []
    aiMatchLoading.value = false
    ElMessage.success('AI解析完成，请先确认是否匹配到已有合同')
  } catch (error) {
    aiMatchLoading.value = false
    aiMatchDialogVisible.value = false
    if (error?.code === 'ECONNABORTED') {
      ElMessage.error('AI解析超时，请稍后重试')
      return
    }
    const baseMessage = resolveErrorMessage(error, '导入或AI解析失败')
    const previewLines = error?.response?.data?.ocr_preview_lines
    if (Array.isArray(previewLines) && previewLines.length > 0) {
      const preview = previewLines.slice(0, 3).join(' / ')
      ElMessage.error(`${baseMessage}；识别预览：${preview}`)
    } else {
      ElMessage.error(baseMessage)
    }
  } finally {
    aiParsing.value = false
    importingScan.value = false
  }
}

const handleContractSaved = async () => {
  await Promise.all([
    loadDepartments(),
    loadFieldOptions(),
    loadScanFiles(),
  ])
}

watch(aiMatchDialogVisible, (visible) => {
  if (!visible) {
    aiMatchLoading.value = false
    aiMatchProcessing.value = false
  }
})

watch(activePreviewUrl, (nextValue, previousValue) => {
  if (previousValue && previousValue !== nextValue && previousValue.startsWith('blob:')) {
    URL.revokeObjectURL(previousValue)
  }
})

watch(() => route.query.file, () => {
  applyRouteSelectedFile()
})

onMounted(async () => {
  await Promise.all([
    loadCurrentUserPermission(),
    loadDepartments(),
    loadFieldOptions(),
    loadScanFiles(),
  ])
})

onBeforeUnmount(() => {
  previewRequestId.value = 0
  releasePreviewUrl()
})
</script>

<style scoped>
.scan-page {
  min-height: calc(100vh - 112px);
  display: flex;
  flex-direction: column;
}

.scan-layout {
  display: grid;
  grid-template-columns: minmax(0, 3fr) minmax(360px, 2fr);
  gap: 18px;
  align-items: stretch;
  flex: 1;
  min-height: 0;
}

.scan-list-panel,
.scan-preview-panel {
  display: flex;
  flex-direction: column;
  background: rgba(255, 255, 255, 0.82);
  border: 1px solid rgba(210, 223, 243, 0.8);
  border-radius: 24px;
  box-shadow: 0 18px 40px rgba(44, 79, 139, 0.12);
  backdrop-filter: blur(14px);
  padding: 18px;
  min-height: 0;
}

.scan-panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}

.scan-preview-header {
  padding-bottom: 8px;
  border-bottom: 1px solid rgba(219, 229, 241, 0.9);
}

.scan-panel-title {
  font-size: 20px;
  font-weight: 700;
  color: #16345f;
}

.scan-panel-subtitle {
  margin-top: 4px;
  font-size: 13px;
  color: #6b7a90;
}

.scan-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 16px;
  align-content: start;
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding-right: 4px;
}

.scan-card {
  border: 1px solid rgba(211, 223, 245, 0.92);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(243, 247, 255, 0.98));
  border-radius: 18px;
  padding: 12px;
  text-align: left;
  cursor: pointer;
  transition: transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s ease;
}

.scan-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 14px 28px rgba(47, 84, 150, 0.15);
  border-color: rgba(120, 160, 231, 0.95);
}

.scan-card.is-active {
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.16), 0 16px 30px rgba(43, 89, 172, 0.18);
}

.scan-thumb-box {
  aspect-ratio: 210 / 290;
  border-radius: 14px;
  overflow: hidden;
  background: #edf3ff;
  border: 1px solid rgba(203, 216, 240, 0.92);
}

.scan-thumb {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.scan-thumb-fallback,
.scan-panel-loading,
.scan-panel-empty,
.scan-preview-loading,
.scan-preview-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  color: #70819b;
}

.scan-thumb-fallback {
  height: 100%;
  font-size: 13px;
}

.scan-panel-loading,
.scan-panel-empty,
.scan-preview-loading,
.scan-preview-empty {
  min-height: 280px;
  font-size: 14px;
}

.scan-card-meta {
  margin-top: 10px;
}

.scan-card-name {
  font-size: 14px;
  font-weight: 600;
  color: #1f3355;
  line-height: 1.45;
  overflow: hidden;
  display: -webkit-box;
  line-clamp: 2;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.scan-card-desc {
  margin-top: 6px;
  font-size: 12px;
  color: #76849b;
}

.scan-preview-body {
  margin-top: 16px;
  flex: 1;
  min-height: 0;
  border-radius: 18px;
  overflow: hidden;
  background: #f4f7fc;
  border: 1px solid rgba(212, 223, 241, 0.92);
}

.scan-preview-frame {
  width: 100%;
  height: 100%;
  border: none;
  background: #fff;
}

.ai-folder-dialog-tip {
  margin-bottom: 10px;
  color: #5f6f86;
  font-size: 13px;
}

.ai-folder-dialog-selected {
  margin-bottom: 12px;
  color: #1f3556;
  font-weight: 600;
  word-break: break-all;
}

.ai-folder-tree-wrap {
  border: 1px solid #d8e1f0;
  border-radius: 12px;
  padding: 12px;
  background: #fbfdff;
  min-height: 360px;
  max-height: 56vh;
  overflow: auto;
}

.ai-folder-tree-node {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  max-width: 100%;
}

.ai-folder-tree-icon {
  width: 20px;
  text-align: center;
}

.ai-folder-tree-label {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

@media (max-width: 1100px) {
  .scan-layout {
    grid-template-columns: 1fr;
    flex: none;
  }

  .scan-list-panel,
  .scan-preview-panel {
    min-height: auto;
  }

  .scan-grid {
    max-height: none;
  }

  .scan-preview-body {
    height: 60vh;
    flex: none;
  }
}
</style>
