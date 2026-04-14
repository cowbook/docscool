<template>
  <div class="contract-page">
    <el-card>
      <template #header>
        <div class="card-header">
          <div class="card-title">所有合同</div>
          <div class="header-actions">
            <el-button :disabled="importingExcel" @click="downloadImportTemplate">导入模板下载</el-button>
            <el-button :loading="importingExcel" :disabled="aiParsing" @click="triggerExcelUpload">
              {{ importingExcel ? 'EXCEL导入中...' : 'EXCEL导入' }}
            </el-button>
            <el-button :loading="aiParsing" @click="triggerAiUpload">{{ aiParsing ? 'AI解析中...' : 'AI上传' }}</el-button>
            <el-button type="primary" :disabled="aiParsing" @click="openCreate">新建合同</el-button>
          </div>
        </div>
      </template>

      <input
        ref="excelUploadInput"
        type="file"
        accept=".xls,.xlsx,application/vnd.ms-excel,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        style="display: none"
        @change="handleExcelSelected"
      />

      <input
        ref="aiUploadInput"
        type="file"
        accept="application/pdf,.pdf"
        style="display: none"
        @change="handleAiPdfSelected"
      />

      <div class="toolbar">
        <el-select v-model="filters.handling_department" clearable placeholder="按承办部门筛选" style="width: 220px" @change="loadContracts">
          <el-option v-for="item in departments" :key="item" :label="item" :value="item" />
        </el-select>
        <el-select v-model="filters.approval_status" clearable placeholder="按审批状态筛选" style="width: 180px" @change="loadContracts">
          <el-option v-for="item in options.approval_status" :key="item" :label="item" :value="item" />
        </el-select>
        <el-input
          v-model="filters.keyword"
          clearable
          placeholder="搜索任意合同字段"
          style="width: 280px"
          @clear="loadContracts"
          @keyup.enter="loadContracts"
        />
        <el-button type="primary" @click="loadContracts">搜索</el-button>
        <el-button @click="loadContracts">刷新</el-button>
      </div>

      <el-table :data="pagedContracts" stripe size="small" class="contract-table">
         <el-table-column label="文件" min-width="220">
          <template #default="scope">
            <el-link class="file-cell"  @click.stop="openFilePreview(scope.row)" v-if="scope.row.file_path">

              <el-tooltip :content="scope.row.file_path" placement="top">
                <Icon
                  v-if="scope.row.file_path"
                  :icon="getFileIcon(scope.row.file_path)"
                  class="file-ok file-download"
                />
              </el-tooltip>


              <span class="file-name" :title="getFileName(scope.row.file_path)">
                {{ getFileName(scope.row.file_path) || '缺失' }}
              </span>
            </el-link>
            <div v-else  @click.stop="javascript:void(0);" >
                <el-icon class="file-miss"><CircleCloseFilled /></el-icon>
                <span class="no-file-name">未上传</span>
            
            </div>
          </template>
        </el-table-column>

        <el-table-column prop="contract_name" label="合同名称" :min-width="contractNameColumnWidth" show-overflow-tooltip>
          <template #default="scope">
            <button class="contract-name-link" type="button" @click.stop="openEdit(scope.row)">
              <span class="contract-name-cell">{{ scope.row.contract_name }}</span>
            </button>
          </template>
        </el-table-column>
        <el-table-column prop="contract_number" label="合同编号" min-width="140" />
        <el-table-column prop="contract_unit" label="合同单位" min-width="180" show-overflow-tooltip />
        <el-table-column prop="contract_amount_wan" label="合同金额(万元)" min-width="120" />
        <el-table-column prop="approval_status" label="审批状态" min-width="100" />
        <el-table-column prop="handler" label="承办人" min-width="100" />
        <el-table-column prop="handling_department" label="承办部门" min-width="130" />
        <el-table-column prop="handling_date" label="承办日期" min-width="110" />
        <el-table-column prop="contract_type" label="合同类型" min-width="110" />
        <el-table-column prop="is_archived" label="是否归档" min-width="90" />
        <el-table-column prop="project" label="项目" min-width="220" show-overflow-tooltip />
     
        <el-table-column label="操作" width="140" fixed="right" align="center">
          <template #default="scope">
            <div class="action-buttons">
              <el-upload
                :show-file-list="false"
                :http-request="(options) => doUpload(scope.row.id, options.file)"
              >
                <el-tooltip content="上传合同" placement="top">
                  <el-button circle size="small" :icon="Upload" />
                </el-tooltip>
              </el-upload>
              <el-tooltip content="编辑" placement="top">
                <el-button circle size="small" type="primary" :icon="Edit" @click.stop="openEdit(scope.row)" />
              </el-tooltip>
              <el-tooltip content="删除" placement="top">
                <el-button circle size="small" type="danger" :icon="Delete" @click.stop="handleDelete(scope.row)" />
              </el-tooltip>
            </div>
          </template>
        </el-table-column>
      </el-table>

      <div class="pager">
        <el-pagination
          v-model:current-page="currentPage"
          :page-size="pageSize"
          :total="totalContracts"
          layout="total, prev, pager, next, jumper"
          background
        />
      </div>
    </el-card>

    <el-dialog v-model="aiMatchDialogVisible" title="识别结果确认" width="min(1080px, 96vw)">
      <div class="ai-match-dialog">
        <div class="ai-match-preview-column">
          <div class="preview-header">
            <div class="preview-title">上传文件预览</div>
          </div>
          <div
            class="preview-panel"
            :class="{ 'preview-panel-clickable': !!previewUrl && !previewLoading }"
            @click="openFullscreenPreview"
          >
            <div v-if="previewLoading" class="preview-placeholder">预览加载中...</div>
            <VuePdfEmbed
              v-else-if="previewUrl"
              :source="previewUrl"
              class="pdf-preview-embed"
              @rendering-failed="handlePdfRenderFailed"
            />
            <div v-else class="preview-placeholder">{{ previewMessage }}</div>
          </div>
          <div v-if="previewUrl && !previewLoading" class="preview-hint">点击预览区域可全屏查看</div>
        </div>

        <div class="ai-match-content">
          <div class="ai-match-summary">
            <div class="ai-match-title">AI 已完成解析，请先确认这是新合同还是已有合同。</div>
            <div class="ai-match-subtitle">系统已按合同标题相似度和金额相同规则筛出候选合同。</div>
          </div>

          <el-table
            :data="aiMatchCandidates"
            stripe
            size="small"
            class="ai-match-table"
            empty-text="未找到相似合同，可直接选择“这是新合同”"
            @row-click="handleAiMatchRowClick"
          >
            <el-table-column label="选择" width="74" align="center">
              <template #default="scope">
                <input
                  class="ai-match-radio"
                  type="radio"
                  name="ai-match-selection"
                  :checked="aiMatchSelection === String(scope.row.id)"
                  @change="selectAiMatchCandidate(scope.row.id)"
                />
              </template>
            </el-table-column>
            <el-table-column label="文件" min-width="240">
              <template #default="scope">
                <el-link v-if="scope.row.file_path" class="file-cell" @click.stop="openFilePreview(scope.row)">
                  <Icon :icon="getFileIcon(scope.row.file_path)" class="file-ok file-download" />
                  <span class="file-name" :title="getFileName(scope.row.file_path)">
                    {{ getFileName(scope.row.file_path) }}
                  </span>
                </el-link>
                <span v-else class="no-file-name">未上传</span>
              </template>
            </el-table-column>
            <el-table-column prop="contract_name" label="合同名称" min-width="280" show-overflow-tooltip />
            <el-table-column prop="contract_amount_wan" label="金额(万元)" min-width="130" />
            <el-table-column label="匹配依据" min-width="160">
              <template #default="scope">
                {{ formatAiMatchReasons(scope.row) }}
              </template>
            </el-table-column>
          </el-table>

          <label class="ai-match-new-option" @click="selectAiMatchAsNew">
            <input
              class="ai-match-radio"
              type="radio"
              name="ai-match-selection"
              :checked="aiMatchSelection === AI_NEW_CONTRACT_VALUE"
              @change="selectAiMatchAsNew"
            />
            <span>这是新合同</span>
          </label>
        </div>
      </div>

      <template #footer>
        <el-button @click="closeAiMatchDialog">取消</el-button>
        <el-button type="primary" :loading="aiMatchProcessing" @click="proceedAiMatchSelection">下一步</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="dialogVisible" :title="editing ? '编辑合同' : '新建合同'" width="min(1380px, 98vw)">
      <el-form :model="form" label-width="120px" class="dialog-form">
        <div class="dialog-layout">
          <div class="preview-column">
            <div class="preview-header">
              <div class="preview-title">文件预览</div>
              <div class="preview-actions">

                <el-button size="small" @click="textDialogVisible = true">文本</el-button>

                <el-upload
                  :show-file-list="false"
                  :http-request="(options) => handleDialogUpload(options.file)"
                >
                  <el-button :icon="Upload" size="small">上传文件</el-button>
                </el-upload>
              </div>
            </div>
            <div
              class="preview-panel"
              :class="{ 'preview-panel-clickable': !!previewUrl && !previewLoading }"
              @click="openFullscreenPreview"
            >
              <div v-if="previewLoading" class="preview-placeholder">预览加载中...</div>
              <VuePdfEmbed
                v-else-if="previewUrl"
                :source="previewUrl"
                class="pdf-preview-embed"
                @rendering-failed="handlePdfRenderFailed"
              />
              <div v-else class="preview-placeholder">{{ previewMessage }}</div>
            </div>
            <div v-if="previewUrl && !previewLoading" class="preview-hint">点击预览区域可全屏查看</div>
          </div>

          <div class="form-column">
            <div class="form-grid">
          
              <el-form-item label="合同名称"  class="form-item-span-2">
                <el-input v-model="form.contract_name" />
              </el-form-item>
              <el-form-item label="合同编号">
                <el-input v-model="form.contract_number" />
              </el-form-item>
              <el-form-item label="合同单位">
                <el-input v-model="form.contract_unit" />
              </el-form-item>
              <el-form-item label="合同金额(万元)">
                <el-input
                  v-model="form.contract_amount_wan"
                  inputmode="decimal"
                  placeholder="支持最多 8 位及以上精确小数输入"
                  @blur="normalizeContractAmount"
                />
              </el-form-item>
              <el-form-item label="审批状态">
                <el-select v-model="form.approval_status" clearable placeholder="可留空" style="width: 100%">
                  <el-option v-for="item in options.approval_status" :key="item" :label="item" :value="item" />
                </el-select>
              </el-form-item>
              <el-form-item label="承办人">
                <el-input v-model="form.handler" clearable placeholder="可留空" />
              </el-form-item>
              <el-form-item label="承办部门">
                <el-select v-model="form.handling_department" placeholder="请选择部门" style="width: 100%">
                  <el-option v-for="item in departments" :key="item" :label="item" :value="item" />
                </el-select>
              </el-form-item>
              <el-form-item label="合同确定方式">
                <el-select v-model="form.contract_determination_method" placeholder="请选择合同确定方式" style="width: 100%">
                  <el-option v-for="item in options.contract_determination_method" :key="item" :label="item" :value="item" />
                </el-select>
              </el-form-item>
              <el-form-item label="承办日期">
                <el-date-picker v-model="form.handling_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
              </el-form-item>
              <el-form-item label="合同类型">
                <el-select v-model="form.contract_type" placeholder="请选择合同类型" style="width: 100%">
                  <el-option v-for="item in options.contract_type" :key="item" :label="item" :value="item" />
                </el-select>
              </el-form-item>
              <el-form-item label="发票类型">
                <el-select v-model="form.invoice_type" placeholder="请选择发票类型" style="width: 100%">
                  <el-option v-for="item in options.invoice_type" :key="item" :label="item" :value="item" />
                </el-select>
              </el-form-item>
              <el-form-item label="税率">
                <el-input v-model="form.tax_rate" />
              </el-form-item>
              <el-form-item label="计价方式">
                <el-select v-model="form.pricing_method" placeholder="请选择计价方式" style="width: 100%">
                  <el-option v-for="item in options.pricing_method" :key="item" :label="item" :value="item" />
                </el-select>
              </el-form-item>
              <el-form-item label="是否归档">
                <el-select v-model="form.is_archived" style="width: 100%">
                  <el-option v-for="item in options.is_archived" :key="item" :label="item" :value="item" />
                </el-select>
              </el-form-item>
              <el-form-item label="项目">
                <el-select v-model="form.project" clearable placeholder="可留空" style="width: 100%" filterable>
                  <el-option v-for="item in options.project" :key="item" :label="item" :value="item" />
                </el-select>
              </el-form-item>

              <el-form-item label="文件路径">
                <el-input v-model="form.file_path" readonly placeholder="暂无文件路径" />
              </el-form-item>
            </div>
          </div>
        </div>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button :loading="saving" type="primary" @click="saveContract">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="fullPreviewVisible"
      width="96vw"
      top="2vh"
      destroy-on-close
      append-to-body
    >
      <template #header>
        <div class="fullscreen-dialog-header">
          <span class="fullscreen-dialog-title">{{ fullPreviewTitle }}</span>
          <el-button
            type="primary"
            :disabled="!currentPreviewRow?.file_path"
            @click="downloadContractFile(currentPreviewRow)"
          >
            下载原文件
          </el-button>
        </div>
      </template>

      <div class="fullscreen-preview-wrapper">
        <VuePdfEmbed
          v-if="previewUrl"
          :source="previewUrl"
          class="pdf-preview-embed fullscreen-pdf-preview"
          @rendering-failed="handlePdfRenderFailed"
        />
        <div v-else class="preview-placeholder fullscreen-preview-placeholder">暂无可预览内容</div>
      </div>

      <template #footer>
        <el-button @click="fullPreviewVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="textDialogVisible" title="合同文本" width="min(960px, 96vw)">
      <el-input
        v-model="form.fullbody"
        type="textarea"
        :rows="24"
        resize="vertical"
        placeholder="暂无文本内容"
      />

      <template #footer>
        <el-button @click="textDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Icon } from '@iconify/vue'
