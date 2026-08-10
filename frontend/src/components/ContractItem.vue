<template>
  <div>
    <el-dialog
      v-model="dialogVisible"
      :title="editing ? '编辑合同' : '新建合同'"
      width="min(1380px, 98vw)"
      top="2vh"
    >
      <div v-if="contractDialogLoading" class="contract-dialog-loading-panel">
        <el-icon class="contract-dialog-loading-icon is-loading"><Loading /></el-icon>
        <div class="contract-dialog-loading-text">加载中...</div>
      </div>

      <template v-else>
      <el-form :model="form" :disabled="contractDialogLoading || dialogReadOnly" label-width="120px" class="dialog-form">
        <div class="dialog-layout">
          <div class="preview-column">
            <div class="preview-header">
              <div class="preview-title">文件预览</div>
              <div class="preview-actions">
                <el-button-group class="preview-action-group">
                  <el-button
                    size="small"
                    :icon="Search"
                    :loading="aiParsing"
                    :disabled="dialogReadOnly || aiParsing || (!form.file_path && !pendingAiUploadFile)"
                    @click="runAiRecognitionFromPreview"
                  >
                    {{ aiParsing ? '识别中...' : 'AI识别' }}
                  </el-button>
                  <el-button v-if="false" size="small" :icon="Document" @click="textDialogVisible = true">文本</el-button>

                  <el-button
                    v-if="props.showFileActions && !dialogReadOnly"
                    :icon="Upload"
                    size="small"
                    @click="openUploadFolderDialog"
                  >
                    上传文件
                  </el-button>

                  <el-button
                    v-if="props.showFileActions && !dialogReadOnly"
                    size="small"
                    :icon="Link"
                    @click="openLinkFileDialog"
                  >
                    链接文件
                  </el-button>
                </el-button-group>
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
                <div class="status-checkbox-group">
                  <el-checkbox v-model="isArchivedChecked" label="已归档" />
                  <el-tooltip content="由系统判断，填写了所有字段，并且已识别文本。" placement="top">
                    <el-checkbox v-model="isCompletenessChecked" label="整理完毕" :disabled="!isSuperRole" />
                  </el-tooltip>
                </div>

                    <el-link
                class="ocr-md-link"
                type="primary"
                :underline="ocrMdLinkEnabled"
                :disabled="!ocrMdLinkEnabled"
                      :href="ocrMdLinkEnabled ? ocrPreviewUrl : undefined"
                target="_blank"
              >
                {{ ocrMdChecking ? 'OCR文本检测中...' : '打开OCR文本' }}
              </el-link>
              </el-form-item>

              <el-form-item label="合同名称" class="form-item-span-2" required>
                <div class="contract-name-with-flag">
                  <el-dropdown trigger="click" @command="handleColorFlagSelect">
                    <button type="button" class="flag-trigger" title="颜色标记">
                      <span class="flag-icon" :class="getColorFlagClass(form.color_flag)">⚑</span>
                    </button>
                    <template #dropdown>
                      <el-dropdown-menu class="flag-dropdown-menu">
                        <el-dropdown-item :command="''">
                          <span class="flag-icon is-none">⚑</span>
                        </el-dropdown-item>
                        <el-dropdown-item v-for="item in colorFlagOptions" :key="item" :command="item">
                          <span class="flag-icon" :class="getColorFlagClass(item)">⚑</span>
                        </el-dropdown-item>
                      </el-dropdown-menu>
                    </template>
                  </el-dropdown>
                  <el-input v-model="form.contract_name" class="contract-name-input" />
                </div>
              </el-form-item>
              <el-form-item label="合同编号" required>
                <el-input v-model="form.contract_number" />
              </el-form-item>
              <el-form-item label="合同单位" required>
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
              <el-form-item label="合同执行状态" required>
                <el-select v-model="form.contract_execution_status" placeholder="请选择合同执行状态" style="width: 100%">
                  <el-option v-for="item in normalizedOptions.contract_execution_status" :key="item" :label="item" :value="item" />
                </el-select>
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
              <el-form-item label="现管部门" required>
                <el-select
                  v-model="form.current_management_department"
                  filterable
                  allow-create
                  clearable
                  placeholder="默认为部门映射后的当前部门"
                  style="width: 100%"
                >
                  <el-option v-for="item in currentManagementDepartments" :key="item" :label="item" :value="item" />
                </el-select>
              </el-form-item>
              <el-form-item label="合同形式" required>
                <el-select v-model="form.contract_form" placeholder="请选择合同形式" style="width: 100%">
                  <el-option v-for="item in normalizedOptions.contract_form" :key="item" :label="item" :value="item" />
                </el-select>
              </el-form-item>
              <el-form-item label="原合同">
                <div class="original-contract-field">
                  <el-select v-model="form.original_contract_id" clearable filterable placeholder="请选择原合同" style="width: 100%">
                    <el-option
                      v-for="item in originalContractOptions"
                      :key="item.id"
                      :label="item.label"
                      :value="item.id"
                    />
                  </el-select>
                </div>
              </el-form-item>
              <el-form-item label="合同确定方式" required>
                <el-select v-model="form.contract_determination_method" placeholder="请选择合同确定方式" style="width: 100%">
                  <el-option v-for="item in normalizedOptions.contract_determination_method" :key="item" :label="item" :value="item" />
                </el-select>
              </el-form-item>
              <el-form-item label="承办日期">
                <el-date-picker v-model="form.handling_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
              </el-form-item>
              <el-form-item label="合同类型" required>
                <el-select v-model="form.contract_type" placeholder="请选择合同类型" style="width: 100%">
                  <el-option v-for="item in normalizedOptions.contract_type" :key="item" :label="item" :value="item" />
                </el-select>
              </el-form-item>
              <el-form-item label="采购类型" required>
                <el-select v-model="form.purchase_type" placeholder="请选择采购类型" style="width: 100%">
                  <el-option v-for="item in normalizedOptions.purchase_type" :key="item" :label="item" :value="item" />
                </el-select>
              </el-form-item>
              <el-form-item label="印花税率" required>
                <el-input v-model="form.stamp_tax_rate" placeholder="根据合同类型自动回填，可手动调整" clearable />
              </el-form-item>
              <el-form-item label="计价方式" required>
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
            <div class="contract-meta-info">
              <span>创建人：{{ form.created_by || '—' }}</span>
              <span>创建时间：{{ formatMetaDateTime(form.created_at) }}</span>
              <span>修改人：{{ form.updated_by || '—' }}</span>
              <span>修改时间：{{ formatMetaDateTime(form.updated_at) }}</span>
            </div>

            <div class="payment-flow-section">
              <div class="payment-flow-header">
                <div class="payment-flow-title">支付流水</div>
                <div class="payment-flow-count" v-if="paymentFlowRows.length">{{ paymentFlowRows.length }} 条</div>
              </div>

              <el-alert
                v-if="paymentFlowError"
                type="warning"
                :closable="false"
                show-icon
                :title="paymentFlowError"
                class="payment-flow-alert"
              />

              <div v-loading="paymentFlowLoading" class="payment-flow-table-wrap">

                <el-table
                  v-if="paymentFlowRows.length"
                  :data="paymentFlowRows"
                  size="small"
                  border
                  stripe
                  max-height="280">

                  <el-table-column prop="FPYZ_NAM" label="付款描述" min-width="180" show-overflow-tooltip />
                  <el-table-column prop="VEN_NO" label="供应商" min-width="160" show-overflow-tooltip />
                  <el-table-column prop="FKSP_STA" label="审批状态" min-width="110" />
                  <el-table-column prop="FKLX_NO" label="付款类型" min-width="110" />
                  <el-table-column prop="BCZF_AMT" label="本次支付金额" min-width="130" />
                  <el-table-column prop="YHYZF_AMT" label="已支付金额" min-width="120" />
                  <el-table-column prop="JHFK_DTM" label="计划付款日期" min-width="140" />
                  <el-table-column prop="JBUSR_ID" label="承办人" min-width="100" />
                  <el-table-column prop="JBRQ_DTM" label="承办日期" min-width="160" />
                  <el-table-column prop="CWFK_ID" label="付款审批编号" min-width="160" show-overflow-tooltip />

                </el-table>

                <el-empty v-else :description="paymentFlowLoading ? '正在加载支付流水...' : paymentFlowEmptyText" :image-size="64" />
              
              </div>

            </div>

            

            

          </div>
        </div>
      </el-form>
      </template>

      <template #footer>
        <el-button
          v-if="!props.showFileActions && !dialogReadOnly"
          type="danger"
          :loading="saving"
          :disabled="contractDialogLoading || !editing?.id"
          @click="unbindContract"
        >
          解绑合同
        </el-button>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button
          v-if="!dialogReadOnly"
          :loading="saving"
          :disabled="contractDialogLoading"
          type="primary"
          @click="saveContract"
        >
          保存
        </el-button>
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
          <div class="fullscreen-dialog-title-wrap">
            <span class="fullscreen-dialog-title">{{ fullPreviewTitle }}</span>
            <span class="fullscreen-dialog-breadcrumb" :title="fullPreviewBreadcrumb">目录：{{ fullPreviewBreadcrumb }}</span>
          </div>
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
        <div v-else-if="previewLoading" class="preview-placeholder fullscreen-preview-placeholder">预览加载中...</div>
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
        :readonly="dialogReadOnly"
        placeholder="暂无文本内容"
      />

      <template #footer>
        <el-button @click="textDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="uploadFolderDialogVisible"
      title="选择上传目录"
      width="min(760px, 96vw)"
      :close-on-click-modal="false"
    >
      <div class="upload-folder-dialog-tip">请先选择目标目录，再选择本地文件。</div>
      <div class="upload-folder-dialog-selected">当前选择：{{ uploadFolderSelectedPath || '未选择' }}</div>

      <div class="upload-folder-tree-wrap" v-loading="linkTreeLoading">
        <el-tree
          :data="linkTreeData"
          node-key="path"
          :props="linkTreeProps"
          lazy
          :load="loadLinkTreeChildren"
          :expand-on-click-node="true"
          highlight-current
          @node-click="onUploadFolderNodeClick"
        >
          <template #default="{ node, data }">
            <span class="upload-folder-tree-node" :title="normalizePath(data.path || '')">
              <span class="upload-folder-tree-icon" aria-hidden="true">{{ node.expanded ? '📂' : '📁' }}</span>
              <span class="upload-folder-tree-label">{{ data.name }}</span>
            </span>
          </template>
        </el-tree>
      </div>

      <template #footer>
        <el-button @click="uploadFolderDialogVisible = false">取消</el-button>
        <el-button type="primary" :disabled="!canConfirmUploadFolder" @click="confirmUploadFolderSelection">下一步：选择本地文件</el-button>
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
          <div class="link-left-header">
            <div class="panel-title">{{ linkRootName }}</div>
            <el-button
              v-if="!form.file_path"
              class="apple-smart-match-btn"
              size="small"
              :loading="smartMatchingFile"
              @click="runSmartMatchFile"
            >
              智能匹配文件
            </el-button>
          </div>
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
          <div class="fullscreen-dialog-title-wrap">
            <span class="fullscreen-dialog-title">文件预览 - {{ getFileName(linkSelectedFilePath || '') || '当前文件' }}</span>
            <span class="fullscreen-dialog-breadcrumb" :title="linkFullPreviewBreadcrumb">目录：{{ linkFullPreviewBreadcrumb }}</span>
          </div>
        </div>
      </template>

      <div class="fullscreen-preview-wrapper">
        <VuePdfEmbed
          v-if="linkPreviewUrl"
          :source="linkPreviewUrl"
          class="pdf-preview-embed fullscreen-pdf-preview"
          @rendering-failed="handleLinkPreviewFailed"
        />
        <div v-else-if="linkPreviewLoading" class="preview-placeholder fullscreen-preview-placeholder">预览加载中...</div>
        <div v-else class="preview-placeholder fullscreen-preview-placeholder">{{ linkPreviewMessage || '暂无可预览内容' }}</div>
      </div>

      <template #footer>
        <el-button @click="linkFullPreviewVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <input
      ref="uploadFileInputRef"
      type="file"
      style="display: none"
      @change="handleUploadFileSelected"
    />


  </div>
