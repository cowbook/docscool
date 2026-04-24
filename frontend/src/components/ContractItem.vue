<template>
  <div>
    <el-dialog
      v-model="dialogVisible"
      :title="editing ? '编辑合同' : '新建合同'"
      width="min(1380px, 98vw)"
      top="2vh"
    >
      <el-form :model="form" label-width="120px" class="dialog-form">
        <div class="dialog-layout">
          <div class="preview-column">
            <div class="preview-header">
              <div class="preview-title">文件预览</div>
              <div class="preview-actions">
                <el-button
                  size="small"
                  type="primary"
                  :loading="aiParsing"
                  :disabled="aiParsing || (!form.file_path && !pendingAiUploadFile)"
                  @click="runAiRecognitionFromPreview"
                >
                  {{ aiParsing ? '识别中...' : 'AI识别' }}
                </el-button>
                <el-button size="small" @click="textDialogVisible = true">文本</el-button>

                <el-upload
                  v-if="props.showFileActions"
                  :show-file-list="false"
                  :http-request="(options) => handleDialogUpload(options.file)"
                >
                  <el-button :icon="Upload" size="small">上传文件</el-button>
                </el-upload>

                <el-button v-if="props.showFileActions" size="small" @click="openLinkFileDialog">链接文件</el-button>
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
            <div class="readonly-file-path" :title="form.file_path || ''">
              <el-link
                class="readonly-file-link"
                type="primary"
                :underline="!!form.file_path"
                :disabled="!form.file_path"
                @click="handleDialogFilePathDownload"
              >
                {{ form.file_path || '暂无文件路径' }}
              </el-link>
            </div>
          </div>

          <div class="form-column">
            <div class="form-grid">
              <el-form-item label="是否归档" class="form-item-span-2">
                <el-switch
                  v-model="form.is_archived"
                  active-text="已归档"
                  inactive-text="未归档"
                  active-value="已归档"
                  inactive-value="未归档"
                />
              </el-form-item>

              <el-form-item label="合同名称" class="form-item-span-2">
                <el-input v-model="form.contract_name" />
              </el-form-item>
              <el-form-item label="合同编号">
                <el-input v-model="form.contract_number" />
              </el-form-item>
              <el-form-item label="合同单位">
                <el-input v-model="form.contract_unit" />
              </el-form-item>
              <el-form-item label="合同金额">
                <el-input
                  v-model="form.contract_amount"
                  inputmode="decimal"
                  placeholder="支持最多 8 位及以上精确小数输入"
                  @blur="normalizeContractAmount"
                />
              </el-form-item>
              <el-form-item label="份数">
                <el-input
                  v-model="form.copy_count"
                  inputmode="numeric"
                  clearable
                  placeholder="纯数字，可留空"
                  @blur="normalizeCopyCount"
                />
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
                  <el-option v-for="item in normalizedOptions.contract_determination_method" :key="item" :label="item" :value="item" />
                </el-select>
              </el-form-item>
              <el-form-item label="承办日期">
                <el-date-picker v-model="form.handling_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
              </el-form-item>
              <el-form-item label="合同类型">
                <el-select v-model="form.contract_type" placeholder="请选择合同类型" style="width: 100%">
                  <el-option v-for="item in normalizedOptions.contract_type" :key="item" :label="item" :value="item" />
                </el-select>
              </el-form-item>
              <el-form-item label="采购类型">
                <el-select v-model="form.purchase_type" placeholder="请选择采购类型" style="width: 100%">
                  <el-option v-for="item in normalizedOptions.purchase_type" :key="item" :label="item" :value="item" />
                </el-select>
              </el-form-item>
              <el-form-item label="印花税率">
                <el-input v-model="form.stamp_tax_rate" placeholder="根据合同类型自动回填，可手动调整" clearable />
              </el-form-item>
              <el-form-item label="计价方式">
                <el-select v-model="form.pricing_method" placeholder="请选择计价方式" style="width: 100%">
                  <el-option v-for="item in normalizedOptions.pricing_method" :key="item" :label="item" :value="item" />
                </el-select>
              </el-form-item>
              <el-form-item label="项目">
                <el-select v-model="form.project" clearable placeholder="可留空" style="width: 100%" filterable>
                  <el-option v-for="item in normalizedOptions.project" :key="item" :label="item" :value="item" />
                </el-select>
              </el-form-item>
              <el-form-item label="存档位置">
                <el-input
                  v-model="form.save_place"
                  maxlength="50"
                  show-word-limit
                  clearable
                  placeholder="最多50个字符，可留空"
                />
              </el-form-item>
            </div>
          </div>
        </div>
      </el-form>

      <template #footer>
        <el-button
          v-if="!props.showFileActions"
          type="danger"
          :loading="saving"
          :disabled="!editing?.id"
          @click="unbindContract"
        >
          解绑合同
        </el-button>
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

    <el-dialog
      v-model="linkFileDialogVisible"
      class="link-file-dialog"
      title="选择并链接文件"
      width="min(1280px, 96vw)"
      top="2vh"
      :close-on-click-modal="false"
    >
      <div class="link-file-layout">
        <div class="link-file-left">
          <div class="panel-title">{{ linkRootName }}</div>
          <el-tree
            ref="linkTreeRef"
            v-loading="linkTreeLoading"
            :data="linkTreeData"
            node-key="path"
            :props="linkTreeProps"
            lazy
            :load="loadLinkTreeChildren"
            :expand-on-click-node="true"
            highlight-current
            @node-click="onLinkTreeNodeClick"
          >
            <template #default="{ node, data }">
              <span class="tree-node-content">
                <span class="tree-folder-icon" aria-hidden="true">{{ node.expanded ? '📂' : '📁' }}</span>
                <span class="tree-node-label">{{ data.name }}</span>
              </span>
            </template>
          </el-tree>
        </div>

        <div class="link-file-right">
          <div class="panel-title">文件列表（当前目录：{{ linkSelectedFolderPath || '/' }}）</div>
          <div class="link-file-table-wrap">
            <el-table
              v-loading="linkFilesLoading"
              :data="linkFiles"
              border
              stripe
              size="small"
              class="link-file-table"
              @row-click="handleLinkFileRowClick"
            >
              <el-table-column label="选择" width="72" align="center">
                <template #default="scope">
                  <input
                    type="radio"
                    name="link-file-selection"
                    :checked="linkSelectedFilePath === scope.row.file_path"
                    @change="handleLinkFileRowClick(scope.row)"
                  />
                </template>
              </el-table-column>
              <el-table-column label="文件" min-width="280">
                <template #default="scope">
                  <el-link class="file-cell link-file-name-link" type="primary" @click.stop="handleLinkFileRowClick(scope.row)">
                    <Icon :icon="getFileIcon(scope.row.file_path)" class="file-ok" />
                    <span class="file-name" :title="scope.row.name">{{ scope.row.name }}</span>
                  </el-link>
                </template>
              </el-table-column>
              <el-table-column prop="contract_name" label="匹配合同" min-width="220" show-overflow-tooltip />
            </el-table>
          </div>
        </div>

        <div
          class="link-file-preview-panel"
          :class="{ 'preview-panel-clickable': !!linkPreviewUrl && !linkPreviewLoading }"
          @click="openLinkFullscreenPreview"
        >
          <div v-if="linkPreviewLoading" class="preview-placeholder">预览加载中...</div>
          <VuePdfEmbed
            v-else-if="linkPreviewUrl"
            :source="linkPreviewUrl"
            class="pdf-preview-embed link-preview-embed"
            @rendering-failed="handleLinkPreviewFailed"
          />
          <div v-else class="preview-placeholder">{{ linkPreviewMessage }}</div>
        </div>
      </div>

      <template #footer>
        <el-button @click="closeLinkFileDialog">取消</el-button>
        <el-button type="primary" @click="confirmLinkFile">确认</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="linkFullPreviewVisible"
      width="96vw"
      top="2vh"
      destroy-on-close
      append-to-body
    >
      <template #header>
        <div class="fullscreen-dialog-header">
          <span class="fullscreen-dialog-title">文件预览 - {{ getFileName(linkSelectedFilePath || '') || '当前文件' }}</span>
        </div>
      </template>

      <div class="fullscreen-preview-wrapper">
        <VuePdfEmbed
          v-if="linkPreviewUrl"
          :source="linkPreviewUrl"
          class="pdf-preview-embed fullscreen-pdf-preview"
          @rendering-failed="handleLinkPreviewFailed"
        />
        <div v-else class="preview-placeholder fullscreen-preview-placeholder">{{ linkPreviewMessage || '暂无可预览内容' }}</div>
      </div>

      <template #footer>
        <el-button @click="linkFullPreviewVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, nextTick, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Icon } from '@iconify/vue'