import VuePdfEmbed from 'vue-pdf-embed'
import fileTypeWord from '@iconify-icons/vscode-icons/file-type-word'
import fileTypeExcel from '@iconify-icons/vscode-icons/file-type-excel'
import fileTypePdf from '@iconify-icons/vscode-icons/file-type-pdf2'
import microsoftOffice from '@iconify-icons/simple-icons/microsoftoffice'
import { CircleCloseFilled, Delete, Edit, Upload } from '@element-plus/icons-vue'
import { GlobalWorkerOptions } from 'pdfjs-dist/legacy/build/pdf.mjs'
import PdfWorker from 'pdfjs-dist/legacy/build/pdf.worker.min.mjs?url'

import http from '../api/http'

GlobalWorkerOptions.workerSrc = PdfWorker

const AI_NEW_CONTRACT_VALUE = '__new_contract__'

const contracts = ref([])
const departments = ref([])
const saving = ref(false)
const aiParsing = ref(false)
const aiMatchDialogVisible = ref(false)
const aiMatchProcessing = ref(false)
const aiMatchCandidates = ref([])
const aiMatchSelection = ref(AI_NEW_CONTRACT_VALUE)
const aiParsedFields = ref(null)
const aiParsedFullbody = ref('')
const aiParsedUploadFile = ref(null)
const previewFileName = ref('')
const importingExcel = ref(false)
const dialogVisible = ref(false)
const textDialogVisible = ref(false)
const editing = ref(null)
const currentPage = ref(1)
const excelUploadInput = ref(null)
const aiUploadInput = ref(null)
const pendingAiUploadFile = ref(null)
const previewUrl = ref('')
const previewLoading = ref(false)
const previewMessage = ref('暂无文件')
const fullPreviewVisible = ref(false)
const currentPreviewRow = ref(null)
const pageSize = 100