</template>

<script setup>
import { computed, nextTick, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Icon } from '@iconify/vue'
import VuePdfEmbed from 'vue-pdf-embed'
import fileTypeWord from '@iconify-icons/vscode-icons/file-type-word'
import fileTypeExcel from '@iconify-icons/vscode-icons/file-type-excel'
import fileTypePdf from '@iconify-icons/vscode-icons/file-type-pdf2'
import microsoftOffice from '@iconify-icons/simple-icons/microsoftoffice'
import { Document, Link, Loading, Search, Upload } from '@element-plus/icons-vue'
import { GlobalWorkerOptions } from 'pdfjs-dist/legacy/build/pdf.mjs'
import PdfWorker from 'pdfjs-dist/legacy/build/pdf.worker.min.mjs?url'

import http from '../api/http'

GlobalWorkerOptions.workerSrc = PdfWorker

const props = defineProps({
  departments: {
    type: Array,
    default: () => [],
  },
  currentManagementDepartments: {
    type: Array,
    default: () => [],
  },
  options: {
    type: Object,
    default: () => ({}),
  },
  contracts: {
    type: Array,
    default: () => [],
  },
  linkTreeSnapshot: {
    type: Object,
    default: () => ({}),
  },
  aiParsing: {
    type: Boolean,
    default: false,
  },
  currentUserRole: {
    type: String,
    default: 'admin',
  },
  showFileActions: {
    type: Boolean,
    default: true,
  },
})