import VuePdfEmbed from 'vue-pdf-embed'
import fileTypeWord from '@iconify-icons/vscode-icons/file-type-word'
import fileTypeExcel from '@iconify-icons/vscode-icons/file-type-excel'
import fileTypePdf from '@iconify-icons/vscode-icons/file-type-pdf2'
import microsoftOffice from '@iconify-icons/simple-icons/microsoftoffice'
import { Document, Upload } from '@element-plus/icons-vue'
import { GlobalWorkerOptions } from 'pdfjs-dist/legacy/build/pdf.mjs'
import PdfWorker from 'pdfjs-dist/legacy/build/pdf.worker.min.mjs?url'

import http from '../api/http'

GlobalWorkerOptions.workerSrc = PdfWorker

const props = defineProps({
  departments: {
    type: Array,
    default: () => [],
  },
  options: {
    type: Object,
    default: () => ({}),
  },
  linkTreeSnapshot: {
    type: Object,
    default: () => ({}),
  },
  aiParsing: {
    type: Boolean,
    default: false,
  },
  showFileActions: {
    type: Boolean,
    default: true,
  },
})

const emit = defineEmits(['saved', 'update:aiParsing'])

const aiParsing = computed(() => props.aiParsing)
const departments = computed(() => props.departments || [])

const normalizedOptions = computed(() => ({
  contract_determination_method: props.options?.contract_determination_method || [],
  contract_type: props.options?.contract_type || [],
  purchase_type: props.options?.purchase_type || [],
  stamp_tax_rate_by_contract_type: props.options?.stamp_tax_rate_by_contract_type || {},
  pricing_method: props.options?.pricing_method || [],
  is_archived: props.options?.is_archived || [],
  project: props.options?.project || [],
}))