const filters = reactive({
  handling_department: '',
  approval_status: '',
  keyword: '',
})

const options = reactive({
  approval_status: [],
  contract_determination_method: [],
  contract_type: [],
  invoice_type: [],
  pricing_method: [],
  is_archived: [],
  project: [],
})

const totalContracts = computed(() => contracts.value.length)
const pagedContracts = computed(() => {
  const start = (currentPage.value - 1) * pageSize
  return contracts.value.slice(start, start + pageSize)
})
const contractNameColumnWidth = computed(() => {
  const baseWidth = 220
  const maxWidth = 560
  const longestLength = contracts.value.reduce((maxLength, item) => {
    const text = String(item?.contract_name || '')
    return Math.max(maxLength, text.length)
  }, 0)

  return Math.min(maxWidth, Math.max(baseWidth, longestLength * 12 + 16))
})
const fullPreviewTitle = computed(() => {
  if (previewFileName.value) {
    return `文件预览 - ${previewFileName.value}`
  }
  const name = getFileName(currentPreviewRow.value?.file_path || '')
  return name ? `文件预览 - ${name}` : '文件预览'
})

const form = reactive({
  file_path: '',
  contract_name: '',
  contract_number: '',
  contract_unit: '',
  contract_amount_wan: '',
  approval_status: '',
  handler: '',
  handling_department: '',
  contract_determination_method: '',
  handling_date: '',
  contract_type: '',
  invoice_type: '',
  tax_rate: '',
  pricing_method: '',
  is_archived: '未归档',
  project: '',
  fullbody: '',
})