const emit = defineEmits(['saved', 'update:aiParsing'])

const aiParsing = computed(() => props.aiParsing)
const departments = computed(() => props.departments || [])
const currentManagementDepartments = computed(() => {
  const source = Array.isArray(props.currentManagementDepartments)
    ? props.currentManagementDepartments
    : []
  if (source.length > 0) {
    return source
  }
  return departments.value
})

const normalizedOptions = computed(() => ({
  contract_form: props.options?.contract_form || [],
  contract_determination_method: props.options?.contract_determination_method || [],
  contract_type: props.options?.contract_type || [],
  purchase_type: props.options?.purchase_type || [],
  contract_execution_status: props.options?.contract_execution_status || [],
  stamp_tax_rate_by_contract_type: props.options?.stamp_tax_rate_by_contract_type || {},
  pricing_method: props.options?.pricing_method || [],
  is_archived: props.options?.is_archived || [],
  color_flag: props.options?.color_flag || [],
  completeness: props.options?.completeness || [],
  project: props.options?.project || [],
}))

const isSuperRole = computed(() => ['super_admin', 'synology_super_admin'].includes(String(props.currentUserRole || '').trim()))
const colorFlagOptions = computed(() => {
  const source = Array.isArray(normalizedOptions.value.color_flag) ? normalizedOptions.value.color_flag : []
  return source.length ? source : ['红旗', '橙旗', '黄旗', '绿旗', '蓝旗']
})

const isArchivedChecked = computed({
  get: () => String(form.is_archived || '').trim() === '已归档',
  set: (checked) => {
    form.is_archived = checked ? '已归档' : '未归档'
  },
})

const isCompletenessChecked = computed({
  get: () => String(form.completeness || '').trim() === '是',
  set: (checked) => {
    form.completeness = checked ? '是' : '否'
  },
})

const getColorFlagClass = (value) => {
  const text = String(value || '').trim()
  if (text === '红旗') return 'is-red'
  if (text === '橙旗') return 'is-orange'
  if (text === '黄旗') return 'is-yellow'
  if (text === '绿旗') return 'is-green'
  if (text === '蓝旗') return 'is-blue'
  return 'is-none'
}

const handleColorFlagSelect = (command) => {
  form.color_flag = String(command || '').trim()
}

const computeCompletenessValue = () => {
  const hasFile = !!String(form.file_path || '').trim()
  const hasContractNumber = !!String(form.contract_number || '').trim()
  const hasContractName = !!String(form.contract_name || '').trim()
  const hasContractUnit = !!String(form.contract_unit || '').trim()
  const hasCurrentManagementDepartment = !!String(form.current_management_department || '').trim()
  const hasContractForm = !!String(form.contract_form || '').trim()
  const hasDetermination = !!String(form.contract_determination_method || '').trim()
  const hasContractType = !!String(form.contract_type || '').trim()
  const hasPurchaseType = !!String(form.purchase_type || '').trim()
  const hasExecutionStatus = !!String(form.contract_execution_status || '').trim()
  const hasStampTaxRate = !!String(form.stamp_tax_rate || '').trim()
  const hasPricingMethod = !!String(form.pricing_method || '').trim()
  const hasOcrMarkdown = !!ocrMdLinkEnabled.value
  return hasFile
    && hasContractNumber
    && hasContractName
    && hasContractUnit
    && hasCurrentManagementDepartment
    && hasContractForm
    && hasDetermination
    && hasContractType
    && hasPurchaseType
    && hasExecutionStatus
    && hasStampTaxRate
    && hasPricingMethod
    && hasOcrMarkdown
    ? '是'
    : '否'
}

const applyCompletenessDefault = ({ force = false } = {}) => {
  form.completeness = computeCompletenessValue()
}

const collectCompletenessRequiredFieldErrors = () => {
  const errors = []

  if (!String(form.file_path || '').trim()) {
    errors.push('请先上传或链接合同文件')
  }
  if (!String(form.contract_number || '').trim()) {
    errors.push('请先填写合同编号')
  }
  if (!String(form.contract_name || '').trim()) {
    errors.push('请先填写合同名称')
  }
  if (!String(form.contract_unit || '').trim()) {
    errors.push('请先填写合同单位')
  }
  if (!String(form.current_management_department || '').trim()) {
    errors.push('请先选择现管部门')
  }
  if (!String(form.contract_form || '').trim()) {
    errors.push('请先选择合同形式')
  }
  if (!String(form.contract_determination_method || '').trim()) {
    errors.push('请先选择合同确定方式')
  }
  if (!String(form.contract_type || '').trim()) {
    errors.push('请先选择合同类型')
  }
  if (!String(form.purchase_type || '').trim()) {
    errors.push('请先选择采购类型')
  }
  if (!String(form.contract_execution_status || '').trim()) {
    errors.push('请先选择合同执行状态')
  }
  if (!String(form.stamp_tax_rate || '').trim()) {
    errors.push('请先填写印花税率')
  }
  if (!String(form.pricing_method || '').trim()) {
    errors.push('请先选择计价方式')
  }
  if (ocrMdChecking.value) {
    errors.push('OCR文本检测中，请稍后再保存')
  } else if (!ocrMdLinkEnabled.value) {
    errors.push('未检测到OCR文本，请先完成OCR识别')
  }

  return errors
}

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
const smartMatchingFile = ref(false)
const uploadFolderDialogVisible = ref(false)
const uploadFolderSelectedPath = ref('')
const uploadTargetFolderPath = ref('')
const uploadFileInputRef = ref(null)
const paymentFlowRows = ref([])
const paymentFlowLoading = ref(false)
const paymentFlowError = ref('')