const getStampTaxRateByContractType = (contractType) => {
  const mapping = normalizedOptions.value.stamp_tax_rate_by_contract_type || {}
  const key = String(contractType || '').trim()
  return key ? String(mapping[key] || '').trim() : ''
}

const dialogVisible = ref(false)
const textDialogVisible = ref(false)
const fullPreviewVisible = ref(false)
const linkFullPreviewVisible = ref(false)
const linkFileDialogVisible = ref(false)
const linkTreeLoading = ref(false)
const linkFilesLoading = ref(false)
const linkTreeRef = ref(null)
const linkTreeData = ref([])
const linkRootName = ref('/')
const linkTreeCache = reactive({})
const linkSelectedFolderPath = ref('')
const linkSelectedFilePath = ref('')
const linkFiles = ref([])
const linkPreviewUrl = ref('')
const linkPreviewLoading = ref(false)
const linkPreviewMessage = ref('请选择PDF文件进行预览')

const saving = ref(false)
const editing = ref(null)
const currentPreviewRow = ref(null)
const pendingAiUploadFile = ref(null)
const previewUrl = ref('')
const previewLoading = ref(false)
const previewMessage = ref('暂无文件')
const previewFileName = ref('')

const linkTreeProps = {
  label: 'name',
  children: 'children',
}

const form = reactive({
  file_path: '',
  contract_name: '',
  contract_number: '',
  contract_unit: '',
  contract_amount: '',
  copy_count: '',
  handler: '',
  handling_department: '',
  contract_determination_method: '',
  handling_date: '',
  contract_type: '',
  purchase_type: '',
  stamp_tax_rate: '',
  pricing_method: '',
  is_archived: '未归档',
  project: '',
  save_place: '',
  fullbody: '',
})

const fullPreviewTitle = computed(() => {
  if (previewFileName.value) {
    return `文件预览 - ${previewFileName.value}`
  }

  const name = getFileName(currentPreviewRow.value?.file_path || '')
  return name ? `文件预览 - ${name}` : '文件预览'
})

const resetForm = () => {
  form.file_path = ''
  form.contract_name = ''
  form.contract_number = ''
  form.contract_unit = ''
  form.contract_amount = ''
  form.copy_count = ''
  form.handler = ''
  form.handling_department = ''
  form.contract_determination_method = ''
  form.handling_date = ''
  form.contract_type = ''
  form.purchase_type = ''
  form.stamp_tax_rate = ''
  form.pricing_method = ''
  form.is_archived = '未归档'
  form.project = ''
  form.save_place = ''
  form.fullbody = ''
}

const setAiParsing = (value) => {
  emit('update:aiParsing', value)
}

const loadContractDetail = async (contractId) => {
  const { data } = await http.get(`/contracts/${contractId}`)
  return data
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
  form.contract_amount = normalizeAmountInputValue(row.contract_amount)
  form.copy_count = normalizeCopyCountInput(row.copy_count)
  form.handler = row.handler || ''
  form.handling_department = row.handling_department || row.department || ''
  form.contract_determination_method = row.contract_determination_method || ''
  form.handling_date = row.handling_date || ''
  form.contract_type = row.contract_type || ''
  form.purchase_type = row.purchase_type || ''
  form.stamp_tax_rate = row.stamp_tax_rate || getStampTaxRateByContractType(row.contract_type)
  form.pricing_method = row.pricing_method || ''
  form.is_archived = row.is_archived || '未归档'
  form.project = row.project || ''
  form.save_place = row.save_place || ''
  form.fullbody = row.fullbody || ''
}