const resetForm = () => {
  form.file_path = ''
  form.contract_name = ''
  form.contract_number = ''
  form.contract_unit = ''
  form.contract_amount_wan = ''
  form.approval_status = ''
  form.handler = ''
  form.handling_department = ''
  form.contract_determination_method = ''
  form.handling_date = ''
  form.contract_type = ''
  form.invoice_type = ''
  form.tax_rate = ''
  form.pricing_method = ''
  form.is_archived = '未归档'
  form.project = ''
  form.fullbody = ''
}

const resetAiMatchState = () => {
  aiMatchCandidates.value = []
  aiMatchSelection.value = AI_NEW_CONTRACT_VALUE
  aiParsedFields.value = null
  aiParsedFullbody.value = ''
  aiParsedUploadFile.value = null
  aiMatchProcessing.value = false
}

const loadContractDetail = async (contractId) => {
  const { data } = await http.get(`/contracts/${contractId}`)
  return data
}

const loadDepartments = async () => {
  const { data } = await http.get('/settings/departments')
  departments.value = (Array.isArray(data) ? data : []).map((item) => item.name)
}

const loadFieldOptions = async () => {
  const { data } = await http.get('/options/contract-fields')
  options.approval_status = data?.approval_status || []
  options.contract_determination_method = data?.contract_determination_method || []
  options.contract_type = data?.contract_type || []
  options.invoice_type = data?.invoice_type || []
  options.pricing_method = data?.pricing_method || []
  options.is_archived = data?.is_archived || []
  options.project = data?.project || []
}

const loadContracts = async () => {
  const { data } = await http.get('/contracts', {
    params: {
      handling_department: filters.handling_department || undefined,
      approval_status: filters.approval_status || undefined,
      keyword: filters.keyword || undefined,
    },
  })
  contracts.value = data
  currentPage.value = 1
}

const openCreate = () => {
  editing.value = null
  pendingAiUploadFile.value = null
  currentPreviewRow.value = null
  previewFileName.value = ''
  resetForm()
  resetPreview('暂无文件')
  dialogVisible.value = true
}

const isBlankValue = (value) => String(value ?? '').trim() === ''

const populateFormFromContract = (row) => {
  form.file_path = row.file_path || ''
  form.contract_name = row.contract_name || ''
  form.contract_number = row.contract_number || ''
  form.contract_unit = row.contract_unit || ''
  form.contract_amount_wan = normalizeAmountInputValue(row.contract_amount_wan)
  form.approval_status = row.approval_status || ''
  form.handler = row.handler || ''
  form.handling_department = row.handling_department || row.department || ''
  form.contract_determination_method = row.contract_determination_method || ''
  form.handling_date = row.handling_date || ''
  form.contract_type = row.contract_type || ''
  form.invoice_type = row.invoice_type || ''
  form.tax_rate = row.tax_rate || ''
  form.pricing_method = row.pricing_method || ''
  form.is_archived = row.is_archived || '未归档'
  form.project = row.project || ''
  form.fullbody = row.fullbody || ''
}

const applyAiSupplementalFields = (fields, sourceRow = {}) => {
  const mapping = [
    ['contract_name', 'contract_name'],
    ['contract_number', 'contract_number'],
    ['contract_unit', 'contract_unit'],
    ['contract_amount_wan', 'contract_amount_wan'],
    ['approval_status', 'approval_status'],
    ['handler', 'handler'],
    ['handling_department', 'handling_department'],
    ['contract_determination_method', 'contract_determination_method'],
    ['handling_date', 'handling_date'],
    ['contract_type', 'contract_type'],
    ['invoice_type', 'invoice_type'],
    ['tax_rate', 'tax_rate'],
    ['pricing_method', 'pricing_method'],
    ['is_archived', 'is_archived'],
    ['project', 'project'],
    ['fullbody', 'fullbody'],
  ]

  for (const [formKey, fieldKey] of mapping) {
    const incomingRaw = fields?.[fieldKey]
    const incomingValue = formKey === 'contract_amount_wan'
      ? normalizeAmountInputValue(incomingRaw)
      : String(incomingRaw ?? '').trim()

    if (isBlankValue(incomingValue)) {
      continue
    }

    const existingValue = formKey === 'handling_department'
      ? (sourceRow?.handling_department || sourceRow?.department || '')
      : sourceRow?.[formKey]

    if (!isBlankValue(existingValue)) {
      continue
    }

    form[formKey] = incomingValue
  }
}

const openCreateFromAi = (file, fields) => {
  editing.value = null
  pendingAiUploadFile.value = file
  currentPreviewRow.value = null
  previewFileName.value = file?.name || ''
  resetForm()
  form.file_path = file?.name || ''
  applyParsedFields(fields || {})
  form.fullbody = aiParsedFullbody.value || ''
  setPreviewFromFile(file)
  dialogVisible.value = true
}

const openEditWithSupplementalFields = async (row, fields) => {
  const detail = row?.id ? await loadContractDetail(row.id) : row
  editing.value = detail
  currentPreviewRow.value = detail
  previewFileName.value = ''
  pendingAiUploadFile.value = null
  populateFormFromContract(detail)
  applyAiSupplementalFields(fields || {}, detail)
  loadPdfPreviewForRow(detail)
  dialogVisible.value = true
}

const triggerExcelUpload = () => {
  if (importingExcel.value) {
    return
  }
  excelUploadInput.value?.click()
}

const triggerAiUpload = () => {
  if (aiParsing.value) {
    return
  }
  aiUploadInput.value?.click()
}