const saving = ref(false)
const contractDialogLoading = ref(false)
const dialogReadOnly = ref(false)
const editing = ref(null)
const currentPreviewRow = ref(null)
const pendingAiUploadFile = ref(null)
const previewUrl = ref('')
const previewLoading = ref(false)
const previewMessage = ref('暂无文件')
const previewFileName = ref('')
const ocrMdAvailable = ref(false)
const ocrMdChecking = ref(false)
let ocrMdProbeToken = 0
const canConfirmUploadFolder = computed(() => !!normalizePath(uploadFolderSelectedPath.value))
const paymentFlowEmptyText = computed(() => {
  if (!editing.value?.id) {
    return '请先保存合同后查看支付流水'
  }
  if (!String(form.contract_number || '').trim()) {
    return '当前合同没有合同编号，无法查询支付流水'
  }
  return '暂无支付流水'
})

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
  current_management_department: '',
  contract_form: '新签合同',
  contract_determination_method: '',
  handling_date: '',
  contract_type: '',
  purchase_type: '',
  contract_execution_status: '正在执行',
  stamp_tax_rate: '',
  pricing_method: '',
  is_archived: '未归档',
  color_flag: '',
  completeness: '',
  project: '',
  save_place: '',
  original_contract_id: '',
  original_contract_label: '',
  fullbody: '',
  created_by: '',
  created_at: '',
  updated_by: '',
  updated_at: '',
})

const formatMetaDateTime = (value) => {
  const text = String(value || '').trim()
  if (!text) {
    return '—'
  }

  const date = new Date(text)
  if (Number.isNaN(date.getTime())) {
    return text
  }

  const pad = (n) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}

const fullPreviewTitle = computed(() => {
  if (previewFileName.value) {
    return `文件预览 - ${previewFileName.value}`
  }

  const name = getFileName(currentPreviewRow.value?.file_path || '')
  return name ? `文件预览 - ${name}` : '文件预览'
})

const formatStorageBreadcrumb = (value) => {
  const parentPath = getParentPath(value)
  return parentPath ? `/${parentPath}` : '/'
}

const fullPreviewBreadcrumb = computed(() => formatStorageBreadcrumb(currentPreviewRow.value?.file_path || ''))
const linkFullPreviewBreadcrumb = computed(() => formatStorageBreadcrumb(linkSelectedFilePath.value))

const originalContractOptions = computed(() => {
  const currentId = editing.value?.id
  const base = (props.contracts || [])
    .filter((item) => item && item.id && item.id !== currentId)
    .map((item) => ({
      id: item.id,
      label: `${item.contract_number || '无编号'} - ${item.contract_name || '未命名合同'}`,
    }))

  const selectedId = Number(form.original_contract_id)
  if (Number.isInteger(selectedId) && selectedId > 0 && !base.some((item) => Number(item.id) === selectedId)) {
    base.unshift({
      id: selectedId,
      label: form.original_contract_label || `ID:${selectedId}`,
    })
  }

  return base
})

const originalContractDisplayLabel = computed(() => {
  const selectedId = Number(form.original_contract_id)
  if (!Number.isInteger(selectedId) || selectedId <= 0) {
    return ''
  }

  const matched = originalContractOptions.value.find((item) => Number(item.id) === selectedId)
  if (matched?.label) {
    return matched.label
  }

  return form.original_contract_label || `ID:${selectedId}`
})

const apiPrefix = import.meta.env.PROD ? '/docs/api' : '/api'
const appBasePrefix = import.meta.env.BASE_URL || '/'

const ocrPreviewRelativeDir = computed(() => {
  const normalizedPath = normalizePath(form.file_path)
  if (!normalizedPath) {
    return ''
  }

  const parts = normalizedPath.split('/').filter(Boolean)
  if (!parts.length) {
    return ''
  }

  const last = String(parts[parts.length - 1] || '').trim()
  if (!last) {
    return ''
  }
  const dotIndex = last.lastIndexOf('.')
  parts[parts.length - 1] = dotIndex > 0 ? last.slice(0, dotIndex) : last

  return parts.join('/')
})

const ocrMdRelativePath = computed(() => {
  if (!ocrPreviewRelativeDir.value) {
    return ''
  }
  return `${ocrPreviewRelativeDir.value}/full.md`
})

const ocrMdApiUrl = computed(() => {
  const relativePath = ocrMdRelativePath.value
  if (!relativePath) {
    return ''
  }

  const encodedPath = relativePath
    .split('/')
    .filter(Boolean)
    .map((item) => encodeURIComponent(item))
    .join('/')

  return `${apiPrefix}/html/${encodedPath}`
})

const ocrPreviewUrl = computed(() => {
  const relativeDir = ocrPreviewRelativeDir.value
  if (!relativeDir) {
    return ''
  }

  const encodedPath = relativeDir
    .split('/')
    .filter(Boolean)
    .map((item) => encodeURIComponent(item))
    .join('/')

  return `${appBasePrefix}preview/${encodedPath}/`
})

const ocrMdLinkEnabled = computed(() => {
  return !!ocrPreviewUrl.value && ocrMdAvailable.value && !ocrMdChecking.value
})

const probeOcrMdAvailability = async (url) => {
  const currentToken = ++ocrMdProbeToken
  if (!url) {
    ocrMdAvailable.value = false
    ocrMdChecking.value = false
    return
  }

  ocrMdChecking.value = true
  try {
    const response = await fetch(url, {
      method: 'GET',
      cache: 'no-store',
      credentials: 'same-origin',
    })
    if (currentToken !== ocrMdProbeToken) {
      return
    }
    ocrMdAvailable.value = response.ok
  } catch (_error) {
    if (currentToken !== ocrMdProbeToken) {
      return
    }
    ocrMdAvailable.value = false
  } finally {
    if (currentToken === ocrMdProbeToken) {
      ocrMdChecking.value = false
    }
  }
}

const waitForOcrMdAvailability = async (url, { maxAttempts = 1, delayMs = 0 } = {}) => {
  const targetUrl = String(url || '').trim()
  if (!targetUrl) {
    ocrMdProbeToken += 1
    ocrMdAvailable.value = false
    ocrMdChecking.value = false
    return false
  }

  const attempts = Math.max(1, Number(maxAttempts) || 1)
  const delay = Math.max(0, Number(delayMs) || 0)

  for (let index = 0; index < attempts; index += 1) {
    await probeOcrMdAvailability(targetUrl)
    if (ocrMdAvailable.value) {
      return true
    }

    if (index < attempts - 1 && delay > 0) {
      await new Promise((resolve) => {
        window.setTimeout(resolve, delay)
      })
    }
  }

  return ocrMdAvailable.value
}