const applyAiSupplementalFields = (fields, sourceRow = {}) => {
  const mapping = [
    ['contract_name', 'contract_name'],
    ['contract_number', 'contract_number'],
    ['contract_unit', 'contract_unit'],
    ['contract_amount', 'contract_amount'],
    ['copy_count', 'copy_count'],
    ['handler', 'handler'],
    ['handling_department', 'handling_department'],
    ['contract_determination_method', 'contract_determination_method'],
    ['handling_date', 'handling_date'],
    ['contract_type', 'contract_type'],
    ['purchase_type', 'purchase_type'],
    ['stamp_tax_rate', 'stamp_tax_rate'],
    ['pricing_method', 'pricing_method'],
    ['is_archived', 'is_archived'],
    ['project', 'project'],
    ['save_place', 'save_place'],
    ['fullbody', 'fullbody'],
  ]

  for (const [formKey, fieldKey] of mapping) {
    const incomingRaw = fields?.[fieldKey]
    const incomingValue = formKey === 'contract_amount'
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

const applyParsedFields = (fields) => {
  form.contract_name = fields?.contract_name || ''
  form.contract_number = fields?.contract_number || ''
  form.contract_unit = fields?.contract_unit || ''
  form.contract_amount = normalizeAmountInputValue(fields?.contract_amount || '')
  form.copy_count = normalizeCopyCountInput(fields?.copy_count || '')
  form.handler = fields?.handler || ''
  form.handling_department = fields?.handling_department || ''
  form.contract_determination_method = fields?.contract_determination_method || ''
  form.handling_date = fields?.handling_date || ''
  form.contract_type = fields?.contract_type || ''
  form.purchase_type = fields?.purchase_type || ''
  form.stamp_tax_rate = fields?.stamp_tax_rate || getStampTaxRateByContractType(fields?.contract_type)
  form.pricing_method = fields?.pricing_method || ''
  form.is_archived = fields?.is_archived || '未归档'
  form.project = fields?.project || ''
  form.save_place = fields?.save_place || ''
  form.fullbody = fields?.fullbody || ''
}

const openCreateFromAi = (file, fields) => {
  editing.value = null
  pendingAiUploadFile.value = file
  currentPreviewRow.value = null
  previewFileName.value = file?.name || ''
  resetForm()
  form.file_path = file?.name || ''
  applyParsedFields(fields || {})
  setPreviewFromFile(file)
  dialogVisible.value = true
}

const openCreateWithFilePath = async (filePath, fields) => {
  editing.value = null
  pendingAiUploadFile.value = null
  currentPreviewRow.value = null
  previewFileName.value = getFileName(filePath || '')
  resetForm()
  applyParsedFields(fields || {})
  form.file_path = String(filePath || '').trim()
  dialogVisible.value = true

  if (form.file_path) {
    await syncMainPreviewFromLinkedFile(form.file_path)
  } else {
    resetPreview('暂无文件')
  }
}

const openEditWithSupplementalFields = async (row, fields) => {
  const detail = row?.id ? await loadContractDetail(row.id) : row
  editing.value = detail
  currentPreviewRow.value = detail
  previewFileName.value = ''
  pendingAiUploadFile.value = null
  populateFormFromContract(detail)
  applyAiSupplementalFields(fields || {}, detail)
  await loadPdfPreviewForRow(detail)
  dialogVisible.value = true
}

const openEdit = (row) => openEditWithSupplementalFields(row, null)

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
  form.contract_amount = normalizeAmountInputValue(form.contract_amount)
}

const normalizeCopyCountInput = (value) => {
  const raw = String(value ?? '').trim()
  if (!raw) {
    return ''
  }
  return raw.replace(/\D+/g, '')
}

const normalizeCopyCount = () => {
  form.copy_count = normalizeCopyCountInput(form.copy_count)
}

const unbindContract = async () => {
  if (!editing.value?.id) {
    ElMessage.warning('仅已存在的合同支持解绑')
    return
  }

  saving.value = true
  try {
    await http.put(`/contracts/${editing.value.id}`, {
      file_path: '',
    })

    form.file_path = ''
    if (editing.value) {
      editing.value.file_path = null
    }
    if (currentPreviewRow.value?.id === editing.value.id) {
      currentPreviewRow.value.file_path = null
    }

    pendingAiUploadFile.value = null
    resetPreview('暂无文件')
    dialogVisible.value = false
    ElMessage.success('解绑成功')
    emit('saved')
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || '解绑失败')
  } finally {
    saving.value = false
  }
}