const handleExcelSelected = async (event) => {
  const file = event?.target?.files?.[0]
  if (!file) {
    return
  }

  if (!/\.(xls|xlsx)$/i.test(file.name)) {
    ElMessage.warning('请上传 xls 或 xlsx 文件')
    event.target.value = ''
    return
  }

  importingExcel.value = true
  try {
    const fd = new FormData()
    fd.append('file', file)

    const { data } = await http.post('/contracts/import-excel', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 300000,
    })

    await loadFieldOptions()
    await loadContracts()

    const summary = `导入完成：成功 ${data?.imported_count || 0} 条，跳过 ${data?.skipped_count || 0} 条。`
    const errorLines = Array.isArray(data?.errors)
      ? data.errors.slice(0, 10).map((item) => `第 ${item.row} 行：${item.message}`)
      : []

    if (errorLines.length > 0) {
      await ElMessageBox.alert(`${summary}\n\n${errorLines.join('\n')}`, 'EXCEL导入结果', {
        confirmButtonText: '知道了',
      })
      if (data?.error_report_token) {
        await downloadImportErrorReport(data.error_report_token, data.error_report_filename)
        ElMessage.success('失败明细已下载，可修正后再次导入')
      }
    } else {
      ElMessage.success(summary)
    }
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || 'EXCEL 导入失败')
  } finally {
    importingExcel.value = false
    event.target.value = ''
  }
}

const downloadImportTemplate = async () => {
  try {
    const response = await http.get('/contracts/import-template', {
      responseType: 'blob',
    })
    const headerName = parseFilenameFromDisposition(response.headers?.['content-disposition'])
    triggerBrowserDownload(response.data, headerName || '合同导入模板.xlsx')
  } catch (error) {
    const message = await parseErrorMessage(error, '导入模板下载失败')
    ElMessage.error(message)
  }
}

const downloadImportErrorReport = async (token, fallbackName = '合同导入失败明细.xlsx') => {
  const response = await http.get(`/contracts/import-error-report/${token}`, {
    responseType: 'blob',
  })
  const headerName = parseFilenameFromDisposition(response.headers?.['content-disposition'])
  triggerBrowserDownload(response.data, headerName || fallbackName)
}

const applyParsedFields = (fields) => {
  form.contract_name = fields?.contract_name || ''
  form.contract_number = fields?.contract_number || ''
  form.contract_unit = fields?.contract_unit || ''
  form.contract_amount_wan = normalizeAmountInputValue(fields?.contract_amount_wan || '')
  form.approval_status = fields?.approval_status || ''
  form.handler = fields?.handler || ''
  form.handling_department = fields?.handling_department || ''
  form.contract_determination_method = fields?.contract_determination_method || ''
  form.handling_date = fields?.handling_date || ''
  form.contract_type = fields?.contract_type || ''
  form.invoice_type = fields?.invoice_type || ''
  form.tax_rate = fields?.tax_rate || ''
  form.pricing_method = fields?.pricing_method || ''
  form.is_archived = fields?.is_archived || '未归档'
  form.project = fields?.project || ''
  form.fullbody = fields?.fullbody || ''
}

const selectAiMatchCandidate = (contractId) => {
  aiMatchSelection.value = String(contractId)
}

const selectAiMatchAsNew = () => {
  aiMatchSelection.value = AI_NEW_CONTRACT_VALUE
}

const handleAiMatchRowClick = (row) => {
  if (row?.id) {
    selectAiMatchCandidate(row.id)
  }
}

const formatAiMatchReasons = (row) => {
  const reasons = Array.isArray(row?.match_reasons)
    ? row.match_reasons.filter((item) => String(item || '').trim())
    : []

  if (reasons.length > 0) {
    return reasons.join(' / ')
  }

  const fallback = []
  if (row?.name_similarity > 0) {
    fallback.push('标题相似')
  }
  if (row?.same_amount) {
    fallback.push('金额相同')
  }
  return fallback.join(' / ')
}

const closeAiMatchDialog = () => {
  aiMatchDialogVisible.value = false
  resetAiMatchState()
  previewFileName.value = ''
}

const proceedAiMatchSelection = async () => {
  const selectedValue = aiMatchSelection.value
  const selectedFile = aiParsedUploadFile.value
  const parsedFields = aiParsedFields.value || {}

  if (!selectedFile) {
    ElMessage.error('AI上传文件状态已丢失，请重新上传')
    closeAiMatchDialog()
    return
  }

  aiMatchProcessing.value = true
  try {
    if (selectedValue === AI_NEW_CONTRACT_VALUE) {
      aiMatchDialogVisible.value = false
      openCreateFromAi(selectedFile, parsedFields)
      resetAiMatchState()
      return
    }

    const selectedId = Number(selectedValue)
    const matchedRow = aiMatchCandidates.value.find((item) => item.id === selectedId)
    if (!matchedRow) {
      ElMessage.warning('请选择要关联的已有合同，或选择“这是新合同”')
      return
    }

    const uploadResult = await doUpload(matchedRow.id, selectedFile)
    const mergedRow = {
      ...matchedRow,
      file_path: uploadResult?.file_path || matchedRow.file_path,
    }

    aiMatchDialogVisible.value = false
    await openEditWithSupplementalFields(mergedRow, parsedFields)
    ElMessage.success('已关联到已有合同，请确认补充字段后保存')
    resetAiMatchState()
  } finally {
    aiMatchProcessing.value = false
  }
}