const resetForm = () => {
  form.file_path = ''
  form.contract_name = ''
  form.contract_number = ''
  form.contract_unit = ''
  form.contract_amount = ''
  form.copy_count = ''
  form.handler = ''
  form.handling_department = ''
  form.current_management_department = ''
  form.contract_form = '新签合同'
  form.contract_determination_method = ''
  form.handling_date = ''
  form.contract_type = ''
  form.purchase_type = ''
  form.contract_execution_status = '正在执行'
  form.stamp_tax_rate = ''
  form.pricing_method = ''
  form.is_archived = '未归档'
  form.color_flag = ''
  form.completeness = ''
  form.project = ''
  form.save_place = ''
  form.original_contract_id = ''
  form.original_contract_label = ''
  form.fullbody = ''
  form.created_by = ''
  form.created_at = ''
  form.updated_by = ''
  form.updated_at = ''
  applyCompletenessDefault({ force: true })
}

const resetPaymentFlows = () => {
  paymentFlowRows.value = []
  paymentFlowError.value = ''
  paymentFlowLoading.value = false
}

const loadPaymentFlows = async (contractId) => {
  paymentFlowLoading.value = true
  paymentFlowError.value = ''
  try {
    const { data } = await http.get(`/contracts/${contractId}/payment-flows`)
    paymentFlowRows.value = Array.isArray(data?.payments) ? data.payments : []
  } catch (error) {
    paymentFlowRows.value = []
    paymentFlowError.value = '支付流水加载失败'
  } finally {
    paymentFlowLoading.value = false
  }
}

const setAiParsing = (value) => {
  emit('update:aiParsing', value)
}

const loadContractDetail = async (contractId) => {
  const { data } = await http.get(`/contracts/${contractId}`)
  return data
}

const openCreate = () => {
  contractDialogLoading.value = false
  dialogReadOnly.value = false
  editing.value = null
  pendingAiUploadFile.value = null
  currentPreviewRow.value = null
  previewFileName.value = ''
  resetForm()
  resetPaymentFlows()
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
  form.current_management_department = row.current_management_department || ''
  form.contract_form = row.contract_form || '新签合同'
  form.contract_determination_method = row.contract_determination_method || ''
  form.handling_date = row.handling_date || ''
  form.contract_type = row.contract_type || ''
  form.purchase_type = row.purchase_type || ''
  form.contract_execution_status = row.contract_execution_status || '正在执行'
  form.stamp_tax_rate = row.stamp_tax_rate || getStampTaxRateByContractType(row.contract_type)
  form.pricing_method = row.pricing_method || ''
  form.is_archived = row.is_archived || '未归档'
  form.color_flag = row.color_flag || ''
  form.completeness = row.completeness || ''
  form.project = row.project || ''
  form.save_place = row.save_place || ''
  form.original_contract_id = row.original_contract_id || ''
  form.original_contract_label = row?.original_contract
    ? `${row.original_contract.contract_number || '无编号'} - ${row.original_contract.contract_name || '未命名合同'}`
    : ''
  form.fullbody = row.fullbody || ''
  form.created_by = row.created_by || ''
  form.created_at = row.created_at || ''
  form.updated_by = row.updated_by || ''
  form.updated_at = row.updated_at || ''
  applyCompletenessDefault()
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
    ['current_management_department', 'current_management_department'],
    ['contract_determination_method', 'contract_determination_method'],
    ['handling_date', 'handling_date'],
    ['contract_type', 'contract_type'],
    ['purchase_type', 'purchase_type'],
    ['contract_execution_status', 'contract_execution_status'],
    ['stamp_tax_rate', 'stamp_tax_rate'],
    ['pricing_method', 'pricing_method'],
    ['is_archived', 'is_archived'],
    ['color_flag', 'color_flag'],
    ['completeness', 'completeness'],
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
  form.current_management_department = fields?.current_management_department || ''
  form.contract_form = fields?.contract_form || '新签合同'
  form.contract_determination_method = fields?.contract_determination_method || ''
  form.handling_date = fields?.handling_date || ''
  form.contract_type = fields?.contract_type || ''
  form.purchase_type = fields?.purchase_type || ''
  form.contract_execution_status = fields?.contract_execution_status || '正在执行'
  form.stamp_tax_rate = fields?.stamp_tax_rate || getStampTaxRateByContractType(fields?.contract_type)
  form.pricing_method = fields?.pricing_method || ''
  form.is_archived = fields?.is_archived || '未归档'
  form.color_flag = fields?.color_flag || ''
  form.completeness = fields?.completeness || ''
  form.project = fields?.project || ''
  form.save_place = fields?.save_place || ''
  form.original_contract_id = fields?.original_contract_id || ''
  form.original_contract_label = fields?.original_contract
    ? `${fields.original_contract.contract_number || '无编号'} - ${fields.original_contract.contract_name || '未命名合同'}`
    : ''
  form.fullbody = fields?.fullbody || ''
  applyCompletenessDefault({ force: true })
}

const openCreateFromAi = (file, fields) => {
  contractDialogLoading.value = false
  dialogReadOnly.value = false
  editing.value = null
  pendingAiUploadFile.value = file
  currentPreviewRow.value = null
  previewFileName.value = file?.name || ''
  resetForm()
  resetPaymentFlows()
  form.file_path = file?.name || ''
  applyParsedFields(fields || {})
  setPreviewFromFile(file)
  dialogVisible.value = true
}

const openCreateWithFilePath = async (filePath, fields) => {
  contractDialogLoading.value = false
  dialogReadOnly.value = false
  editing.value = null
  pendingAiUploadFile.value = null
  currentPreviewRow.value = null
  previewFileName.value = getFileName(filePath || '')
  resetForm()
  resetPaymentFlows()
  applyParsedFields(fields || {})
  form.file_path = String(filePath || '').trim()
  dialogVisible.value = true

  if (form.file_path) {
    await syncMainPreviewFromLinkedFile(form.file_path)
  } else {
    resetPreview('暂无文件')
  }
}

const openEditWithSupplementalFields = async (row, fields, options = {}) => {
  contractDialogLoading.value = true
  dialogReadOnly.value = Boolean(options?.readOnly)
  editing.value = row || {}
  currentPreviewRow.value = row || null
  previewFileName.value = ''
  pendingAiUploadFile.value = null
  resetForm()
  resetPaymentFlows()
  resetPreview('暂无文件')
  dialogVisible.value = true

  try {
    const detail = row?.id ? await loadContractDetail(row.id) : row
    editing.value = detail
    currentPreviewRow.value = detail
    populateFormFromContract(detail)
    applyAiSupplementalFields(fields || {}, detail)
    await Promise.all([
      loadPdfPreviewForRow(detail),
      loadPaymentFlows(detail.id),
    ])
  } catch (error) {
    dialogVisible.value = false
    ElMessage.error(error?.response?.data?.message || '合同详情加载失败')
  } finally {
    contractDialogLoading.value = false
  }
}

