<template>
  <el-dialog v-model="visible" title="识别结果确认" width="min(1080px, 96vw)">
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
        <div v-if="loading" class="ai-match-loading-panel">
          <el-icon class="ai-match-loading-icon is-loading"><Loading /></el-icon>
          <div class="ai-match-loading-text">加载中...</div>
        </div>

        <template v-else>
        <div class="ai-match-summary">
          <div class="ai-match-title">AI 已完成解析，请先确认这是新合同还是已有合同。</div>
          <div class="ai-match-subtitle">系统已按合同标题相似度和金额相同规则筛出候选合同。</div>
        </div>

        <el-table
          :data="candidates"
          stripe
          border
          resizable
          size="small"
          class="ai-match-table"
          empty-text="未找到相似合同，可直接选择“这是新合同”"
          @row-click="handleRowClick"
        >
          <el-table-column label="选择" width="74" align="center">
            <template #default="scope">
              <input
                class="ai-match-radio"
                type="radio"
                name="ai-match-selection"
                :checked="selection === String(scope.row.id)"
                @change="selectCandidate(scope.row.id)"
              />
            </template>
          </el-table-column>
          <el-table-column label="文件" min-width="240">
            <template #default="scope">
              <el-link v-if="scope.row.file_path" class="file-cell" @click.stop>
                <Icon :icon="getFileIcon(scope.row.file_path)" class="file-ok file-download" />
                <span class="file-name" :title="getFileName(scope.row.file_path)">
                  {{ getFileName(scope.row.file_path) }}
                </span>
              </el-link>
              <span v-else class="no-file-name">未上传</span>
            </template>
          </el-table-column>
          <el-table-column prop="contract_name" label="合同名称" min-width="280" show-overflow-tooltip />
          <el-table-column prop="contract_amount" label="金额" min-width="130" />
          <el-table-column label="匹配依据" min-width="160">
            <template #default="scope">
              {{ formatReasons(scope.row) }}
            </template>
          </el-table-column>
        </el-table>

        <label class="ai-match-new-option" @click="selectAsNew">
          <input
            class="ai-match-radio"
            type="radio"
            name="ai-match-selection"
            :checked="selection === AI_NEW_CONTRACT_VALUE"
            @change="selectAsNew"
          />
          <span>这是新合同</span>
        </label>
        </template>
      </div>
    </div>

    <template #footer>
      <el-button @click="handleCancel">取消</el-button>
      <el-button type="primary" :loading="processing" :disabled="loading" @click="handleConfirm">下一步</el-button>
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
        <span class="fullscreen-dialog-title">文件预览 - {{ file?.name || '当前文件' }}</span>
      </div>
    </template>

    <div class="fullscreen-preview-wrapper">
      <VuePdfEmbed
        v-if="previewUrl"
        :source="previewUrl"
        class="pdf-preview-embed fullscreen-pdf-preview"
        @rendering-failed="handlePdfRenderFailed"
      />
      <div v-else class="preview-placeholder fullscreen-preview-placeholder">{{ previewMessage || '暂无可预览内容' }}</div>
    </div>

    <template #footer>
      <el-button @click="fullPreviewVisible = false">关闭</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { Icon } from '@iconify/vue'
import VuePdfEmbed from 'vue-pdf-embed'
import { Loading } from '@element-plus/icons-vue'
import fileTypeWord from '@iconify-icons/vscode-icons/file-type-word'
import fileTypeExcel from '@iconify-icons/vscode-icons/file-type-excel'
import fileTypePdf from '@iconify-icons/vscode-icons/file-type-pdf2'
import microsoftOffice from '@iconify-icons/simple-icons/microsoftoffice'

const AI_NEW_CONTRACT_VALUE = '__new_contract__'

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false,
  },
  candidates: {
    type: Array,
    default: () => [],
  },
  loading: {
    type: Boolean,
    default: false,
  },
  processing: {
    type: Boolean,
    default: false,
  },
  file: {
    type: Object,
    default: null,
  },
  previewUrl: {
    type: String,
    default: '',
  },
})