const handleAiPdfSelected = async (event) => {
  const file = event?.target?.files?.[0]
  if (!file) {
    return
  }

  if (!/\.pdf$/i.test(file.name)) {
    ElMessage.warning('请上传PDF文件')
    event.target.value = ''
    return
  }

  resetAiMatchState()
  pendingAiUploadFile.value = null
  aiParsing.value = true
  ElMessage.info('AI正在解析PDF，请稍候')
  try {
    const fd = new FormData()
    fd.append('file', file)
    const { data } = await http.post('/contracts/ai-parse', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 300000,
    })

    const parsedFullbody = data?.fullbody || ''
    const parsedFields = {
      ...(data?.fields || {}),
      fullbody: parsedFullbody,
    }

    aiParsedUploadFile.value = file
    aiParsedFields.value = parsedFields
    aiParsedFullbody.value = parsedFullbody
    aiMatchCandidates.value = Array.isArray(data?.match_candidates) ? data.match_candidates : []
    aiMatchSelection.value = AI_NEW_CONTRACT_VALUE
    previewFileName.value = file.name
    setPreviewFromFile(file)
    aiMatchDialogVisible.value = true
    ElMessage.success('AI解析完成，请先确认是否匹配到已有合同')
  } catch (error) {
    if (error?.code === 'ECONNABORTED') {
      ElMessage.error('AI解析超时，请稍后重试')
      return
    }

    const baseMessage = error?.response?.data?.message || 'AI解析失败'
    const previewLines = error?.response?.data?.ocr_preview_lines
    if (Array.isArray(previewLines) && previewLines.length > 0) {
      const preview = previewLines.slice(0, 3).join(' / ')
      ElMessage.error(`${baseMessage}；识别预览：${preview}`)
    } else {
      ElMessage.error(baseMessage)
    }
  } finally {
    aiParsing.value = false
    event.target.value = ''
  }
}

const openEdit = (row) => {
  openEditWithSupplementalFields(row, null)
}

const revokePreviewUrl = () => {
  if (previewUrl.value) {
    window.URL.revokeObjectURL(previewUrl.value)
    previewUrl.value = ''
  }
}

const resetPreview = (message = '暂无文件', closeFullscreen = true) => {
  previewLoading.value = false
  previewMessage.value = message
  if (closeFullscreen) {
    fullPreviewVisible.value = false
  }
  revokePreviewUrl()
}

const isPdfFilePath = (filePath) => getFileExt(filePath) === 'pdf'

const setPreviewFromBlob = (blob) => {
  revokePreviewUrl()
  const source = blob instanceof Blob ? blob : new Blob([blob], { type: 'application/pdf' })
  const safeBlob = source.type && source.type.includes('pdf')
    ? source
    : new Blob([source], { type: 'application/pdf' })
  previewUrl.value = window.URL.createObjectURL(safeBlob)
  previewMessage.value = ''
}

const setPreviewFromFile = (file) => {
  if (!file) {
    previewFileName.value = ''
    resetPreview('暂无文件')
    return
  }
  previewFileName.value = file.name || ''
  if (!/\.pdf$/i.test(file.name)) {
    resetPreview('该文件不是PDF，无法预览')
    return
  }
  setPreviewFromBlob(file)
}

const handlePdfRenderFailed = () => {
  resetPreview('PDF组件渲染失败，请检查文件内容或浏览器兼容性')
}

const openFullscreenPreview = () => {
  if (!previewUrl.value || previewLoading.value) {
    return
  }
  fullPreviewVisible.value = true
}

const openFilePreview = async (row) => {
  if (!row?.file_path) {
    ElMessage.warning('该合同未上传文件')
    return
  }

  currentPreviewRow.value = row
  previewFileName.value = ''
  fullPreviewVisible.value = true

  if (!isPdfFilePath(row.file_path)) {
    resetPreview('该文件不是PDF，无法预览，请使用下方按钮下载原文件', false)
    return
  }

  await loadPdfPreviewForRow(row, false)
}

const loadPdfPreviewForRow = async (row, closeFullscreenOnError = true) => {
  if (!row?.file_path) {
    resetPreview('暂无文件', closeFullscreenOnError)
    return
  }

  if (!isPdfFilePath(row.file_path)) {
    resetPreview('该文件不是PDF，无法预览', closeFullscreenOnError)
    return
  }

  previewLoading.value = true
  previewFileName.value = getFileName(row.file_path)
  previewMessage.value = ''
  try {
    const response = await http.get(`/contracts/${row.id}/preview`, {
      responseType: 'blob',
    })
    setPreviewFromBlob(response.data)
  } catch (error) {
    const message = await parseErrorMessage(error, 'PDF预览加载失败')
    resetPreview(`PDF预览加载失败：${message}`, closeFullscreenOnError)
    ElMessage.warning(message)
  } finally {
    previewLoading.value = false
  }
}

const normalizeAmountInputValue = (value) => {
  const raw = String(value ?? '').trim()
  if (!raw) {
    return ''
  }

  const normalized = raw
    .replace(/[，,\s]/g, '')
    .replace(/。/g, '.')

  if (/^\d*(?:\.\d*)?$/.test(normalized)) {
    return normalized
  }

  return raw
}

const normalizeContractAmount = () => {
  form.contract_amount_wan = normalizeAmountInputValue(form.contract_amount_wan)
}

const saveContract = async () => {
  const normalizedAmount = normalizeAmountInputValue(form.contract_amount_wan)

  if (!form.contract_name || !form.handling_department || !normalizedAmount) {
    ElMessage.warning('请填写必要字段')
    return
  }

  if (!/^\d+(?:\.\d+)?$/.test(normalizedAmount)) {
    ElMessage.warning('合同金额请输入纯数字，可带小数点')
    return
  }

  form.contract_amount_wan = normalizedAmount

  if (!departments.value.includes(form.handling_department)) {
    ElMessage.warning('请选择系统设置中的有效部门')
    return
  }

  if (form.project && !options.project.includes(form.project)) {
    ElMessage.warning('请选择项目设置中的有效项目')
    return
  }

  saving.value = true
  try {
    if (editing.value) {
      await http.put(`/contracts/${editing.value.id}`, {
        contract_number: form.contract_number,
        contract_name: form.contract_name,
        contract_unit: form.contract_unit,
        contract_amount_wan: normalizedAmount,
        approval_status: form.approval_status,
        handler: form.handler,
        handling_department: form.handling_department,
        contract_determination_method: form.contract_determination_method,
        handling_date: form.handling_date,
        contract_type: form.contract_type,
        invoice_type: form.invoice_type,
        tax_rate: form.tax_rate,
        pricing_method: form.pricing_method,
        is_archived: form.is_archived,
        project: form.project,
        fullbody: form.fullbody,
      })
      ElMessage.success('更新成功')
    } else {
      const { data: created } = await http.post('/contracts', {
        contract_number: form.contract_number,
        contract_name: form.contract_name,
        contract_unit: form.contract_unit,
        contract_amount_wan: normalizedAmount,
        approval_status: form.approval_status,
        handler: form.handler,
        handling_department: form.handling_department,
        contract_determination_method: form.contract_determination_method,
        handling_date: form.handling_date,
        contract_type: form.contract_type,
        invoice_type: form.invoice_type,
        tax_rate: form.tax_rate,
        pricing_method: form.pricing_method,
        is_archived: form.is_archived,
        project: form.project,
        fullbody: form.fullbody,
      })

      if (pendingAiUploadFile.value) {
        const fd = new FormData()
        fd.append('file', pendingAiUploadFile.value)
        await http.post(`/contracts/${created.id}/upload`, fd, {
          headers: { 'Content-Type': 'multipart/form-data' },
        })
      }

      pendingAiUploadFile.value = null
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    await loadDepartments()
    await loadFieldOptions()
    await loadContracts()
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || '保存失败')
  } finally {
    saving.value = false
  }
}