const openEdit = (row, options = {}) => openEditWithSupplementalFields(row, null, options)

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
  if (dialogReadOnly.value) {
    ElMessage.warning('当前为只读模式，无法执行解绑')
    return
  }

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
  if (dialogReadOnly.value) {
    ElMessage.warning('当前为只读模式，无法保存')
    return
  }

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

  if (!ocrMdLinkEnabled.value && ocrMdApiUrl.value) {
    await waitForOcrMdAvailability(ocrMdApiUrl.value, {
      maxAttempts: 3,
      delayMs: 600,
    })
  }

  const completenessValidationErrors = collectCompletenessRequiredFieldErrors()
  if (completenessValidationErrors.length > 0) {
    const detail = completenessValidationErrors
      .map((item, index) => `${index + 1}. ${item}`)
      .join('<br/>')

    await ElMessageBox.alert(detail, '请补全以下必填项', {
      confirmButtonText: '知道了',
      dangerouslyUseHTMLString: true,
    })
    return
  }

  applyCompletenessDefault({ force: true })

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
        current_management_department: form.current_management_department,
        contract_form: form.contract_form,
        contract_determination_method: form.contract_determination_method,
        handling_date: form.handling_date,
        contract_type: form.contract_type,
        purchase_type: form.purchase_type,
        contract_execution_status: form.contract_execution_status,
        stamp_tax_rate: form.stamp_tax_rate,
        pricing_method: form.pricing_method,
        is_archived: form.is_archived,
        color_flag: form.color_flag,
        ...(isSuperRole.value ? { completeness: form.completeness } : {}),
        project: form.project,
        save_place: normalizedSavePlace,
        original_contract_id: form.original_contract_id,
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
        current_management_department: form.current_management_department,
        contract_form: form.contract_form,
        contract_determination_method: form.contract_determination_method,
        handling_date: form.handling_date,
        contract_type: form.contract_type,
        purchase_type: form.purchase_type,
        contract_execution_status: form.contract_execution_status,
        stamp_tax_rate: form.stamp_tax_rate,
        pricing_method: form.pricing_method,
        is_archived: form.is_archived,
        color_flag: form.color_flag,
        ...(isSuperRole.value ? { completeness: form.completeness } : {}),
        project: form.project,
        save_place: normalizedSavePlace,
        original_contract_id: form.original_contract_id,
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

watch(
  () => form.handling_department,
  (value, oldValue) => {
    if (value === oldValue) {
      return
    }
    if (!String(form.current_management_department || '').trim()) {
      form.current_management_department = String(value || '').trim()
    }
  },
)

watch(
  [
    () => form.file_path,
    () => form.contract_number,
    () => form.contract_name,
    () => form.contract_unit,
    () => form.current_management_department,
    () => form.contract_form,
    () => form.contract_determination_method,
    () => form.contract_type,
    () => form.purchase_type,
    () => form.contract_execution_status,
    () => form.stamp_tax_rate,
    () => form.pricing_method,
  ],
  () => {
    applyCompletenessDefault()
  },
)

watch(
  () => ocrMdLinkEnabled.value,
  () => {
    applyCompletenessDefault()
  },
)

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

function normalizePath(value) {
  return String(value || '').replace(/\\/g, '/').replace(/^\/+|\/+$/g, '')
}

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

const normalizeMatchText = (value) => String(value || '').toLowerCase().replace(/[\s\-_.\/\\]+/g, '')

const normalizeNameForSimilarity = (value) => String(value || '').toLowerCase().replace(/[^\w\u4e00-\u9fff]/g, '')

const extractYearValue = (text) => {
  const num = Number(String(text || '').trim())
  if (!Number.isFinite(num)) {
    return null
  }
  if (num >= 1000 && num <= 9999) {
    return num
  }
  if (num >= 0 && num <= 99) {
    return 2000 + num
  }
  return null
}

const parseYearRangeFromFolderName = (name) => {
  const raw = String(name || '').trim()
  if (!raw) {
    return null
  }

  // Keep only digits and common separators, then parse in strict formats:
  // yy1-yy2, YYYY, YY.
  const text = raw.replace(/[^0-9\-~—–_]/g, '')
  if (!text) {
    return null
  }

  const rangeMatch = text.match(/^(\d{2,4})\s*[-~—–_]\s*(\d{2,4})$/)
  if (rangeMatch) {
    const startYear = extractYearValue(rangeMatch[1])
    const endYear = extractYearValue(rangeMatch[2])
    if (startYear && endYear) {
      return {
        start: Math.min(startYear, endYear),
        end: Math.max(startYear, endYear),
      }
    }
  }

  const singleMatch = text.match(/^(\d{4}|\d{2})$/)
  if (singleMatch) {
    const year = extractYearValue(singleMatch[1])
    if (year) {
      return { start: year, end: year }
    }
  }

  return null
}

const calcNameSimilarity = (left, right) => {
  const a = normalizeNameForSimilarity(left)
  const b = normalizeNameForSimilarity(right)
  if (!a || !b) {
    return 0
  }
  if (a === b) {
    return 1
  }

  const maxLen = Math.max(a.length, b.length)
  let same = 0
  const minLen = Math.min(a.length, b.length)
  for (let i = 0; i < minLen; i += 1) {
    if (a[i] === b[i]) {
      same += 1
    }
  }

  const includesBoost = a.includes(b) || b.includes(a) ? 0.2 : 0
  return Math.min(1, same / maxLen + includesBoost)
}

const collectFilesRecursively = async (rootFolderPath) => {
  const queue = [normalizePath(rootFolderPath)]
  const visited = new Set()
  const foundFiles = []

  while (queue.length > 0) {
    const folderPath = queue.shift()
    if (visited.has(folderPath)) {
      continue
    }
    visited.add(folderPath)

    const [{ data: filesData }, children] = await Promise.all([
      http.get('/folders/files', { params: { folder_path: folderPath } }),
      fetchLinkFolderChildren(folderPath),
    ])

    const rows = Array.isArray(filesData?.files) ? filesData.files : []
    foundFiles.push(...rows)

    for (const child of children || []) {
      const childPath = normalizePath(child?.path || '')
      if (!visited.has(childPath)) {
        queue.push(childPath)
      }
    }
  }

  return foundFiles
}