const saveContract = async () => {
  const normalizedAmount = normalizeAmountInputValue(form.contract_amount)
  const normalizedCopyCount = normalizeCopyCountInput(form.copy_count)
  const normalizedSavePlace = String(form.save_place || '').trim()

  if (!form.contract_name || !form.handling_department) {
    ElMessage.warning('请填写必要字段')
    return
  }

  if (normalizedAmount && !/^\d+(?:\.\d+)?$/.test(normalizedAmount)) {
    ElMessage.warning('合同金额请输入纯数字，可带小数点')
    return
  }

  if (normalizedCopyCount && !/^\d+$/.test(normalizedCopyCount)) {
    ElMessage.warning('份数请输入纯数字')
    return
  }

  if (normalizedSavePlace.length > 50) {
    ElMessage.warning('存档位置最多50个字符')
    return
  }

  form.contract_amount = normalizedAmount
  form.copy_count = normalizedCopyCount
  form.save_place = normalizedSavePlace

  if (!props.departments.includes(form.handling_department)) {
    ElMessage.warning('请选择系统设置中的有效部门')
    return
  }

  if (form.project && !normalizedOptions.value.project.includes(form.project)) {
    ElMessage.warning('请选择项目设置中的有效项目')
    return
  }

  saving.value = true
  try {
    if (editing.value) {
      await http.put(`/contracts/${editing.value.id}`, {
        file_path: form.file_path,
        contract_number: form.contract_number,
        contract_name: form.contract_name,
        contract_unit: form.contract_unit,
        contract_amount: normalizedAmount,
        copy_count: normalizedCopyCount,
        handler: form.handler,
        handling_department: form.handling_department,
        contract_determination_method: form.contract_determination_method,
        handling_date: form.handling_date,
        contract_type: form.contract_type,
        purchase_type: form.purchase_type,
        stamp_tax_rate: form.stamp_tax_rate,
        pricing_method: form.pricing_method,
        is_archived: form.is_archived,
        project: form.project,
        save_place: normalizedSavePlace,
        fullbody: form.fullbody,
      })
      ElMessage.success('更新成功')
    } else {
      const { data: created } = await http.post('/contracts', {
        file_path: form.file_path,
        contract_number: form.contract_number,
        contract_name: form.contract_name,
        contract_unit: form.contract_unit,
        contract_amount: normalizedAmount,
        copy_count: normalizedCopyCount,
        handler: form.handler,
        handling_department: form.handling_department,
        contract_determination_method: form.contract_determination_method,
        handling_date: form.handling_date,
        contract_type: form.contract_type,
        purchase_type: form.purchase_type,
        stamp_tax_rate: form.stamp_tax_rate,
        pricing_method: form.pricing_method,
        is_archived: form.is_archived,
        project: form.project,
        save_place: normalizedSavePlace,
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
    emit('saved')
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

watch(
  () => form.contract_type,
  (value, oldValue) => {
    if (value === oldValue) {
      return
    }
    form.stamp_tax_rate = getStampTaxRateByContractType(value)
  },
)

const doUpload = async (contractId, file) => {
  const fd = new FormData()
  fd.append('file', file)
  const { data } = await http.post(`/contracts/${contractId}/upload`, fd, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
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

  try {
    const data = await doUpload(editing.value.id, file)
    await syncEditingFileState(data?.file_path)
    ElMessage.success('上传成功')
    emit('saved')
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || '上传失败')
  }
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

const normalizePath = (value) => String(value || '').replace(/\\/g, '/').replace(/^\/+|\/+$/g, '')

const resetLinkTreeCache = () => {
  for (const key of Object.keys(linkTreeCache)) {
    delete linkTreeCache[key]
  }
}

const setCachedChildren = (parentPath, children) => {
  linkTreeCache[normalizePath(parentPath)] = Array.isArray(children) ? children : []
}

const getCachedChildren = (parentPath) => {
  const value = linkTreeCache[normalizePath(parentPath)]
  return Array.isArray(value) ? value : null
}

const applyLinkTreeSnapshot = (snapshot = {}) => {
  const root = snapshot?.root || {}
  linkRootName.value = root?.name || '/'

  resetLinkTreeCache()
  const childrenByParent = snapshot?.childrenByParent
  if (childrenByParent && typeof childrenByParent === 'object') {
    Object.entries(childrenByParent).forEach(([parentPath, children]) => {
      if (Array.isArray(children)) {
        setCachedChildren(parentPath, children)
      }
    })
  }

  const rootChildren = Array.isArray(snapshot?.rootChildren)
    ? snapshot.rootChildren
    : (getCachedChildren('') || [])
  setCachedChildren('', rootChildren)
  linkTreeData.value = rootChildren
}

const fetchLinkFolderChildren = async (parentPath = '', options = {}) => {
  const normalizedParentPath = normalizePath(parentPath)
  const force = !!options?.force

  if (!force) {
    const cached = getCachedChildren(normalizedParentPath)
    if (cached) {
      return cached
    }
  }

  const { data } = await http.get('/folders/children', {
    params: { parent_path: normalizedParentPath },
  })
  const children = Array.isArray(data?.children) ? data.children : []
  setCachedChildren(normalizedParentPath, children)
  return children
}

const buildPathChain = (path) => {
  const normalized = normalizePath(path)
  if (!normalized) {
    return []
  }

  const parts = normalized.split('/').filter(Boolean)
  const chain = []
  let current = ''
  for (const part of parts) {
    current = current ? `${current}/${part}` : part
    chain.push(current)
  }
  return chain
}

const expandLinkTreeToPath = async (path) => {
  const targetPath = normalizePath(path)
  const tree = linkTreeRef.value
  if (!tree || !targetPath) {
    tree?.setCurrentKey?.(null)
    return
  }

  const chain = buildPathChain(targetPath)
  let parentPath = ''
  for (const currentPath of chain) {
    const children = await fetchLinkFolderChildren(parentPath)
    if (!parentPath) {
      linkTreeData.value = children
    } else {
      tree.updateKeyChildren(parentPath, children)
    }
    parentPath = currentPath
  }

  await nextTick()
  for (const currentPath of chain) {
    tree.getNode(currentPath)?.expand?.()
  }
  tree.setCurrentKey?.(targetPath)
}

const loadLinkTreeChildren = async (node, resolve) => {
  const parentPath = node?.level === 0 ? '' : (node?.data?.path || '')
  try {
    resolve(await fetchLinkFolderChildren(parentPath))
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || '读取子目录失败')
    resolve([])
  }
}

const refreshLinkTreeNodeChildren = async (parentPath = '', silent = true) => {
  const normalizedParentPath = normalizePath(parentPath)
  try {
    const children = await fetchLinkFolderChildren(normalizedParentPath, { force: true })
    if (!normalizedParentPath) {
      linkTreeData.value = children
      return
    }
    linkTreeRef.value?.updateKeyChildren?.(normalizedParentPath, children)
  } catch (error) {
    if (!silent) {
      ElMessage.error(error?.response?.data?.message || '读取子目录失败')
    }
  }
}

const loadLinkFiles = async (folderPath = '') => {
  linkFilesLoading.value = true
  try {
    const { data } = await http.get('/folders/files', {
      params: { folder_path: normalizePath(folderPath) },
    })
    linkSelectedFolderPath.value = data?.folder_path || ''
    const rows = Array.isArray(data?.files) ? data.files : []
    linkFiles.value = rows
    if (!rows.some((row) => row.file_path === linkSelectedFilePath.value)) {
      linkSelectedFilePath.value = ''
    }
  } catch (error) {
    linkFiles.value = []
    ElMessage.error(error?.response?.data?.message || '读取文件失败')
  } finally {
    linkFilesLoading.value = false
  }
}

const getParentPath = (value) => {
  const path = normalizePath(value)
  if (!path) {
    return ''
  }
  const idx = path.lastIndexOf('/')
  return idx >= 0 ? path.slice(0, idx) : ''
}

const openLinkFileDialog = async () => {
  linkFileDialogVisible.value = true
  linkTreeLoading.value = true
  linkSelectedFilePath.value = form.file_path || ''
  cleanupLinkPreview()
  try {
    applyLinkTreeSnapshot(props.linkTreeSnapshot || {})
    if (!linkTreeData.value.length) {
      const { data } = await http.get('/folders/tree')
      const root = data?.root || { name: '/', path: '' }
      linkRootName.value = root?.name || '/'
      linkTreeData.value = await fetchLinkFolderChildren('', { force: true })
    }

    const initialFolder = normalizePath(getParentPath(form.file_path || ''))
    await expandLinkTreeToPath(initialFolder)
    await loadLinkFiles(initialFolder)
  } catch (error) {
    linkTreeData.value = []
    linkFiles.value = []
    ElMessage.error(error?.response?.data?.message || '加载文件选择器失败')
  } finally {
    linkTreeLoading.value = false
  }
}

const onLinkTreeNodeClick = async (node) => {
  const folderPath = node?.path || ''
  const normalizedFolderPath = normalizePath(folderPath)
  const cachedChildren = getCachedChildren(normalizedFolderPath)
  if (cachedChildren) {
    linkTreeRef.value?.updateKeyChildren?.(normalizedFolderPath, cachedChildren)
  }
  refreshLinkTreeNodeChildren(normalizedFolderPath)

  await loadLinkFiles(folderPath)
}

const cleanupLinkPreview = () => {
  if (linkPreviewUrl.value) {
    window.URL.revokeObjectURL(linkPreviewUrl.value)
  }
  linkPreviewUrl.value = ''
  linkPreviewMessage.value = '请选择PDF文件进行预览'
  linkPreviewLoading.value = false
}

const openLinkFilePreview = async (filePath) => {
  const targetPath = String(filePath || '').trim()
  if (!targetPath) {
    return
  }
  if (getFileExt(targetPath) !== 'pdf') {
    cleanupLinkPreview()
    linkPreviewMessage.value = '该文件不是PDF，无法预览'
    return
  }

  linkPreviewLoading.value = true
  linkPreviewMessage.value = ''
  try {
    const response = await http.get('/folders/file-preview', {
      params: { path: targetPath },
      responseType: 'blob',
    })
    if (linkPreviewUrl.value) {
      window.URL.revokeObjectURL(linkPreviewUrl.value)
    }
    linkPreviewUrl.value = window.URL.createObjectURL(response.data)
  } catch (error) {
    const message = await parseErrorMessage(error, '文件预览加载失败')
    cleanupLinkPreview()
    linkPreviewMessage.value = `文件预览加载失败：${message}`
    ElMessage.warning(message)
  } finally {
    linkPreviewLoading.value = false
  }
}

const syncMainPreviewFromLinkedFile = async (filePath) => {
  const targetPath = String(filePath || '').trim()
  if (!targetPath) {
    previewFileName.value = ''
    resetPreview('暂无文件', false)
    return
  }

  previewFileName.value = getFileName(targetPath)

  if (editing.value?.id) {
    if (currentPreviewRow.value?.id === editing.value.id) {
      currentPreviewRow.value.file_path = targetPath
    } else {
      currentPreviewRow.value = {
        ...(currentPreviewRow.value || {}),
        id: editing.value.id,
        file_path: targetPath,
      }
    }
  }

  if (getFileExt(targetPath) !== 'pdf') {
    resetPreview('该文件不是PDF，无法预览，请使用下方按钮下载原文件', false)
    return
  }

  previewLoading.value = true
  previewMessage.value = ''
  try {
    const response = await http.get('/folders/file-preview', {
      params: { path: targetPath },
      responseType: 'blob',
    })
    setPreviewFromBlob(response.data)
  } catch (error) {
    const message = await parseErrorMessage(error, 'PDF预览加载失败')
    resetPreview(`PDF预览加载失败：${message}`, false)
    ElMessage.warning(message)
  } finally {
    previewLoading.value = false
  }
}

const handleLinkFileRowClick = async (row) => {
  if (!row?.file_path) {
    return
  }
  linkSelectedFilePath.value = row.file_path
  await openLinkFilePreview(row.file_path)
}

const openLinkFullscreenPreview = () => {
  if (!linkPreviewUrl.value || linkPreviewLoading.value) {
    return
  }
  linkFullPreviewVisible.value = true
}

const confirmLinkFile = async () => {
  const selectedPath = linkSelectedFilePath.value || ''
  if (!selectedPath) {
    ElMessage.warning('请选择一个文件')
    return
  }

  form.file_path = selectedPath
  if (editing.value) {
    editing.value.file_path = selectedPath
  }
  if (currentPreviewRow.value?.id === editing.value?.id) {
    currentPreviewRow.value.file_path = selectedPath
  }

  await syncMainPreviewFromLinkedFile(selectedPath)
  ElMessage.success('已选择文件，点击“保存”后生效')
  closeLinkFileDialog()
}

const closeLinkFileDialog = () => {
  linkFileDialogVisible.value = false
  cleanupLinkPreview()
}

const runAiRecognitionFromPreview = async () => {
  if (props.aiParsing) {
    return
  }

  ElMessage({
    type: 'info',
    message: 'AI识别结果只会自动填写空白的字段',
    duration: 5000,
  })

  const existingFullbody = String(form.fullbody || '').trim()
  if (existingFullbody.length > 20) {
    setAiParsing(true)
    ElMessage.info('检测到已有合同文本，跳过OCR，直接进行AI结构化解析')
    try {
      const { data } = await http.post('/contracts/ai-parse', {
        fullbody: existingFullbody,
      }, {
        timeout: 300000,
      })

      const parsedFullbody = data?.fullbody || existingFullbody
      const parsedFields = {
        ...(data?.fields || {}),
        fullbody: parsedFullbody,
      }

      const sourceSnapshot = {
        ...(editing.value || {}),
        ...form,
      }

      applyAiSupplementalFields(parsedFields, sourceSnapshot)
      ElMessage.success('AI解析成功，合同信息已根据识别结果更新')
      return
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
      return
    } finally {
      setAiParsing(false)
    }
  }

  let sourceFile = null
  let fileName = ''

  if (pendingAiUploadFile.value) {
    sourceFile = pendingAiUploadFile.value
    fileName = sourceFile.name || 'contract.pdf'
  } else if (form.file_path) {
    try {
      if (editing.value?.id) {
        const response = await http.get(`/contracts/${editing.value.id}/download`, {
          responseType: 'blob',
        })
        const blob = response.data
        fileName = getFileName(form.file_path) || `contract-${editing.value.id}.pdf`
        sourceFile = new File([blob], fileName, { type: blob.type || 'application/pdf' })
      } else {
        const response = await http.get('/folders/file-preview', {
          params: { path: normalizePath(form.file_path) },
          responseType: 'blob',
        })
        const blob = response.data
        fileName = getFileName(form.file_path) || 'contract.pdf'
        sourceFile = new File([blob], fileName, { type: blob.type || 'application/pdf' })
      }
    } catch (error) {
      const message = await parseErrorMessage(error, '获取文件内容失败，无法进行AI识别')
      ElMessage.error(message)
      return
    }
  } else {
    ElMessage.warning('请先上传或链接合同文件后再进行AI识别')
    return
  }

  if (!/\.pdf$/i.test(fileName)) {
    ElMessage.warning('当前文件不是PDF，无法进行AI识别')
    return
  }

  setAiParsing(true)
  ElMessage.info('AI正在解析当前合同，请稍候')
  try {
    const fd = new FormData()
    fd.append('file', sourceFile)

    const { data } = await http.post('/contracts/ai-parse', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 300000,
    })

    const parsedFullbody = data?.fullbody || ''
    const parsedFields = {
      ...(data?.fields || {}),
      fullbody: parsedFullbody,
    }

    const sourceSnapshot = {
      ...(editing.value || {}),
      ...form,
    }

    applyAiSupplementalFields(parsedFields, sourceSnapshot)
    ElMessage.success('AI解析成功，合同信息已根据识别结果更新')
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
    setAiParsing(false)
  }
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

const handleDialogFilePathDownload = async () => {
  if (!form.file_path) {
    ElMessage.warning('暂无可下载文件')
    return
  }

  const contractId = editing.value?.id || currentPreviewRow.value?.id
  if (!contractId) {
    ElMessage.warning('请先保存合同后再下载文件')
    return
  }

  await downloadContractFile({
    id: contractId,
    file_path: form.file_path,
    contract_name: form.contract_name,
  })
}

const handleLinkPreviewFailed = () => {
  linkPreviewMessage.value = 'PDF组件渲染失败，请检查文件内容或浏览器兼容性'
}

const handleContractDeleted = (contractId) => {
  if (editing.value?.id === contractId) {
    dialogVisible.value = false
    textDialogVisible.value = false
    editing.value = null
    pendingAiUploadFile.value = null
    resetForm()
  }

  if (currentPreviewRow.value?.id === contractId) {
    currentPreviewRow.value = null
    previewFileName.value = ''
    resetPreview('暂无文件')
  }
}

watch(dialogVisible, (visible) => {
  if (!visible) {
    resetPreview('暂无文件')
  }
})

watch(linkFileDialogVisible, (visible) => {
  if (!visible) {
    cleanupLinkPreview()
  }
})

watch(
  () => props.linkTreeSnapshot,
  (snapshot) => {
    applyLinkTreeSnapshot(snapshot || {})
  },
  { immediate: true, deep: true },
)

defineExpose({
  openCreate,
  openCreateFromAi,
  openCreateWithFilePath,
  openEdit,
  openEditWithSupplementalFields,
  openFilePreview,
  handleContractDeleted,
})
</script>

<style>
.link-file-dialog {
  height: 90vh;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
}
</style>

<style scoped>
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

.preview-actions {
  display: flex;
  gap: 8px;
}

.readonly-file-path {
  width: 100%;
  min-height: 32px;
  display: flex;
  align-items: center;
  padding: 6px 10px;
  border-radius: 6px;
  border: 1px solid #e5e7eb;
  background: #f9fafb;
  color: #4b5563;
  font-size: 7px !important;
  line-height: 1.4;
  word-break: break-all;
}

.readonly-file-link {
  width: 100%;
  justify-content: flex-start;
  font-size: 12px;
  line-height: 1.4;
  word-break: break-all;
  white-space: normal;
}

.file-cell {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  max-width: 100%;
}

.file-name {
  display: inline-block;
  flex-grow: 1;
  overflow: hidden;
  white-space: nowrap;
  color: #374151;
  margin-left: 4px;
}

.file-ok {
  width: 18px;
  height: 18px;
  font-size: 18px;
  flex-shrink: 0;
}

.panel-title {
  margin-bottom: 8px;
  font-size: 14px;
  font-weight: 600;
  color: #374151;
}

.link-file-dialog :deep(.el-dialog__body) {
  flex: 1;
  min-height: 0;
  overflow: hidden;
  padding-top: 10px;
  padding-bottom: 8px;
}

.link-file-layout {
  display: grid;
  grid-template-columns: 320px minmax(0, 1fr) 320px;
  gap: 12px;
  height: 100%;
  min-height: 0;
}

.link-file-left,
.link-file-right {
  border: 1px solid #ebeef5;
  border-radius: 8px;
  padding: 10px;
  background: #fff;
  height: calc(90vh - 118px);
  max-width: 100vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.link-file-left :deep(.el-tree) {
  flex: 1;
  min-height: 0;
  overflow: auto;
}

.link-file-table-wrap {
  flex: 1;
  min-height: 0;
  overflow: auto;
}

.link-file-table {
  height: 100%;
}

.link-file-preview-panel {
  margin-top: 12px;
  min-height: 320px;
  max-height: 480px;
  overflow: auto;
  border: 1px solid #eee;
  border-radius: 4px;
  background: #fafbfc;
  display: flex;
  align-items: center;
  justify-content: center;
}

.link-preview-embed {
  width: 100%;
  height: 400px;
}

.tree-node-content {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}

.tree-node-label {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
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
</style>