const syncEditingFileState = async (filePath) => {
  const normalizedFilePath = filePath || ''
  form.file_path = normalizedFilePath

  if (editing.value) {
    editing.value.file_path = normalizedFilePath
  }
  if (currentPreviewRow.value?.id === editing.value?.id) {
    currentPreviewRow.value.file_path = normalizedFilePath
  }

  if (!normalizedFilePath) {
    resetPreview('暂无文件', false)
    return
  }

  await loadPdfPreviewForRow({ id: editing.value.id, file_path: normalizedFilePath }, false)
}

const doUpload = async (contractId, file) => {
  const fd = new FormData()
  fd.append('file', file)
  try {
    const { data } = await http.post(`/contracts/${contractId}/upload`, fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    ElMessage.success('上传成功')
    await loadContracts()
    return data
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || '上传失败')
    throw error
  }
}

const handleDelete = async (row) => {
  if (!row?.id) {
    return
  }

  try {
    await ElMessageBox.confirm(
      `确认删除合同《${row.contract_name || '未命名合同'}》吗？\n这会同时删除合同数据和已上传文件，且无法恢复。`,
      '删除确认',
      {
        confirmButtonText: '删除',
        cancelButtonText: '取消',
        type: 'warning',
      },
    )

    await http.delete(`/contracts/${row.id}`)

    if (editing.value?.id === row.id) {
      dialogVisible.value = false
      textDialogVisible.value = false
      editing.value = null
      pendingAiUploadFile.value = null
      resetForm()
    }

    if (currentPreviewRow.value?.id === row.id) {
      currentPreviewRow.value = null
      previewFileName.value = ''
      resetPreview('暂无文件')
    }

    ElMessage.success('删除成功')
    await loadContracts()
  } catch (error) {
    if (error === 'cancel' || error === 'close') {
      return
    }
    ElMessage.error(error?.response?.data?.message || '删除失败')
  }
}

const handleDialogUpload = async (file) => {
  if (!editing.value?.id) {
    pendingAiUploadFile.value = file
    form.file_path = file?.name || ''
    currentPreviewRow.value = null
    setPreviewFromFile(file)
    ElMessage.success('文件已选择，保存合同后会自动上传')
    return
  }

  const data = await doUpload(editing.value.id, file)
  await syncEditingFileState(data?.file_path)
}