const chooseBestMatchedFile = (files) => {
  const contractNumber = normalizeMatchText(form.contract_number)
  const contractName = String(form.contract_name || '').trim()

  if (files.length === 0) {
    return null
  }

  if (contractNumber) {
    const numberMatched = files.filter((item) => {
      const fileName = normalizeMatchText(item?.name || item?.file_path || '')
      return fileName.includes(contractNumber)
    })

    if (numberMatched.length > 0) {
      numberMatched.sort((a, b) => {
        const simA = calcNameSimilarity(contractName, a?.name || '')
        const simB = calcNameSimilarity(contractName, b?.name || '')
        if (simB !== simA) {
          return simB - simA
        }
        return Number(b?.mtime || 0) - Number(a?.mtime || 0)
      })
      return numberMatched[0]
    }
  }

  if (contractName) {
    const ranked = files
      .map((item) => ({
        item,
        sim: calcNameSimilarity(contractName, item?.name || ''),
      }))
      .sort((a, b) => {
        if (b.sim !== a.sim) {
          return b.sim - a.sim
        }
        return Number(b.item?.mtime || 0) - Number(a.item?.mtime || 0)
      })

    if (ranked[0]?.sim > 0) {
      return ranked[0].item
    }
  }

  return null
}

const runSmartMatchFile = async () => {
  if (smartMatchingFile.value) {
    return
  }

  if (!String(form.contract_number || '').trim() && !String(form.contract_name || '').trim()) {
    ElMessage.warning('请先填写合同编号或合同名称后再智能匹配')
    return
  }

  smartMatchingFile.value = true
  try {
    const rootChildren = await fetchLinkFolderChildren('', { force: false })
    let searchBasePath = ''

    const departmentName = String(form.handling_department || '').trim()
    if (departmentName) {
      const deptNode = (rootChildren || []).find((node) => String(node?.name || '').trim() === departmentName)
      if (deptNode?.path) {
        searchBasePath = normalizePath(deptNode.path)
      }
    }

    const level3Candidates = await fetchLinkFolderChildren(searchBasePath, { force: false })
    const yearFolders = (level3Candidates || []).filter((node) => !!parseYearRangeFromFolderName(node?.name || ''))

    const handlingYear = (() => {
      const text = String(form.handling_date || '').trim()
      const match = text.match(/(20\d{2})/)
      return match ? Number(match[1]) : null
    })()

    let searchRoots = []
    if (yearFolders.length > 0) {
      if (handlingYear) {
        searchRoots = yearFolders
          .filter((node) => {
            const range = parseYearRangeFromFolderName(node?.name || '')
            return range && handlingYear >= range.start && handlingYear <= range.end
          })
          .map((node) => normalizePath(node?.path || ''))
      }
      if (searchRoots.length === 0) {
        searchRoots = yearFolders.map((node) => normalizePath(node?.path || ''))
      }
    } else {
      searchRoots = [searchBasePath]
    }

    const candidateFiles = []
    for (const rootPath of searchRoots) {
      const rows = await collectFilesRecursively(rootPath)
      candidateFiles.push(...rows)
    }

    const best = chooseBestMatchedFile(candidateFiles)
    if (!best?.file_path) {
      ElMessage.warning('未找到可匹配的文件')
      return
    }

    const targetFilePath = normalizePath(best.file_path)
    const targetFolderPath = getParentPath(targetFilePath)
    await expandLinkTreeToPath(targetFolderPath)
    await loadLinkFiles(targetFolderPath)
    linkSelectedFilePath.value = targetFilePath
    await openLinkFilePreview(targetFilePath)
    ElMessage.success('已定位到智能匹配文件')
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || '智能匹配失败')
  } finally {
    smartMatchingFile.value = false
  }
}