const emit = defineEmits(['update:modelValue', 'confirm-selection', 'cancel'])

const visible = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value),
})

const selection = ref(AI_NEW_CONTRACT_VALUE)
const previewUrl = ref('')
const previewLoading = ref(false)
const previewMessage = ref('暂无文件')
const fullPreviewVisible = ref(false)
const ownsPreviewUrl = ref(false)

const cleanupPreview = () => {
  if (previewUrl.value && ownsPreviewUrl.value) {
    window.URL.revokeObjectURL(previewUrl.value)
  }
  previewUrl.value = ''
  ownsPreviewUrl.value = false
}

const loadPreviewFromFile = () => {
  cleanupPreview()

  const externalPreviewUrl = String(props.previewUrl || '').trim()
  if (externalPreviewUrl) {
    previewUrl.value = externalPreviewUrl
    previewMessage.value = ''
    previewLoading.value = false
    ownsPreviewUrl.value = false
    return
  }

  if (!props.file) {
    previewMessage.value = '暂无文件'
    return
  }

  const name = String(props.file?.name || '')
  if (!/\.pdf$/i.test(name)) {
    previewMessage.value = '该文件不是PDF，无法预览'
    return
  }

  previewLoading.value = true
  previewMessage.value = ''
  try {
    previewUrl.value = window.URL.createObjectURL(props.file)
    ownsPreviewUrl.value = true
  } finally {
    previewLoading.value = false
  }
}

watch(() => props.modelValue, (visibleNow) => {
  if (visibleNow) {
    selection.value = AI_NEW_CONTRACT_VALUE
    loadPreviewFromFile()
  } else {
    fullPreviewVisible.value = false
    cleanupPreview()
  }
})

watch(() => props.file, () => {
  if (props.modelValue) {
    loadPreviewFromFile()
  }
})

watch(() => props.previewUrl, () => {
  if (props.modelValue) {
    loadPreviewFromFile()
  }
})

onBeforeUnmount(() => {
  cleanupPreview()
})

const selectCandidate = (contractId) => {
  selection.value = String(contractId)
}

const selectAsNew = () => {
  selection.value = AI_NEW_CONTRACT_VALUE
}

const handleRowClick = (row) => {
  if (row?.id) {
    selectCandidate(row.id)
  }
}

const formatReasons = (row) => {
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

const openFullscreenPreview = () => {
  if (!previewUrl.value || previewLoading.value) {
    return
  }
  fullPreviewVisible.value = true
}

const handlePdfRenderFailed = () => {
  previewMessage.value = 'PDF组件渲染失败，请检查文件内容或浏览器兼容性'
}

const handleCancel = () => {
  emit('cancel')
}

const handleConfirm = () => {
  if (props.loading) {
    return
  }
  emit('confirm-selection', selection.value)
}
</script>

<style scoped>
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

.preview-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
}

.preview-title {
  font-size: 14px;
  font-weight: 600;
  color: #374151;
}

.preview-panel {
  height: min(62vh, 720px);
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

.ai-match-content {
  display: grid;
  gap: 12px;
}

.ai-match-loading-panel {
  min-height: 320px;
  display: grid;
  place-items: center;
  align-content: center;
  gap: 12px;
}

.ai-match-loading-icon {
  font-size: 28px;
  color: #2563eb;
}

.ai-match-loading-text {
  font-size: 14px;
  color: #6b7280;
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

.file-cell {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  max-width: 100%;
}

.file-name {
  display: inline-block;
  max-width: 170px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: #374151;
}

.no-file-name {
  color: #9ca3af;
  font-size: 14px;
}

.file-ok {
  width: 18px;
  height: 18px;
  font-size: 18px;
}

.file-download {
  cursor: pointer;
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

@media (max-width: 1100px) {
  .ai-match-dialog {
    grid-template-columns: 1fr;
  }

  .ai-match-preview-column .preview-panel {
    height: min(48vh, 520px);
  }
}
</style>