const parseFilenameFromDisposition = (value) => {
  if (!value) {
    return ''
  }

  const utf8Match = value.match(/filename\*=UTF-8''([^;]+)/i)
  if (utf8Match?.[1]) {
    return decodeURIComponent(utf8Match[1].replace(/"/g, '').trim())
  }

  const plainMatch = value.match(/filename=([^;]+)/i)
  if (plainMatch?.[1]) {
    return plainMatch[1].replace(/"/g, '').trim()
  }

  return ''
}

const getFileName = (filePath) => {
  if (!filePath) {
    return ''
  }
  const normalized = String(filePath).replace(/\\/g, '/')
  const parts = normalized.split('/')
  return parts[parts.length - 1] || normalized
}

const getFileExt = (filePath) => {
  const name = getFileName(filePath).toLowerCase()
  const dotIndex = name.lastIndexOf('.')
  if (dotIndex < 0 || dotIndex === name.length - 1) {
    return ''
  }
  return name.slice(dotIndex + 1)
}

const getFileIcon = (filePath) => {
  const ext = getFileExt(filePath)
  if (ext === 'doc' || ext === 'docx') {
    return fileTypeWord
  }
  if (ext === 'xls' || ext === 'xlsx') {
    return fileTypeExcel
  }
  if (ext === 'pdf') {
    return fileTypePdf
  }
  if (ext === 'wps') {
    return microsoftOffice
  }
  return fileTypeWord
}

const triggerBrowserDownload = (blob, filename) => {
  const url = window.URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename || 'download.bin'
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  window.URL.revokeObjectURL(url)
}

const parseErrorMessage = async (error, fallbackMessage) => {
  const directMessage = error?.response?.data?.message
  if (directMessage) {
    return directMessage
  }

  const blobData = error?.response?.data
  if (blobData instanceof Blob) {
    try {
      const text = await blobData.text()
      const parsed = JSON.parse(text)
      if (parsed?.message) {
        return parsed.message
      }
    } catch (_e) {
      return fallbackMessage
    }
  }

  return fallbackMessage
}

const downloadContractFile = async (row) => {
  if (!row?.file_path) {
    ElMessage.warning('该合同未上传文件')
    return
  }

  try {
    const response = await http.get(`/contracts/${row.id}/download`, {
      responseType: 'blob',
    })

    const headerName = parseFilenameFromDisposition(response.headers?.['content-disposition'])
    const fallbackName = row.file_path.split('/').pop() || `${row.contract_name || 'contract'}.bin`
    triggerBrowserDownload(response.data, headerName || fallbackName)
  } catch (error) {
    const message = await parseErrorMessage(error, '下载失败')
    ElMessage.error(message)
  }
}

onMounted(async () => {
  try {
    await loadDepartments()
    await loadFieldOptions()
    await loadContracts()
  } catch (_error) {
    ElMessage.error('数据加载失败')
  }
})

watch(dialogVisible, (visible) => {
  if (!visible) {
    resetPreview('暂无文件')
  }
})

watch(aiMatchDialogVisible, (visible) => {
  if (!visible && !aiMatchProcessing.value) {
    resetAiMatchState()
  }
})
</script>

<style>
.el-scrollbar{
    padding-bottom:32px;
}
</style>

<style scoped>
.contract-page {
  display: grid;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.header-actions {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.card-title {
  font-size: 18px;
  font-weight: 600;
}

.toolbar {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.contract-table :deep(.el-table__cell) {
  padding-top: 6px;
  padding-bottom: 6px;
}

.file-cell {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  max-width: 100%;
}
.no-file-name {
  color: #9ca3af;
  font-size: 14px;
  display: inline-block;
  position: relative;
  top: -2px;
  margin-left:4px;
}

.file-name {
  display: inline-block;
  max-width: 170px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: #374151;
  margin-left:4px;

}

.action-buttons {
  display: inline-flex;
  gap: 6px;
}

.file-ok {
  width: 18px;
  height: 18px;
  font-size: 18px;
}

.file-download {
  cursor: pointer;
}

.file-miss {
  color: #ef4444;
  font-size: 16px;
}

.contract-name-link {
  display: inline-flex;
  align-items: center;
  max-width: 100%;
  padding: 0;
  border: 0;
  background: transparent;
  color: #2563eb;
  font-weight: 500;
  cursor: pointer;
}

.contract-name-link:hover .contract-name-cell {
  text-decoration: underline;
}

.contract-name-link:focus-visible {
  outline: 2px solid rgba(37, 99, 235, 0.35);
  outline-offset: 2px;
  border-radius: 4px;
}

.contract-name-cell {
  display: inline-block;
  max-width: 100%;
  white-space: nowrap;
}

.pager {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
}

.ai-match-dialog {
  display: grid;
  grid-template-columns: minmax(300px, 0.9fr) minmax(0, 1.4fr);
  gap: 16px;
  align-items: start;
}

.ai-match-preview-column {
  border: 1px solid #ebeef5;
  border-radius: 8px;
  padding: 10px;
  background: #fafafa;
}

.ai-match-preview-column .preview-panel {
  height: min(62vh, 720px);
}

.ai-match-content {
  display: grid;
  gap: 12px;
}

.ai-match-summary {
  display: grid;
  gap: 4px;
}

.ai-match-title {
  font-size: 15px;
  font-weight: 600;
  color: #111827;
}

.ai-match-subtitle {
  font-size: 13px;
  color: #6b7280;
}

.ai-match-table :deep(.el-table__row) {
  cursor: pointer;
}

.ai-match-radio {
  width: 16px;
  height: 16px;
  cursor: pointer;
}

.ai-match-new-option {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  width: fit-content;
  cursor: pointer;
  color: #111827;
  font-weight: 500;
}

.dialog-layout {
  display: grid;
  grid-template-columns: 1fr;
  gap: 12px 16px;
}

.preview-column {
  border: 1px solid #ebeef5;
  border-radius: 8px;
  padding: 10px;
  background: #fafafa;
}

.preview-title {
  font-size: 14px;
  font-weight: 600;
  color: #374151;
}

.preview-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
}

.preview-panel {
  height: min(70vh, 760px);
  border: 1px dashed #d1d5db;
  border-radius: 6px;
  background: #fff;
  overflow: auto;
}

.preview-panel-clickable {
  cursor: zoom-in;
}

.preview-hint {
  margin-top: 8px;
  font-size: 12px;
  color: #6b7280;
  text-align: right;
}

.preview-placeholder {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #6b7280;
  padding: 12px;
  text-align: center;
}

.pdf-preview-embed {
  width: 100%;
  min-height: 100%;
  padding: 12px;
  box-sizing: border-box;
}

.pdf-preview-embed :deep(canvas) {
  width: 100% !important;
  height: auto !important;
  display: block;
  margin: 0 auto 12px;
}

.fullscreen-preview-wrapper {
  height: 88vh;
  overflow: auto;
  background: #f8fafc;
  border-radius: 8px;
  padding: 16px;
  box-sizing: border-box;
}

.fullscreen-dialog-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding-right: 32px;
}

.fullscreen-dialog-title {
  min-width: 0;
  font-size: 18px;
  font-weight: 600;
  color: #111827;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.fullscreen-pdf-preview {
  max-width: 1400px;
  margin: 0 auto;
}

.fullscreen-preview-placeholder {
  min-height: 60vh;
}

.dialog-form .form-column {
  min-width: 0;
}

.dialog-form .form-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 4px 16px;
}

.form-item-span-2 {
  grid-column: span 1;
}

.preview-actions{
    display: flex;
    gap: 8px;
}

@media (min-width: 1280px) {
  .dialog-layout {
    grid-template-columns: minmax(360px, 1.15fr) minmax(0, 1fr) minmax(0, 1fr);
    align-items: start;
  }

  .dialog-form .form-column {
    grid-column: 2 / span 2;
  }

  .dialog-form .form-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .form-item-span-2 {
    grid-column: span 2;
  }
}

@media (min-width: 1024px) {
  .preview-panel {
    height: min(62vh, 680px);
  }
}

@media (max-width: 1100px) {
  .ai-match-dialog {
    grid-template-columns: 1fr;
  }

  .ai-match-preview-column .preview-panel {
    height: min(48vh, 520px);
  }
}
</style>