const openLinkFileDialog = async () => {
  linkFileDialogVisible.value = true
  linkTreeLoading.value = true
  linkSelectedFilePath.value = form.file_path || ''
  cleanupLinkPreview()
  try {
    await ensureLinkTreeLoaded()

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

const ensureLinkTreeLoaded = async () => {
  applyLinkTreeSnapshot(props.linkTreeSnapshot || {})
  if (linkTreeData.value.length) {
    return
  }

  const { data } = await http.get('/folders/tree')
  const root = data?.root || { name: '/', path: '' }
  linkRootName.value = root?.name || '/'
  linkTreeData.value = await fetchLinkFolderChildren('', { force: true })
}

const onUploadFolderNodeClick = async (node) => {
  const normalizedFolderPath = normalizePath(node?.path || '')
  uploadFolderSelectedPath.value = normalizedFolderPath

  const cachedChildren = getCachedChildren(normalizedFolderPath)
  if (cachedChildren) {
    linkTreeRef.value?.updateKeyChildren?.(normalizedFolderPath, cachedChildren)
  }

  await refreshLinkTreeNodeChildren(normalizedFolderPath, false)
}

const openUploadFolderDialog = async () => {
  uploadFolderDialogVisible.value = true
  linkTreeLoading.value = true
  uploadFolderSelectedPath.value = normalizePath(uploadTargetFolderPath.value)
  try {
    await ensureLinkTreeLoaded()
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || '加载文件夹树失败')
  } finally {
    linkTreeLoading.value = false
  }
}

const confirmUploadFolderSelection = () => {
  const selected = normalizePath(uploadFolderSelectedPath.value)
  if (!selected) {
    ElMessage.warning('请选择上传目录')
    return
  }

  uploadTargetFolderPath.value = selected
  uploadFolderDialogVisible.value = false
  uploadFileInputRef.value?.click()
}

const handleUploadFileSelected = async (event) => {
  const file = event?.target?.files?.[0]
  if (!file) {
    return
  }

  const targetFolderPath = normalizePath(uploadTargetFolderPath.value)
  if (!targetFolderPath) {
    ElMessage.warning('请先选择上传目录')
    event.target.value = ''
    return
  }

  try {
    const fd = new FormData()
    fd.append('folder_path', targetFolderPath)
    fd.append('files', file)

    const { data } = await http.post('/folders/upload', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 300000,
    })

    const uploadedRows = Array.isArray(data?.uploaded) ? data.uploaded : []
    const uploadedPath = String(uploadedRows?.[0]?.file_path || '').trim()
    if (!uploadedPath) {
      throw new Error('上传成功但未返回文件路径')
    }

    pendingAiUploadFile.value = null

    if (editing.value?.id) {
      await http.put(`/contracts/${editing.value.id}`, {
        file_path: uploadedPath,
      })
      await syncEditingFileState(uploadedPath)
      ElMessage.success('上传成功')
      emit('saved')
    } else {
      form.file_path = uploadedPath
      await syncMainPreviewFromLinkedFile(uploadedPath)
      ElMessage.success('上传成功，点击“保存”后生效')
    }
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || error?.message || '上传失败')
  } finally {
    event.target.value = ''
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

  const filePath = String(form.file_path || '').trim()
  if (!filePath) {
    ElMessage.warning('请先上传或链接合同文件后再进行AI识别')
    return
  }

  const payload = {
    file_path: normalizePath(filePath),
  }

  setAiParsing(true)
  ElMessage.info('AI正在解析当前合同，请稍候')
  try {
    const { data } = await http.post('/contracts/ai-parse', payload, {
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

    if (ocrMdApiUrl.value) {
      await waitForOcrMdAvailability(ocrMdApiUrl.value, {
        maxAttempts: 6,
        delayMs: 600,
      })
    }

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
    ocrMdProbeToken += 1
    ocrMdAvailable.value = false
    ocrMdChecking.value = false
    contractDialogLoading.value = false
    dialogReadOnly.value = false
    resetPaymentFlows()
    resetPreview('暂无文件')
  }
})

watch(
  [ocrMdApiUrl, dialogVisible],
  ([url, visible]) => {
    if (!visible || !url) {
      ocrMdProbeToken += 1
      ocrMdAvailable.value = false
      ocrMdChecking.value = false
      return
    }

    probeOcrMdAvailability(url)
  },
  { immediate: true },
)

watch(linkFileDialogVisible, (visible) => {
  if (!visible) {
    cleanupLinkPreview()
  }
})

watch(uploadFolderDialogVisible, (visible) => {
  if (!visible) {
    uploadFolderSelectedPath.value = normalizePath(uploadTargetFolderPath.value)
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

.contract-dialog-loading-panel {
  min-height: 360px;
  display: grid;
  place-items: center;
  align-content: center;
  gap: 12px;
}

.contract-dialog-loading-icon {
  font-size: 28px;
  color: #2563eb;
}

.contract-dialog-loading-text {
  font-size: 14px;
  color: #6b7280;
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

.fullscreen-dialog-title-wrap {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
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

.fullscreen-dialog-breadcrumb {
  min-width: 0;
  color: #6b7280;
  font-size: 12px;
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

.contract-meta-info {
  margin-top: 8px;
  padding: 0 4px;
  display: flex;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 4px 12px;
  font-size: 12px;
  line-height: 1.4;
  color: #9ca3af;
}

.payment-flow-section {
  margin-top: 14px;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  background: #ffffff;
  padding: 10px;
}

.payment-flow-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.payment-flow-title {
  font-size: 14px;
  font-weight: 600;
  color: #374151;
}

.payment-flow-count {
  font-size: 12px;
  color: #6b7280;
}

.payment-flow-alert {
  margin-bottom: 8px;
}

.payment-flow-table-wrap {
  min-height: 86px;
}

.form-item-span-2 {
  grid-column: span 1;
}

.status-checkbox-group {
  display: inline-flex;
  align-items: center;
  gap: 12px;
}

.contract-name-with-flag {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 8px;
}

.contract-name-input {
  flex: 1;
}

.flag-trigger {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  border: 1px solid #d1d5db;
  background: #ffffff;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}

.flag-trigger:hover {
  border-color: #93c5fd;
  background: #eff6ff;
}

.flag-icon {
  font-size: 16px;
  line-height: 1;
}

.flag-icon.is-red { color: #ef4444; }
.flag-icon.is-orange { color: #f97316; }
.flag-icon.is-yellow { color: #eab308; }
.flag-icon.is-green { color: #22c55e; }
.flag-icon.is-blue { color: #3b82f6; }
.flag-icon.is-none { color: #9ca3af; }

.flag-dropdown-menu :deep(.el-dropdown-menu__item) {
  min-width: 46px;
  justify-content: center;
}

.original-contract-field {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.original-contract-hint {
  font-size: 12px;
  color: #6b7280;
  line-height: 1.4;
  word-break: break-all;
}

.preview-actions {
  display: flex;
  align-items: center;
}

.preview-action-group {
  display: inline-flex;
  border-radius: 16px;
  padding: 2px;
  background: rgba(255, 255, 255, 0.94);
  border: 1px solid rgba(15, 23, 42, 0.08);
  box-shadow: 0 8px 20px rgba(15, 23, 42, 0.1), 0 2px 4px rgba(15, 23, 42, 0.06);
}

.preview-action-upload {
  display: inline-flex;
}

.upload-folder-dialog-tip {
  margin-bottom: 8px;
  color: #4b5563;
  font-size: 13px;
}

.upload-folder-dialog-selected {
  margin-bottom: 10px;
  color: #1f2937;
  font-size: 13px;
  word-break: break-all;
}

.upload-folder-tree-wrap {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 8px;
  min-height: 280px;
  max-height: 56vh;
  overflow: auto;
}

.upload-folder-tree-node {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}

.upload-folder-tree-icon {
  font-size: 16px;
  line-height: 1;
}

.upload-folder-tree-label {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.preview-action-group :deep(.el-upload) {
  display: inline-flex;
}

.preview-action-group :deep(.el-button) {
  border: none;
  border-radius: 0;
  min-height: 30px;
  color: #1f2937;
  background: linear-gradient(180deg, #ffffff 0%, #f8fbff 100%);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.92);
}

.preview-action-group :deep(.el-button + .el-button) {
  margin-left: 0;
}

.preview-action-group :deep(.el-button + .el-button::before) {
  content: '';
  position: absolute;
  left: 0;
  top: 6px;
  bottom: 6px;
  width: 1px;
  background: rgba(15, 23, 42, 0.12);
  pointer-events: none;
}

.preview-action-group :deep(.el-button:first-child) {
  border-top-left-radius: 12px;
  border-bottom-left-radius: 12px;
}

.preview-action-group :deep(.el-button:last-child) {
  border-top-right-radius: 12px;
  border-bottom-right-radius: 12px;
}

.preview-action-group :deep(.el-button:hover),
.preview-action-group :deep(.el-button:focus-visible) {
  color: #1d4ed8;
  background: linear-gradient(180deg, #ffffff 0%, #eaf1ff 100%);
}

.preview-action-group :deep(.el-button.is-disabled) {
  background: linear-gradient(180deg, #ffffff 0%, #f4f6f8 100%);
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

.ocr-md-link {
  margin-left: auto;
  flex-shrink: 0;
  font-size: 12px;
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

.link-left-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 8px;
}

.link-left-header .panel-title {
  margin-bottom: 0;
}

.apple-smart-match-btn {
  border-radius: 999px;
  border: 1px solid rgba(15, 23, 42, 0.12);
  background: linear-gradient(180deg, #ffffff 0%, #f2f6ff 100%);
  box-shadow: 0 6px 16px rgba(15, 23, 42, 0.12), inset 0 1px 0 rgba(255, 255, 255, 0.95);
  color: #1f2937;
}

.apple-smart-match-btn:hover {
  color: #1d4ed8;
  border-color: rgba(37, 99, 235, 0.35);
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