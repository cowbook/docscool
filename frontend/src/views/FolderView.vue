<template>
  <div class="folder-page">
    <el-card>
      <template #header>
        <div class="card-header">
          <div class="card-main">
            <div class="card-title">文件夹 （拖放上传）</div>
            <div class="card-subtitle">{{ selectedFolderPath || '/' }}</div>
          </div>
          <div class="header-actions">
            <el-input
              v-model="searchKeyword"
              clearable
              class="header-search"
              placeholder="全文搜索（当前目录）"
              @clear="applySearch"
              @keyup.enter="applySearch"
            />
            <el-button @click="applySearch">搜索</el-button>
          </div>
        </div>
      </template>

      <div ref="folderLayoutRef" class="folder-layout" :style="folderLayoutStyle">
        <div ref="leftPanelRef" class="left-panel" @contextmenu.prevent="onLeftPanelContextMenu">
          <div class="panel-title">
            <div class="panel-title-main">
              <button
                type="button"
                class="root-folder-trigger"
                title="回到根目录"
                @click="goToRootFolder"
              >
                <Icon :icon="mdiFolderOutline" /><span style="font-size:16px;font-weight: 600;display: inline-block;margin-left: 4px; ">{{ rootName }} </span>

              </button>
            </div>
            <div class="panel-subtitle">
                <span v-if="loadingRecursiveCount">...</span>
                <span v-else>{{ recursiveFileCount }}</span>
              </div>
          </div>
          <div
            ref="treeWrapRef"
            class="tree-wrap"
            @contextmenu.prevent="onPanelContextMenu"
            @dragenter.capture.prevent="onTreeDragOver"
            @dragover.capture.prevent="onTreeDragOver"
            @dragleave.capture="onTreeDragLeave"
            @drop.capture.stop.prevent="onTreeDrop"
          >
          <el-tree
            ref="treeRef"
            :key="treeRenderKey"
            v-loading="loadingTree"
            :data="treeData"
            node-key="path"
            :props="treeProps"
            lazy
            :load="loadTreeChildren"
            :expand-on-click-node="true"
            highlight-current
            @node-click="onTreeNodeClick"
            @node-contextmenu="onTreeNodeContextMenu"
          >
            <template #default="{ node, data }">
              <span
                class="tree-node-content"
                :class="{ 'tree-node-drop-active': dragOverNodePath === normalizePath(data.path) }"
                :data-path="normalizePath(data.path)"
              >
                <span class="tree-folder-icon" aria-hidden="true">{{ node.expanded ? '📂' : '📁' }}</span>
                <span class="tree-node-label">{{ data.name }}</span>
              </span>
            </template>
          </el-tree>
          </div>
          <div v-if="contextMenuVisible" class="tree-context-menu" :style="contextMenuStyle">
            <button type="button" class="menu-item" @click="handleContextCommand('create')">新建文件夹</button>
            <button
              v-if="canRenameContextFolder"
              type="button"
              class="menu-item"
              :disabled="!contextTargetPath"
              @click="handleContextCommand('rename')"
            >
              改名
            </button>
            <button
              v-if="canDeleteContextFolder"
              type="button"
              class="menu-item menu-item-danger"
              :disabled="!contextTargetPath"
              @click="handleContextCommand('delete')"
            >
              删除文件夹
            </button>
          </div>
        </div>

        <div
          class="panel-splitter"
          :class="{ 'panel-splitter-active': isResizingPanels }"
          @mousedown.prevent="startPanelResize"
        ></div>

        <div ref="rightPanelRef" class="right-panel">
          <div class="panel-title-row">
            <div class="panel-title-block">
              <div class="panel-title">
                
                <div class="panel-title-main">文件列表</div>

              
                <div class="panel-subtitle">
                  <span>{{ currentFileCount }}</span>
                </div>

              </div>
            
            </div>
            <div class="panel-title-actions">
              <input
                ref="folderUploadInputRef"
                type="file"
                multiple
                class="folder-upload-input"
                @change="handleFolderFilesSelected"
              />
              <el-button-group class="apple-button-group">
                <el-button
                  size="small"
                  :loading="batchMatching"
                  :disabled="!canOperateOnSelectedFolder"
                  @click="openBatchMatchDialog"
                >
                  <el-icon><Search /></el-icon>
                  <span>批量匹配</span>
                </el-button>
                <el-button
                  size="small"
                  type="primary"
                  :loading="uploadingFolderFiles"
                  :disabled="!canOperateOnSelectedFolder"
                  @click="triggerFolderUpload"
                >
                  <el-icon><Upload /></el-icon>
                  <span>上传文件</span>
                </el-button>
              </el-button-group>
            </div>
          </div>

          <div
            ref="fileTableWrapRef"
            class="file-table-wrap"
            @contextmenu.prevent
            @dragenter.capture.prevent="onFileTableDragOver"
            @dragover.capture.prevent="onFileTableDragOver"
            @drop.capture.stop.prevent="onFileTableDrop"
          >
          <div v-if="noPermissionForSelectedFolder" class="file-list-no-permission">您没有权限</div>
          <el-table
            v-else
            v-loading="loadingFiles"
            :data="filteredFiles"
            border
            stripe
            size="small"
            class="file-table"
            @header-dragend="onTableHeaderDragEnd"
          >
            <template #empty>
              <div class="file-table-empty">
                <el-icon class="file-table-empty-icon"><Upload /></el-icon>
                <span>拖放文件上传（无文件）</span>
              </div>
            </template>

            <el-table-column
              column-key="fileName"
              label="文件"
              :width="fileColumnWidth"
              :min-width="210"
              :resizable="true"
            >
              <template #default="scope">

              

                <el-link
                  class="file-cell"
                  @click.stop.prevent="openFilePreview(scope.row, $event)"
                  @contextmenu.prevent.stop="onFileCellContextMenu($event, scope.row)"
                >
             
                  <span class="file-cell-inner">
                    <Icon :icon="getFileIcon(scope.row.file_path)" class="file-icon" />
                    <span class="file-name" :title="scope.row.name">{{ scope.row.name }}</span>
                  </span>
                </el-link>
              </template>
            </el-table-column>

            <el-table-column prop="modified_by" label="修改人" min-width="110" show-overflow-tooltip />

            <el-table-column label="修改时间" min-width="168">
              <template #default="scope">
                <span>{{ formatFileModifiedTime(scope.row?.mtime) }}</span>
              </template>
            </el-table-column>

         

            <el-table-column label="合同名称" min-width="260">
              <template #default="scope">
                <div class="contract-name-cell">
                  <el-tooltip
                    v-if="hasRealContractName(scope.row)"
                    :content="(isArchivedValue(scope.row?.is_archived) ? '已归档' : '未归档') + '-' + scope.row.contract_name"
                  >
                    <el-link
                      class="contract-name-link"
                      type="primary"
                      @click.stop="openContractEditFromFileRow(scope.row)"
                    >
                      <span
                        class="archive-status-icon"
                        :class="isArchivedValue(scope.row?.is_archived) ? 'archive-status-icon-archived' : 'archive-status-icon-unarchived'"
                      >
                        <Icon :icon="isArchivedValue(scope.row?.is_archived) ? mdiArchive : mdiHelp" />
                      </span>

                      <span class="contract-name-text">{{ scope.row.contract_name }}</span>
                    </el-link>
                  </el-tooltip>

                  <div v-else class="unmatched-contract-actions">
                    <span class="contract-name-text" :title="scope.row.contract_name">{{ scope.row.contract_name }}</span>
                    <el-button size="small" type="primary" link @click.stop="openCreateFromFileRow(scope.row)">新建</el-button>
                    <el-button
                      size="small"
                      type="success"
                      link
                      :loading="aiParsingFilePath === scope.row.file_path"
                      @click.stop="startAiMatchFromFileRow(scope.row)"
                    >
                      AI
                    </el-button>
                  </div>
                </div>
              </template>
            </el-table-column>
  

            <el-table-column
              prop="contract_number"
              label="合同编号"
              min-width="140"
              show-overflow-tooltip
              class-name="contract-number-col"
            />
            <el-table-column label="原合同" min-width="220" show-overflow-tooltip>
              <template #default="scope">
                <span :title="formatOriginalContractLabel(scope.row)">
                  {{ formatOriginalContractLabel(scope.row) || '-' }}
                </span>
              </template>
            </el-table-column>
            <el-table-column prop="contract_unit" label="合同单位" min-width="180" show-overflow-tooltip />
            <el-table-column prop="contract_amount" label="合同金额" min-width="120" />
            <el-table-column prop="copy_count" label="份数" min-width="80" />
            <el-table-column prop="handler" label="承办人" min-width="100" />
            <el-table-column prop="handling_department" label="承办部门" min-width="130" />
            <el-table-column prop="handling_date" label="承办日期" min-width="120" />
            <el-table-column prop="contract_type" label="合同类型" min-width="110" />
            <el-table-column prop="purchase_type" label="采购类型" min-width="110" />
            <el-table-column prop="stamp_tax_rate" label="印花税率" min-width="100" />
            <el-table-column prop="save_place" label="存档位置" min-width="140" show-overflow-tooltip />
         
            <el-table-column prop="project" label="项目" min-width="220" show-overflow-tooltip />

          </el-table>

            <div v-if="fileContextMenuVisible && !isViewPermissionUser" class="file-context-menu" :style="fileContextMenuStyle">
              <button type="button" class="menu-item" :disabled="!fileContextTarget" @click="handleFileContextCommand('move')">移动</button>
              <button type="button" class="menu-item" :disabled="!fileContextTarget" @click="handleFileContextCommand('rename')">改名</button>
              <button type="button" class="menu-item menu-item-danger" :disabled="!fileContextTarget" @click="handleFileContextCommand('delete')">删除</button>
            </div>
          </div>
        </div>
      </div>
    </el-card>

    <el-dialog v-model="previewDialogVisible" width="96vw" top="2vh" destroy-on-close append-to-body>
      
      <template #header>
        
        <div class="preview-header">
          <span class="preview-title">{{ previewTitle }}</span>
          <el-button type="primary" :disabled="!previewRow" @click="downloadFile(previewRow)">下载原文件</el-button>
        </div>

      </template>

      <div class="preview-wrapper">

        <VuePdfEmbed
          v-if="previewUrl"
          :source="previewUrl"
          class="pdf-preview-embed"
          @rendering-failed="onPdfRenderFailed"
        />
        <div v-else class="preview-placeholder">暂无可预览内容</div>

      </div>

      <template #footer>
        <el-button @click="previewDialogVisible = false">关闭</el-button>
      </template>

    </el-dialog>

    <el-dialog
      v-model="batchMatchDialogVisible"
      title="批量匹配"
      width="min(980px, 96vw)"
      :close-on-click-modal="false"
    >
      <el-input
        v-model="batchMatchLogText"
        type="textarea"
        class="batch-match-log"
        :rows="18"
        resize="none"
        readonly
      />

      <template #footer>
        <el-button @click="batchMatchDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="batchMatching" @click="startBatchMatch">开始匹配</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="moveFileDialogVisible"
      title="移动文件"
      width="min(680px, 96vw)"
      :close-on-click-modal="false"
      @closed="resetMoveFileDialog"
    >
      <div class="move-dialog-content">
        <div class="move-dialog-row"><span class="move-dialog-label">文件：</span>{{ moveFileSourceName || '-' }}</div>
        <div class="move-dialog-row"><span class="move-dialog-label">当前路径：</span>{{ moveFileSourcePath || '-' }}</div>
        <div class="move-dialog-row"><span class="move-dialog-label">目标目录：</span>{{ moveFileTargetPath || '/' }}</div>

        <div class="move-dialog-actions">
          <el-button size="small" @click="moveFileTargetPath = ''">选择根目录 /</el-button>
        </div>

        <el-tree
          ref="moveTargetTreeRef"
          class="move-target-tree"
          :data="treeData"
          node-key="path"
          :props="treeProps"
          lazy
          :load="loadTreeChildren"
          :expand-on-click-node="true"
          highlight-current
          @node-click="onMoveTargetNodeClick"
        >
          <template #default="{ node, data }">
            <span class="tree-node-content" :data-path="normalizePath(data.path)">
              <span class="tree-folder-icon" aria-hidden="true">{{ node.expanded ? '📂' : '📁' }}</span>
              <span class="tree-node-label">{{ data.name }}</span>
            </span>
          </template>
        </el-tree>
      </div>

      <template #footer>
        <el-button @click="moveFileDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="movingFile" @click="confirmMoveFile">移动</el-button>
      </template>
    </el-dialog>

    <ContractItem
      ref="contractItemRef"
      :departments="departments"
      :contracts="contractEditorContracts"
      :options="options"
      v-model:aiParsing="contractItemAiParsing"
      :show-file-actions="false"
      @saved="handleContractSaved"
    />

    <AiMatchDialog
      v-model="aiMatchDialogVisible"
      :candidates="aiMatchCandidates"
      :processing="aiMatchProcessing"
      :file="aiParsedUploadFile"
      @confirm-selection="proceedAiMatchSelection"
      @cancel="closeAiMatchDialog"
    />
    
  </div>

</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Upload } from '@element-plus/icons-vue'
import { Icon } from '@iconify/vue'
import mdiArchive from '@iconify-icons/mdi/archive-check-outline'
import mdiHelp from '@iconify-icons/mdi/help-circle-outline'
import mdiFolderOutline from '@iconify-icons/mdi/folder-outline'
import VuePdfEmbed from 'vue-pdf-embed'
import fileTypeWord from '@iconify-icons/vscode-icons/file-type-word'
import fileTypeExcel from '@iconify-icons/vscode-icons/file-type-excel'
import fileTypePdf from '@iconify-icons/vscode-icons/file-type-pdf2'
import microsoftOffice from '@iconify-icons/simple-icons/microsoftoffice'
import { GlobalWorkerOptions } from 'pdfjs-dist/legacy/build/pdf.mjs'
import PdfWorker from 'pdfjs-dist/legacy/build/pdf.worker.min.mjs?url'

import http from '../api/http'
import ContractItem from '../components/ContractItem.vue'
import AiMatchDialog from '../components/AiMatchDialog.vue'

GlobalWorkerOptions.workerSrc = PdfWorker

const loadingTree = ref(false)
const loadingFiles = ref(false)
const treeRef = ref(null)
const treeData = ref([])
const treeRenderKey = ref(0)
const files = ref([])
const rootName = ref('/')
const selectedFolderPath = ref('')
const searchKeyword = ref('')
const activeKeyword = ref('')
const fileColumnManualWidth = ref(0)
const previewDialogVisible = ref(false)
const previewUrl = ref('')
const previewRow = ref(null)
const contractItemRef = ref(null)
const contractItemAiParsing = ref(false)
const departments = ref([])
const contractEditorContracts = ref([])
const options = ref({
  contract_form: [],
  contract_determination_method: [],
  contract_type: [],
  purchase_type: [],
  stamp_tax_rate_by_contract_type: {},
  pricing_method: [],
  is_archived: [],
  project: [],
})
const contextMenuVisible = ref(false)
const contextMenuStyle = ref({ left: '0px', top: '0px' })
const contextTargetPath = ref('')
const fileContextMenuVisible = ref(false)
const fileContextMenuStyle = ref({ left: '0px', top: '0px' })
const fileContextTarget = ref(null)
const moveFileDialogVisible = ref(false)
const movingFile = ref(false)
const moveFileSourceRow = ref(null)
const moveFileTargetPath = ref('')
const moveTargetTreeRef = ref(null)
const folderUploadInputRef = ref(null)
const uploadingFolderFiles = ref(false)
const leftPanelRef = ref(null)
const rightPanelRef = ref(null)
const treeWrapRef = ref(null)
const fileTableWrapRef = ref(null)
const folderLayoutRef = ref(null)
const leftPanelWidth = ref(190)
const isResizingPanels = ref(false)
const aiMatchDialogVisible = ref(false)
const aiMatchProcessing = ref(false)
const aiMatchCandidates = ref([])
const aiParsedFields = ref(null)
const aiParsedUploadFile = ref(null)
const aiMatchSourceRow = ref(null)
const aiParsingFilePath = ref('')
const AI_NEW_CONTRACT_VALUE = '__new_contract__'
const batchMatching = ref(false)
const batchMatchDialogVisible = ref(false)
const batchMatchLogText = ref('')
const recursiveFileCount = ref(0)
const loadingRecursiveCount = ref(false)
const dragOverNodePath = ref('')
const userRole = ref('admin')
const userPermission = ref('view')
const allowedFolderRoots = ref([])
const noPermissionForSelectedFolder = ref(false)
const FOLDER_CHILDREN_CACHE_TTL_MS = 15_000
const folderChildrenCache = new Map()
const folderChildrenInFlight = new Map()
let recursiveCountToken = 0

const folderLayoutStyle = computed(() => {
  return {
    gridTemplateColumns: `${leftPanelWidth.value}px 12px minmax(0, 1fr)`,
  }
})

const treeProps = {
  label: 'name',
  children: 'children',
}

const normalizePath = (value) => String(value || '').replace(/\\/g, '/').replace(/^\/+|\/+$/g, '')
const appBasePrefix = import.meta.env.BASE_URL || '/'

const buildOcrPreviewUrlFromFilePath = (filePath) => {
  const normalizedPath = normalizePath(filePath)
  if (!normalizedPath) {
    return ''
  }

  const parts = normalizedPath.split('/').filter(Boolean)
  if (!parts.length) {
    return ''
  }

  const last = String(parts[parts.length - 1] || '').trim()
  const dotIndex = last.lastIndexOf('.')
  parts[parts.length - 1] = dotIndex > 0 ? last.slice(0, dotIndex) : last

  const encodedPath = parts
    .filter(Boolean)
    .map((item) => encodeURIComponent(item))
    .join('/')

  return `${appBasePrefix}preview/${encodedPath}/`
}

const isSuperAdminUser = computed(() => ['super_admin', 'synology_super_admin'].includes(userRole.value))
const isViewPermissionUser = computed(() => {
  if (isSuperAdminUser.value) {
    return false
  }
  return userPermission.value === 'view'
})
const hasAllFolderPermission = computed(() => {
  if (isSuperAdminUser.value) {
    return true
  }
  return allowedFolderRoots.value.includes('全部')
})
const allowedFolderRootSet = computed(() => {
  const items = allowedFolderRoots.value
    .map((item) => String(item || '').trim())
    .filter((item) => item && item !== '全部')
  return new Set(items)
})

const getTopLevelFolderName = (path) => {
  const normalizedPath = normalizePath(path)
  if (!normalizedPath) {
    return ''
  }
  const [top] = normalizedPath.split('/')
  return String(top || '').trim()
}

const isTopLevelFolderPath = (path) => {
  const normalizedPath = normalizePath(path)
  if (!normalizedPath) {
    return false
  }
  return !normalizedPath.includes('/')
}

const hasFolderAccess = (path) => {
  const normalizedPath = normalizePath(path)
  if (!normalizedPath) {
    return hasAllFolderPermission.value
  }
  if (hasAllFolderPermission.value) {
    return true
  }

  const topLevelFolder = getTopLevelFolderName(normalizedPath)
  if (!topLevelFolder) {
    return false
  }
  return allowedFolderRootSet.value.has(topLevelFolder)
}

const filterChildrenByFolderAccess = (children) => {
  const list = Array.isArray(children) ? children : []
  if (hasAllFolderPermission.value) {
    return list
  }
  return list.filter((item) => hasFolderAccess(item?.path || ''))
}

const canOperateOnSelectedFolder = computed(() => {
  if (uploadingFolderFiles.value || noPermissionForSelectedFolder.value) {
    return false
  }
  const normalizedPath = normalizePath(selectedFolderPath.value)
  if (!normalizedPath) {
    return hasAllFolderPermission.value
  }
  return hasFolderAccess(normalizedPath)
})

const canRenameContextFolder = computed(() => {
  const targetPath = normalizePath(contextTargetPath.value)
  if (!targetPath || !hasFolderAccess(targetPath)) {
    return false
  }
  if (!isSuperAdminUser.value && isTopLevelFolderPath(targetPath)) {
    return false
  }
  return true
})

const canDeleteContextFolder = computed(() => {
  const targetPath = normalizePath(contextTargetPath.value)
  if (!targetPath || !hasFolderAccess(targetPath)) {
    return false
  }
  if (!isSuperAdminUser.value && isTopLevelFolderPath(targetPath)) {
    return false
  }
  return true
})

const parseDateFromUnknown = (value) => {
  if (value instanceof Date) {
    return Number.isFinite(value.getTime()) ? value : null
  }

  if (typeof value === 'number' && Number.isFinite(value)) {
    if (value <= 0) {
      return null
    }
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
    if (!Number.isFinite(numeric) || numeric <= 0) {
      return null
    }
    const ms = numeric < 1e12 ? numeric * 1000 : numeric
    const date = new Date(ms)
    return Number.isFinite(date.getTime()) ? date : null
  }

  const isoLike = text.includes(' ') ? text.replace(' ', 'T') : text
  let date = new Date(isoLike)
  if (Number.isFinite(date.getTime())) {
    return date
  }

  date = new Date(text.replace(/-/g, '/'))
  return Number.isFinite(date.getTime()) ? date : null
}

const formatFileModifiedTime = (value) => {
  const date = parseDateFromUnknown(value)
  if (!date) {
    return '-'
  }

  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

const getParentPath = (value) => {
  const path = normalizePath(value)
  if (!path) {
    return ''
  }
  const idx = path.lastIndexOf('/')
  return idx >= 0 ? path.slice(0, idx) : ''
}

const clearFolderChildrenRequestCache = () => {
  folderChildrenCache.clear()
  folderChildrenInFlight.clear()
}

const fetchFolderChildren = async (parentPath = '') => {
  const normalizedParent = normalizePath(parentPath)
  const now = Date.now()

  const cached = folderChildrenCache.get(normalizedParent)
  if (cached && now - cached.ts <= FOLDER_CHILDREN_CACHE_TTL_MS) {
    return cached.children
  }

  const inFlight = folderChildrenInFlight.get(normalizedParent)
  if (inFlight) {
    return inFlight
  }

  const requestPromise = (async () => {
    const { data } = await http.get('/folders/children', {
      params: { parent_path: normalizedParent },
    })
    const children = filterChildrenByFolderAccess(data?.children)
    folderChildrenCache.set(normalizedParent, {
      ts: Date.now(),
      children,
    })
    return children
  })()

  folderChildrenInFlight.set(normalizedParent, requestPromise)
  try {
    return await requestPromise
  } finally {
    folderChildrenInFlight.delete(normalizedParent)
  }
}

const loadTreeChildren = async (node, resolve) => {
  const parentPath = node?.level === 0 ? '' : (node?.data?.path || '')
  try {
    const children = await fetchFolderChildren(parentPath)
    resolve(children)
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || '读取子目录失败')
    resolve([])
  }
}

const refreshAffectedNodeChildren = async (parentPath = '') => {
  const normalizedParent = normalizePath(parentPath)
  const children = await fetchFolderChildren(normalizedParent)

  if (!normalizedParent) {
    treeData.value = children
    return
  }

  const tree = treeRef.value
  const parentNode = tree?.getNode?.(normalizedParent)
  if (tree && parentNode) {
    tree.updateKeyChildren(normalizedParent, children)
  }
}

const hideContextMenu = () => {
  contextMenuVisible.value = false
}

const hideFileContextMenu = () => {
  fileContextMenuVisible.value = false
  fileContextTarget.value = null
}

const hideAllContextMenus = () => {
  hideContextMenu()
  hideFileContextMenu()
}

const showContextMenu = (event, path = '') => {
  event.preventDefault()
  hideFileContextMenu()
  const normalizedPath = normalizePath(path)

  // 非超管不允许在顶层存储（根目录）触发右键菜单。
  if (!normalizedPath && !isSuperAdminUser.value) {
    hideContextMenu()
    return
  }

  if (isViewPermissionUser.value) {
    hideContextMenu()
    return
  }
  if (normalizedPath && !hasFolderAccess(normalizedPath)) {
    hideContextMenu()
    return
  }

  contextTargetPath.value = normalizedPath

  const container = event.currentTarget?.closest?.('.left-panel')
    || event.target?.closest?.('.tree-wrap')
    || event.target?.closest?.('.left-panel')
    || leftPanelRef.value
  const rect = container?.getBoundingClientRect?.()
  const left = rect ? event.clientX - rect.left : 0
  const top = rect ? event.clientY - rect.top : 0

  contextMenuStyle.value = {
    left: `${left}px`,
    top: `${top}px`,
  }
  contextMenuVisible.value = true
}

const showFileContextMenu = (event, row) => {
  event.preventDefault()
  hideContextMenu()

  fileContextTarget.value = row || null
  const container = event.target?.closest?.('.file-table-wrap')
  const rect = container?.getBoundingClientRect?.()
  const left = rect ? event.clientX - rect.left : 0
  const top = rect ? event.clientY - rect.top : 0

  fileContextMenuStyle.value = {
    left: `${left}px`,
    top: `${top}px`,
  }
  fileContextMenuVisible.value = true
}

const onPanelContextMenu = (event) => {
  showContextMenu(event, '')
}

const onLeftPanelContextMenu = (event) => {
  const target = event?.target
  if (target?.closest?.('.tree-node-content') || target?.closest?.('.panel-title')) {
    return
  }
  showContextMenu(event, '')
}

const onTreeNodeContextMenu = (event, data) => {
  onTreeNodeClick(data)
  showContextMenu(event, data?.path || '')
}

const handleContextCommand = async (command) => {
  const targetPath = contextTargetPath.value || ''
  hideContextMenu()

  if (command === 'refresh') {
    await reloadTree()
    return
  }
  if (command === 'create') {
    await createFolder(targetPath)
    return
  }
  if (command === 'rename') {
    await renameFolder(targetPath)
    return
  }
  if (command === 'delete') {
    await deleteFolder(targetPath)
  }
}

const onFileCellContextMenu = (event, row) => {
  if (isViewPermissionUser.value) {
    hideFileContextMenu()
    return
  }

  if (!row?.file_path) {
    return
  }
  showFileContextMenu(event, row)
}

const handleFileContextCommand = async (command) => {
  const row = fileContextTarget.value
  hideFileContextMenu()

  if (!row?.file_path) {
    return
  }

  if (command === 'delete') {
    await deleteFileRow(row)
    return
  }

  if (command === 'rename') {
    await renameFileRow(row)
    return
  }

  if (command === 'move') {
    await openMoveFileDialog(row)
  }
}

const resetMoveFileDialog = () => {
  moveFileSourceRow.value = null
  moveFileTargetPath.value = ''
  movingFile.value = false
}

const onMoveTargetNodeClick = (node) => {
  moveFileTargetPath.value = normalizePath(node?.path || '')
}

const openMoveFileDialog = async (row) => {
  const filePath = String(row?.file_path || '').trim()
  if (!filePath) {
    return
  }

  moveFileSourceRow.value = row
  moveFileTargetPath.value = selectedFolderPath.value || ''
  moveFileDialogVisible.value = true

  await nextTick()
  if (moveFileTargetPath.value) {
    moveTargetTreeRef.value?.setCurrentKey?.(normalizePath(moveFileTargetPath.value))
  } else {
    moveTargetTreeRef.value?.setCurrentKey?.(null)
  }
}

const confirmMoveFile = async () => {
  if (movingFile.value) {
    return
  }

  const sourcePath = String(moveFileSourcePath.value || '').trim()
  if (!sourcePath) {
    ElMessage.warning('源文件路径为空')
    return
  }

  const targetPath = normalizePath(moveFileTargetPath.value)
  const sourceFolderPath = getParentPath(sourcePath)
  if (sourceFolderPath === targetPath) {
    ElMessage.warning('目标目录与当前目录一致，无需移动')
    return
  }

  movingFile.value = true
  try {
    const { data } = await http.put('/folders/file/move', {
      path: sourcePath,
      target_folder_path: targetPath,
    })

    const newPath = String(data?.path || '').trim()
    if (previewRow.value?.file_path === sourcePath && newPath) {
      previewRow.value = {
        ...(previewRow.value || {}),
        file_path: newPath,
        name: newPath.split('/').pop() || previewRow.value?.name,
      }
    }

    moveFileDialogVisible.value = false
    await loadFolderFiles(selectedFolderPath.value)
    await loadRecursiveFileCount(selectedFolderPath.value)

    const affectedCount = Number(data?.affected_contract_count) || 0
    ElMessage.success(`移动成功，已同步 ${affectedCount} 个关联合同文件路径`)
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || '移动文件失败')
  } finally {
    movingFile.value = false
  }
}

const applySearch = () => {
  activeKeyword.value = String(searchKeyword.value || '').trim().toLowerCase()
}

const filteredFiles = computed(() => {
  if (noPermissionForSelectedFolder.value) {
    return []
  }

  const keyword = activeKeyword.value
  if (!keyword) {
    return files.value
  }

  return files.value.filter((row) => {
    const text = [
      row?.name,
      row?.file_path,
      row?.modified_by,
      formatFileModifiedTime(row?.mtime),
      row?.contract_name,
      row?.contract_number,
      row?.contract_unit,
      row?.contract_amount,
      row?.copy_count,
      row?.handler,
      row?.handling_department,
      row?.handling_date,
      row?.contract_type,
      row?.purchase_type,
      row?.stamp_tax_rate,
      row?.save_place,
      row?.is_archived,
      row?.project,
      formatOriginalContractLabel(row),
    ]
      .map((item) => String(item || '').toLowerCase())
      .join(' ')

    return text.includes(keyword)
  })
})

const currentFileCount = computed(() => {
  return Array.isArray(files.value) ? files.value.length : 0
})

const moveFileSourcePath = computed(() => {
  return String(moveFileSourceRow.value?.file_path || '').trim()
})

const moveFileSourceName = computed(() => {
  return String(moveFileSourceRow.value?.name || '').trim()
})

const fileColumnAutoWidth = computed(() => {
  const base = 210
  const maxLen = filteredFiles.value.reduce((acc, row) => {
    const len = String(row?.name || '').length
    return len > acc ? len : acc
  }, 0)
  const estimated = Math.max(base, maxLen * 14 + 56)
  return Math.min(estimated, 560)
})

const fileColumnWidth = computed(() => {
  if (fileColumnManualWidth.value > 0) {
    return fileColumnManualWidth.value
  }
  return fileColumnAutoWidth.value
})

const onTableHeaderDragEnd = (newWidth, _oldWidth, column) => {
  const key = column?.columnKey || column?.property || ''
  if (key !== 'fileName') {
    return
  }
  const width = Number(newWidth)
  if (!Number.isFinite(width) || width <= 0) {
    return
  }
  fileColumnManualWidth.value = Math.max(210, Math.round(width))
}

const previewTitle = computed(() => {
  if (!previewRow.value) {
    return '文件预览'
  }
  return `文件预览 - ${previewRow.value.name || ''}`
})

const revokePreviewUrl = () => {
  if (previewUrl.value) {
    window.URL.revokeObjectURL(previewUrl.value)
    previewUrl.value = ''
  }
}

const resetPreview = () => {
  previewRow.value = null
  revokePreviewUrl()
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

const isPdfFile = (filePath) => String(filePath || '').toLowerCase().endsWith('.pdf')

const getFileExt = (filePath) => {
  const text = String(filePath || '').toLowerCase()
  const idx = text.lastIndexOf('.')
  if (idx < 0 || idx === text.length - 1) {
    return ''
  }
  return text.slice(idx + 1)
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

const getMatchedContractId = (row) => {
  if (!row || typeof row !== 'object') {
    return 0
  }
  const fromMatched = Number(row.matched_contract_id)
  if (Number.isInteger(fromMatched) && fromMatched > 0) {
    return fromMatched
  }
  const fromContract = Number(row.contract?.id)
  if (Number.isInteger(fromContract) && fromContract > 0) {
    return fromContract
  }
  return 0
}

const hasRealContractName = (row) => {
  const name = String(row?.contract_name || '').trim()
  return !!name && name !== '<无匹配>' && getMatchedContractId(row) > 0
}

const contractBriefById = computed(() => {
  const map = new Map()
  ;(contractEditorContracts.value || []).forEach((item) => {
    const id = Number(item?.id)
    if (!Number.isInteger(id) || id <= 0) {
      return
    }
    map.set(id, `${item?.contract_number || '无编号'} - ${item?.contract_name || '未命名合同'}`)
  })
  return map
})

const formatOriginalContractLabel = (row) => {
  const direct = row?.original_contract
  if (direct && Number.isInteger(Number(direct?.id))) {
    return `${direct?.contract_number || '无编号'} - ${direct?.contract_name || '未命名合同'}`
  }

  const id = Number(row?.original_contract_id)
  if (!Number.isInteger(id) || id <= 0) {
    return ''
  }

  return contractBriefById.value.get(id) || `ID:${id}`
}

const isArchivedValue = (value) => {
  const text = String(value ?? '').trim().toLowerCase()
  return ['已归档', '是', 'yes', 'true', '1', 'y'].includes(text)
}

const openContractEditFromFileRow = async (row) => {
  const contractId = getMatchedContractId(row)
  if (!contractId) {
    return
  }
  const readOnly = isViewPermissionUser.value || (isArchivedValue(row?.is_archived) && !isSuperAdminUser.value)
  await contractItemRef.value?.openEdit({ id: contractId }, { readOnly })
}

const openCreateFromFileRow = (row) => {
  const filePath = String(row?.file_path || '').trim()
  if (!filePath) {
    ElMessage.warning('当前文件路径为空，无法新建')
    return
  }
  contractItemRef.value?.openCreateWithFilePath(filePath)
}

const resetAiMatchState = () => {
  aiMatchCandidates.value = []
  aiParsedFields.value = null
  aiParsedUploadFile.value = null
  aiMatchSourceRow.value = null
  aiMatchProcessing.value = false
  aiParsingFilePath.value = ''
}

const closeAiMatchDialog = () => {
  aiMatchDialogVisible.value = false
  resetAiMatchState()
}

const startAiMatchFromFileRow = async (row) => {
  const filePath = String(row?.file_path || '').trim()
  if (!filePath) {
    ElMessage.warning('当前文件路径为空，无法AI识别')
    return
  }

  if (!isPdfFile(filePath)) {
    ElMessage.warning('当前文件不是PDF，无法AI识别')
    return
  }

  aiParsingFilePath.value = filePath
  try {
    const { data } = await http.post('/contracts/ai-parse', {
      file_path: filePath,
    }, {
      timeout: 300000,
    })

    const parsedFullbody = data?.fullbody || ''
    const parsedFields = {
      ...(data?.fields || {}),
      fullbody: parsedFullbody,
    }

    aiParsedUploadFile.value = null
    aiParsedFields.value = parsedFields
    aiMatchCandidates.value = Array.isArray(data?.match_candidates) ? data.match_candidates : []
    aiMatchSourceRow.value = row
    aiMatchDialogVisible.value = true
    ElMessage.success('AI解析完成，请确认匹配结果')
  } catch (error) {
    if (error?.code === 'ECONNABORTED') {
      ElMessage.error('AI解析超时，请稍后重试')
      return
    }

    ElMessage.error(error?.response?.data?.message || error?.message || 'AI解析失败')
  } finally {
    aiParsingFilePath.value = ''
  }
}

const proceedAiMatchSelection = async (selectedValue) => {
  const sourceRow = aiMatchSourceRow.value
  const sourceFilePath = String(sourceRow?.file_path || '').trim()
  const parsedFields = aiParsedFields.value || {}

  if (!sourceFilePath) {
    ElMessage.error('源文件路径丢失，请重新操作')
    closeAiMatchDialog()
    return
  }

  aiMatchProcessing.value = true
  try {
    if (selectedValue === AI_NEW_CONTRACT_VALUE) {
      aiMatchDialogVisible.value = false
      contractItemRef.value?.openCreateWithFilePath(sourceFilePath, parsedFields)
      resetAiMatchState()
      return
    }

    const selectedId = Number(selectedValue)
    const matchedRow = aiMatchCandidates.value.find((item) => Number(item?.id) === selectedId)
    if (!matchedRow) {
      ElMessage.warning('请选择要关联的已有合同，或选择“这是新合同”')
      return
    }

    await http.put(`/contracts/${selectedId}`, {
      file_path: sourceFilePath,
    })

    const mergedRow = {
      ...matchedRow,
      file_path: sourceFilePath,
    }

    aiMatchDialogVisible.value = false
    await contractItemRef.value?.openEditWithSupplementalFields(mergedRow, parsedFields)
    ElMessage.success('已关联到已有合同，请确认补充字段后保存')
    resetAiMatchState()
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || '处理失败')
  } finally {
    aiMatchProcessing.value = false
  }
}

const loadDepartments = async () => {
  const { data } = await http.get('/settings/departments')
  departments.value = (Array.isArray(data) ? data : []).map((item) => item.name)
}

const loadCurrentUserFolderPermission = async () => {
  try {
    const { data } = await http.get('/settings/users/current-permission')
    userRole.value = String(data?.role || 'admin').trim() || 'admin'
    userPermission.value = String(data?.permission || 'view').trim() || 'view'
    const folderList = Array.isArray(data?.folder_list) ? data.folder_list : []
    allowedFolderRoots.value = folderList.map((item) => String(item || '').trim()).filter(Boolean)
  } catch (_error) {
    userRole.value = 'admin'
    userPermission.value = 'view'
    allowedFolderRoots.value = []
  }
}

const loadFieldOptions = async () => {
  const { data } = await http.get('/options/contract-fields')
  options.value = {
    contract_form: data?.contract_form || [],
    contract_determination_method: data?.contract_determination_method || [],
    contract_type: data?.contract_type || [],
    purchase_type: data?.purchase_type || [],
    stamp_tax_rate_by_contract_type: data?.stamp_tax_rate_by_contract_type || {},
    pricing_method: data?.pricing_method || [],
    is_archived: data?.is_archived || [],
    project: data?.project || [],
  }
}

const loadContractEditorContracts = async () => {
  const { data } = await http.get('/contracts')
  contractEditorContracts.value = Array.isArray(data) ? data : []
}

const handleContractSaved = async () => {
  await Promise.all([
    loadDepartments(),
    loadContractEditorContracts(),
    loadFieldOptions(),
    loadFolderFiles(selectedFolderPath.value),
  ])
}

const batchMatchInstructionText = () => {
  return [
    '匹配说明：',
    '1. 本次批量匹配文件夹下（不包含子文件夹）“没有关联合同”的文件。',
    '2. 会先按当前文件夹路径里的部门和年份范围，筛出“没有文件且没有归档”的合同作为候选。',
    '3. 如果文件名中包含明确合同编号，会优先按合同编号直接匹配。',
    '4. 否则会把文件名中第1个中文和最后1个中文之间的文本作为关键名称。',
    '5. 关键名称会与候选合同名称进行对比。',
    '6. 若完全一样则直接匹配。',
    '7. 若没有完全一样：',
    '   - 包含关键名称的候选只有1个则直接匹配。',
    '   - 若有多个候选则匹配最相似的第1个。',
    '8. 匹配后会把该合同文件绑定到合同信息中。',
    '',
    `当前目录：${selectedFolderPath.value || '/'}`,
    '',
    '点击下方“开始匹配”执行。',
  ].join('\n')
}

const appendBatchMatchLog = (line = '') => {
  batchMatchLogText.value = `${batchMatchLogText.value}${batchMatchLogText.value ? '\n' : ''}${line}`
}

const openBatchMatchDialog = () => {
  if (!canOperateOnSelectedFolder.value) {
    ElMessage.warning('您没有权限')
    return
  }
  batchMatchLogText.value = batchMatchInstructionText()
  batchMatchDialogVisible.value = true
}

const startBatchMatch = async () => {
  if (batchMatching.value) {
    return
  }

  batchMatching.value = true
  batchMatchLogText.value = batchMatchInstructionText()
  appendBatchMatchLog('')
  appendBatchMatchLog('开始匹配...')

  try {
    const { data } = await http.post('/folders/batch-match', {
      folder_path: selectedFolderPath.value || '',
    }, {
      timeout: 300000,
    })

    const rows = Array.isArray(data?.results) ? data.results : []
    rows.forEach((item, index) => {
      const prefix = `[${index + 1}/${rows.length}]`
      if (item?.status === 'success') {
        appendBatchMatchLog(
          `${prefix} ${item.name || ''} -> 匹配成功: ${item.matched_contract_name || ''} (ID:${item.matched_contract_id || ''}, 规则:${item.match_method || ''})`
        )
      } else {
        appendBatchMatchLog(
          `${prefix} ${item.name || ''} -> 失败: ${item.message || '未匹配'}`
        )
      }
    })

    appendBatchMatchLog('')
    appendBatchMatchLog(`完成：成功 ${data?.success || 0}，失败 ${data?.failed || 0}，总计 ${data?.total || rows.length}`)
    await loadFolderFiles(selectedFolderPath.value)
    ElMessage.success('批量匹配完成')
  } catch (error) {
    appendBatchMatchLog(`执行失败：${error?.response?.data?.message || '请求失败'}`)
    ElMessage.error(error?.response?.data?.message || '批量匹配失败')
  } finally {
    batchMatching.value = false
  }
}

const triggerFolderUpload = () => {
  if (!canOperateOnSelectedFolder.value) {
    ElMessage.warning('您没有权限')
    return
  }

  if (uploadingFolderFiles.value) {
    return
  }
  folderUploadInputRef.value?.click()
}

const readAllDirectoryEntries = async (reader) => {
  const entries = []
  while (true) {
    const chunk = await new Promise((resolve, reject) => {
      reader.readEntries(resolve, reject)
    })
    if (!chunk?.length) {
      break
    }
    entries.push(...chunk)
  }
  return entries
}

const collectDroppedEntryFiles = async (entry, parentPath = '') => {
  if (!entry) {
    return []
  }

  if (entry.isFile) {
    const file = await new Promise((resolve, reject) => {
      entry.file(resolve, reject)
    })
    const relativePath = parentPath ? `${parentPath}/${file.name}` : file.name
    return [{ file, relativePath }]
  }

  if (!entry.isDirectory) {
    return []
  }

  const currentPath = parentPath ? `${parentPath}/${entry.name}` : entry.name
  const reader = entry.createReader()
  const children = await readAllDirectoryEntries(reader)
  const nested = await Promise.all(children.map((child) => collectDroppedEntryFiles(child, currentPath)))
  return nested.flat()
}

const resolveDroppedUploadItems = async (event) => {
  const transfer = event?.dataTransfer
  if (!transfer) {
    return []
  }

  const items = Array.from(transfer.items || [])
  if (items.length && items.some((item) => typeof item?.webkitGetAsEntry === 'function')) {
    const collected = []
    for (const item of items) {
      if (item?.kind !== 'file') {
        continue
      }

      const entry = item.webkitGetAsEntry?.()
      if (entry) {
        const files = await collectDroppedEntryFiles(entry)
        collected.push(...files)
        continue
      }

      const fallbackFile = item.getAsFile?.()
      if (fallbackFile) {
        collected.push({ file: fallbackFile, relativePath: fallbackFile.webkitRelativePath || fallbackFile.name })
      }
    }

    if (collected.length) {
      return collected
    }
  }

  return Array.from(transfer.files || []).map((file) => ({
    file,
    relativePath: file.webkitRelativePath || file.name,
  }))
}

const uploadFilesToFolder = async (picked, targetFolderPath = selectedFolderPath.value) => {
  const normalizedTargetPath = normalizePath(targetFolderPath)
  if (normalizedTargetPath && !hasFolderAccess(normalizedTargetPath)) {
    ElMessage.warning('您没有权限')
    return
  }
  if (!normalizedTargetPath && !hasAllFolderPermission.value) {
    ElMessage.warning('您没有权限')
    return
  }

  const filesToUpload = Array.from(picked || [])
    .map((item) => {
      if (item instanceof File) {
        return {
          file: item,
          relativePath: item.webkitRelativePath || item.name,
        }
      }

      const file = item?.file
      if (!(file instanceof File)) {
        return null
      }

      return {
        file,
        relativePath: String(item?.relativePath || file.webkitRelativePath || file.name || ''),
      }
    })
    .filter((item) => item && String(item.file?.name || '').trim())

  if (!filesToUpload.length) {
    ElMessage.warning('请选择有效文件')
    return
  }

  const isFolderUpload = filesToUpload.some((item) => {
    const relativePath = String(item?.relativePath || '').replace(/\\/g, '/').replace(/^\/+/, '')
    const idx = relativePath.lastIndexOf('/')
    return idx > 0
  })

  uploadingFolderFiles.value = true
  try {
    const fd = new FormData()
    fd.append('folder_path', normalizedTargetPath)
    filesToUpload.forEach((item) => {
      const relativePath = String(item.relativePath || '')
        .replace(/\\/g, '/')
        .replace(/^\/+/, '')

      fd.append('files', item.file)
      fd.append('relative_paths', relativePath)
    })

    const { data } = await http.post('/folders/upload', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 300000,
    })

    if (isFolderUpload) {
      await reloadTree()
    } else {
      await loadFolderFiles(selectedFolderPath.value)
    }
    const uploadedCount = Number(data?.uploaded_count) || filesToUpload.length
    ElMessage.success(`上传成功，共 ${uploadedCount} 个文件`)
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || '文件上传失败')
  } finally {
    uploadingFolderFiles.value = false
  }
}

const handleFolderFilesSelected = async (event) => {
  const picked = Array.from(event?.target?.files || [])
  if (!picked.length) {
    return
  }
  await uploadFilesToFolder(picked, selectedFolderPath.value)
  event.target.value = ''
}

const hasDraggedFiles = (event) => {
  const transfer = event?.dataTransfer
  if (!transfer) {
    return false
  }

  if (Number(transfer?.files?.length) > 0) {
    return true
  }

  const items = Array.from(transfer?.items || [])
  if (items.some((item) => item?.kind === 'file')) {
    return true
  }

  const types = Array.from(transfer?.types || [])
  return types.includes('Files') || types.includes('application/x-moz-file')
}

const isDropInTreeWrap = (target) => {
  return !!(target && treeWrapRef.value?.contains?.(target))
}

const isDropInLeftPanel = (target) => {
  return !!(target && leftPanelRef.value?.contains?.(target))
}

const isDropInRightPanel = (target) => {
  return !!(target && rightPanelRef.value?.contains?.(target))
}

const isDropInFileTableWrap = (target) => {
  return !!(target && fileTableWrapRef.value?.contains?.(target))
}

const getDragHoverNodePath = (event) => {
  const nodeEl = event?.target?.closest?.('.tree-node-content')
  return normalizePath(nodeEl?.dataset?.path || '')
}

const onTreeDragOver = (event) => {
  if (!hasDraggedFiles(event) || uploadingFolderFiles.value) {
    return
  }
  event.dataTransfer.dropEffect = 'copy'
  dragOverNodePath.value = getDragHoverNodePath(event)
}

const onTreeDragLeave = (event) => {
  const nextTarget = event?.relatedTarget
  if (!event?.currentTarget?.contains?.(nextTarget)) {
    dragOverNodePath.value = ''
  }
}

const onTreeDrop = async (event) => {
  const hoveredPath = getDragHoverNodePath(event)
  const filesFromDrop = await resolveDroppedUploadItems(event)
  dragOverNodePath.value = ''
  if (!filesFromDrop.length) {
    return
  }
  const targetPath = hoveredPath || selectedFolderPath.value
  await uploadFilesToFolder(filesFromDrop, targetPath)
}

const onFileTableDragOver = (event) => {
  if (!hasDraggedFiles(event) || uploadingFolderFiles.value) {
    return
  }
  event.dataTransfer.dropEffect = 'copy'
}

const onFileTableDrop = async (event) => {
  const filesFromDrop = await resolveDroppedUploadItems(event)
  if (!filesFromDrop.length) {
    return
  }
  await uploadFilesToFolder(filesFromDrop, selectedFolderPath.value)
}

const onWindowDragOverCapture = (event) => {
  if (!hasDraggedFiles(event)) {
    return
  }
  event.preventDefault()
  if (event.dataTransfer) {
    event.dataTransfer.dropEffect = 'copy'
  }
}

const onWindowDropCapture = async (event) => {
  if (!hasDraggedFiles(event) || uploadingFolderFiles.value) {
    return
  }

  event.preventDefault()
  event.stopPropagation()

  const target = event?.target
  const filesFromDrop = await resolveDroppedUploadItems(event)
  if (!filesFromDrop.length) {
    dragOverNodePath.value = ''
    return
  }

  if (isDropInLeftPanel(target)) {
    const hoveredPath = getDragHoverNodePath(event)
    dragOverNodePath.value = ''
    await uploadFilesToFolder(filesFromDrop, hoveredPath || selectedFolderPath.value)
    return
  }

  if (isDropInRightPanel(target) || isDropInFileTableWrap(target)) {
    await uploadFilesToFolder(filesFromDrop, selectedFolderPath.value)
    return
  }

  dragOverNodePath.value = ''
}



const loadFolderFiles = async (folderPath) => {
  const normalizedPath = normalizePath(folderPath)
  if (!normalizedPath && !hasAllFolderPermission.value) {
    selectedFolderPath.value = ''
    files.value = []
    noPermissionForSelectedFolder.value = true
    loadingFiles.value = false
    return
  }
  if (normalizedPath && !hasFolderAccess(normalizedPath)) {
    selectedFolderPath.value = normalizedPath
    files.value = []
    noPermissionForSelectedFolder.value = true
    loadingFiles.value = false
    return
  }

  noPermissionForSelectedFolder.value = false
  loadingFiles.value = true
  try {
    const { data } = await http.get('/folders/files', {
      params: { folder_path: normalizedPath || '' },
    })
    selectedFolderPath.value = data?.folder_path || ''
    files.value = Array.isArray(data?.files) ? data.files : []
  } catch (error) {
    files.value = []
    ElMessage.error(error?.response?.data?.message || '读取文件失败')
  } finally {
    loadingFiles.value = false
  }
}

const goToRootFolder = async () => {
  await loadFolderFiles('')
  await nextTick()
  treeRef.value?.setCurrentKey?.(null)
}



const loadRecursiveFileCount = async (folderPath) => {
  const token = ++recursiveCountToken
  loadingRecursiveCount.value = true

  try {
    const { data } = await http.get('/folders/file-count', {
      params: { folder_path: normalizePath(folderPath) },
    })
    const total = Number(data?.total_files) || 0
    if (token !== recursiveCountToken) {
      return
    }
    recursiveFileCount.value = total
  } catch (_error) {
    if (token !== recursiveCountToken) {
      return
    }
    recursiveFileCount.value = 0
  } finally {
    if (token === recursiveCountToken) {
      loadingRecursiveCount.value = false
    }
  }
}


watch(selectedFolderPath, (path) => {
  const normalizedPath = normalizePath(path)
  if (normalizedPath && !hasFolderAccess(normalizedPath)) {
    recursiveFileCount.value = 0
    loadingRecursiveCount.value = false
    return
  }
  loadRecursiveFileCount(path)
}, { immediate: true })

const loadTree = async (keepSelected = true) => {
  loadingTree.value = true
  try {
    clearFolderChildrenRequestCache()
    const { data } = await http.get('/folders/tree')
    const root = data?.root || { name: '/', path: '' }
    rootName.value = root.name || '/'
    // Root folder name is shown in the title; tree only shows root children.
    treeData.value = await fetchFolderChildren('')
    treeRenderKey.value += 1

    const nextPath = keepSelected ? normalizePath(selectedFolderPath.value) : ''
    await loadFolderFiles(nextPath)
    await nextTick()
    if (nextPath) {
      treeRef.value?.setCurrentKey?.(nextPath)
    }
  } catch (error) {
    treeData.value = []
    files.value = []
    ElMessage.error(error?.response?.data?.message || '读取目录树失败')
  } finally {
    loadingTree.value = false
  }
}

const onTreeNodeClick = async (node) => {
  const nodePath = normalizePath(node?.path || '')
  if (nodePath && !hasFolderAccess(nodePath)) {
    selectedFolderPath.value = nodePath
    files.value = []
    noPermissionForSelectedFolder.value = true
    ElMessage.warning('您没有权限')
    return
  }

  await loadFolderFiles(nodePath)
}

const reloadTree = async () => {
  await loadTree(true)
}

const createFolder = async (targetPath = selectedFolderPath.value) => {
  const normalizedTarget = normalizePath(targetPath)
  try {
    const { value } = await ElMessageBox.prompt('请输入新文件夹名称', '新建文件夹', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      inputPlaceholder: '文件夹名称',
      inputValidator: (val) => {
        if (!String(val || '').trim()) {
          return '文件夹名称不能为空'
        }
        if (/[/\\]/.test(val)) {
          return '文件夹名称不能包含斜杠'
        }
        return true
      },
    })

    await http.post('/folders', {
      parent_path: normalizedTarget,
      name: value,
    })

    ElMessage.success('新建成功')
    await refreshAffectedNodeChildren(normalizedTarget)
    await nextTick()
    if (selectedFolderPath.value) {
      treeRef.value?.setCurrentKey?.(normalizePath(selectedFolderPath.value))
    }
  } catch (error) {
    if (error === 'cancel' || error === 'close') {
      return
    }
    ElMessage.error(error?.response?.data?.message || '新建文件夹失败')
  }
}

const confirmForceDeleteFolder = async (folderPath, fileCount) => {
  const dialogClass = `force-delete-confirm-dialog-${Date.now()}`
  let remaining = 10

  const cleanupFns = []
  const updateDialogCountdown = () => {
    const root = document.querySelector(`.${dialogClass}`)
    if (!root) {
      return
    }

    const countEl = root.querySelector('.force-delete-countdown-value')
    if (countEl) {
      countEl.textContent = String(remaining)
    }

    const btnTextEl = root.querySelector('.el-message-box__btns .el-button--primary span')
    if (btnTextEl) {
      btnTextEl.textContent = `彻底删除 (${remaining}s)`
    }
  }

  const intervalId = window.setInterval(() => {
    remaining = Math.max(0, remaining - 1)
    updateDialogCountdown()
  }, 1000)
  cleanupFns.push(() => window.clearInterval(intervalId))

  const timeoutId = window.setTimeout(() => {
    ElMessageBox.close()
  }, 10_000)
  cleanupFns.push(() => window.clearTimeout(timeoutId))

  await nextTick()

  try {
    await ElMessageBox.confirm(
      `文件夹下存在 ${Number(fileCount) || 0} 个文件，是否彻底删除？<br><span class="force-delete-countdown-tip">${remaining} 秒后自动取消</span>`,
      `彻底删除确认：${folderPath}`,
      {
        confirmButtonText: `彻底删除 (${remaining}s)`,
        cancelButtonText: '取消',
        type: 'warning',
        dangerouslyUseHTMLString: true,
        customClass: dialogClass,
        distinguishCancelAndClose: true,
      },
    )
  } finally {
    cleanupFns.forEach((fn) => fn())
  }
}

const applyFolderDeletedState = async (folderPath) => {
  const parentPath = getParentPath(folderPath)
  selectedFolderPath.value = parentPath
  await refreshAffectedNodeChildren(parentPath)
  await loadFolderFiles(parentPath)
  await nextTick()
  if (parentPath) {
    treeRef.value?.setCurrentKey?.(parentPath)
  } else {
    treeRef.value?.setCurrentKey?.(null)
  }
}

const deleteFolder = async (targetPath = selectedFolderPath.value) => {
  const folderPath = normalizePath(targetPath)
  if (!folderPath) {
    ElMessage.warning('根目录不允许删除')
    return
  }

  try {
    await ElMessageBox.confirm(
      `确认删除文件夹「${folderPath}」吗？`,
      '删除确认',
      {
        confirmButtonText: '删除',
        cancelButtonText: '取消',
        type: 'warning',
      },
    )

    await http.delete('/folders', {
      data: { path: folderPath },
    })

    ElMessage.success('删除成功')
    await applyFolderDeletedState(folderPath)
  } catch (error) {
    if (error === 'cancel' || error === 'close') {
      return
    }

    const status = Number(error?.response?.status || 0)
    const message = String(error?.response?.data?.message || '')
    const canForceDelete = status === 409 && (message.includes('该文件夹下存在文件') || message.includes('该文件夹下存在子文件夹'))

    if (canForceDelete) {
      let totalFiles = 0
      try {
        const { data } = await http.get('/folders/file-count', {
          params: { folder_path: folderPath },
        })
        totalFiles = Number(data?.total_files) || 0
      } catch (_countError) {
        totalFiles = 0
      }

      try {
        await confirmForceDeleteFolder(folderPath, totalFiles)
      } catch (confirmError) {
        if (confirmError === 'cancel' || confirmError === 'close') {
          return
        }
        throw confirmError
      }

      try {
        const { data } = await http.delete('/folders', {
          data: {
            path: folderPath,
            force: true,
          },
        })
        const affected = Number(data?.affected_contract_count) || 0
        ElMessage.success(`已彻底删除，清理 ${affected} 条关联合同文件路径`)
        await applyFolderDeletedState(folderPath)
        return
      } catch (forceError) {
        ElMessage.error(forceError?.response?.data?.message || '彻底删除文件夹失败')
        return
      }
    }

    ElMessage.error(error?.response?.data?.message || '删除文件夹失败')
  }
}

const renameFolder = async (targetPath = selectedFolderPath.value) => {
  const folderPath = normalizePath(targetPath)
  if (!folderPath) {
    ElMessage.warning('根目录不允许重命名')
    return
  }

  try {
    const { value } = await ElMessageBox.prompt('请输入新的文件夹名称', '重命名文件夹', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      inputPlaceholder: '新文件夹名称',
      inputValidator: (val) => {
        if (!String(val || '').trim()) {
          return '文件夹名称不能为空'
        }
        if (/[/\\]/.test(val)) {
          return '文件夹名称不能包含斜杠'
        }
        return true
      },
    })

    await http.put('/folders', {
      path: folderPath,
      name: value,
    })

    ElMessage.success('重命名成功')
    const parentPath = getParentPath(folderPath)
    await refreshAffectedNodeChildren(parentPath)
    await nextTick()
    const newPath = parentPath ? `${parentPath}/${value}` : value
    if (selectedFolderPath.value === folderPath) {
      selectedFolderPath.value = newPath
    }
    treeRef.value?.setCurrentKey?.(newPath)
  } catch (error) {
    if (error === 'cancel' || error === 'close') {
      return
    }
    ElMessage.error(error?.response?.data?.message || '重命名文件夹失败')
  }
}

const downloadFile = async (row) => {
  if (!row?.file_path) {
    return
  }

  try {
    const response = await http.get('/folders/file-download', {
      params: { path: row.file_path },
      responseType: 'blob',
    })
    const headerName = parseFilenameFromDisposition(response.headers?.['content-disposition'])
    triggerBrowserDownload(response.data, headerName || row.name || 'download.bin')
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || '下载失败')
  }
}

const openFilePreview = (row, event) => {
  event?.preventDefault?.()
  event?.stopPropagation?.()

  if (!row?.file_path) {
    return
  }

  if (!isPdfFile(row.file_path)) {
    ElMessage.warning('仅支持PDF预览，请使用下载功能')
    return
  }

  const previewUrl = buildOcrPreviewUrlFromFilePath(row.file_path)
  if (!previewUrl) {
    ElMessage.warning('预览地址无效')
    return
  }

  const opened = window.open(previewUrl, '_blank', 'noopener,noreferrer')
  if (!opened) {
    ElMessage.warning('浏览器拦截了新窗口，请允许弹窗后重试')
  }
}

const deleteFileRow = async (row) => {
  const filePath = String(row?.file_path || '').trim()
  const fileName = row?.name || filePath
  if (!filePath) {
    return
  }

  try {
    await ElMessageBox.confirm(
      `确认删除文件「${fileName}」吗？\n删除后会自动清空关联合同的 file_path。`,
      '删除确认',
      {
        confirmButtonText: '删除',
        cancelButtonText: '取消',
        type: 'warning',
      },
    )

    const { data } = await http.delete('/folders/file', {
      data: { path: filePath },
    })

    if (previewRow.value?.file_path === filePath) {
      previewDialogVisible.value = false
      resetPreview()
    }

    await loadFolderFiles(selectedFolderPath.value)
    const affectedCount = Number(data?.affected_contract_count) || 0
    ElMessage.success(`删除成功，已清空 ${affectedCount} 个关联合同文件路径`)
  } catch (error) {
    if (error === 'cancel' || error === 'close') {
      return
    }
    ElMessage.error(error?.response?.data?.message || '删除文件失败')
  }
}

const renameFileRow = async (row) => {
  const filePath = String(row?.file_path || '').trim()
  if (!filePath) {
    return
  }

  try {
    const { value } = await ElMessageBox.prompt('请输入新的文件名', '重命名文件', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      inputPlaceholder: '新文件名',
      inputValue: String(row?.name || ''),
      inputValidator: (val) => {
        if (!String(val || '').trim()) {
          return '文件名不能为空'
        }
        if (/[/\\]/.test(val)) {
          return '文件名不能包含斜杠'
        }
        return true
      },
    })

    const { data } = await http.put('/folders/file', {
      path: filePath,
      name: value,
    })

    const newPath = String(data?.path || '').trim()
    const newName = String(value || '').trim()
    if (previewRow.value?.file_path === filePath) {
      previewRow.value = {
        ...(previewRow.value || {}),
        file_path: newPath || filePath,
        name: newName,
      }
    }

    await loadFolderFiles(selectedFolderPath.value)
    const affectedCount = Number(data?.affected_contract_count) || 0
    ElMessage.success(`改名成功，已同步 ${affectedCount} 个关联合同文件路径`)
  } catch (error) {
    if (error === 'cancel' || error === 'close') {
      return
    }
    ElMessage.error(error?.response?.data?.message || '重命名文件失败')
  }
}

const onPdfRenderFailed = () => {
  ElMessage.warning('PDF 渲染失败，请尝试下载原文件')
}

const onPanelResizeMove = (event) => {
  if (!isResizingPanels.value) {
    return
  }

  const layout = folderLayoutRef.value
  if (!layout) {
    return
  }

  const rect = layout.getBoundingClientRect()
  const minWidth = 160
  const maxWidth = Math.max(minWidth, rect.width - 320)
  let nextWidth = event.clientX - rect.left

  if (nextWidth < minWidth) {
    nextWidth = minWidth
  }
  if (nextWidth > maxWidth) {
    nextWidth = maxWidth
  }

  leftPanelWidth.value = Math.round(nextWidth)
}

const stopPanelResize = () => {
  if (!isResizingPanels.value) {
    return
  }

  isResizingPanels.value = false
  document.body.classList.remove('is-resizing-panels')
  window.removeEventListener('mousemove', onPanelResizeMove)
  window.removeEventListener('mouseup', stopPanelResize)
}

const startPanelResize = () => {
  if (window.matchMedia('(max-width: 1100px)').matches) {
    return
  }

  isResizingPanels.value = true
  document.body.classList.add('is-resizing-panels')
  window.addEventListener('mousemove', onPanelResizeMove)
  window.addEventListener('mouseup', stopPanelResize)
}

onMounted(async () => {
  window.addEventListener('click', hideAllContextMenus)
  window.addEventListener('dragover', onWindowDragOverCapture, true)
  window.addEventListener('drop', onWindowDropCapture, true)
  await loadCurrentUserFolderPermission()
  await Promise.all([
    loadDepartments(),
    loadContractEditorContracts(),
    loadFieldOptions(),
    loadTree(false),
  ])
})

onBeforeUnmount(() => {
  window.removeEventListener('click', hideAllContextMenus)
  window.removeEventListener('dragover', onWindowDragOverCapture, true)
  window.removeEventListener('drop', onWindowDropCapture, true)
  stopPanelResize()
})

watch(previewDialogVisible, (visible) => {
  if (!visible) {
    resetPreview()
  }
})


</script>

<style scoped>
.folder-page {
  border-radius: 12px;
}

.folder-page :deep(.el-card) {
  border-radius: 12px;
  overflow: hidden;
}

.folder-layout {
  display: grid;
  gap: 0;
}

.left-panel,
.right-panel {
  border: 1px solid #ebeef5;
  border-radius: 8px;
  padding: 12px;
  background: #fff;
  min-height: 68vh;
}

.left-panel {
  position: relative;
  border-right: 0;
  border-top-right-radius: 0;
  border-bottom-right-radius: 0;
}

.right-panel {
  border-left: 0;
  border-top-left-radius: 0;
  border-bottom-left-radius: 0;
}

.panel-splitter {
  position: relative;
  cursor: col-resize;
}

.panel-splitter::before {
  content: '';
  position: absolute;
  top: 0;
  bottom: 0;
  left: 50%;
  width: 1px;
  transform: translateX(-50%);
  background: #d1d5db;
}

.panel-splitter:hover::before,
.panel-splitter-active::before {
  background: #2563eb;
}

:global(body.is-resizing-panels) {
  cursor: col-resize;
  user-select: none;
}

.tree-wrap {
  position: relative;
}

.file-table-wrap {
  position: relative;
}

.tree-wrap :deep(.el-tree-node__expand-icon) {
  display: none;
}

.tree-node-content {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border-radius: 4px;
  transition: background-color 0.15s ease;
}

.tree-node-drop-active {
  background: #dbeafe;
}

.tree-folder-icon {
  font-size: 16px;
  line-height: 1;
}

.tree-wrap :deep(.el-tree-node__content > .el-tree-node__loading-icon ~ .tree-node-content .tree-folder-icon),
.tree-wrap :deep(.el-tree-node__content > .el-tree-node__expand-icon.is-loading ~ .tree-node-content .tree-folder-icon) {
  display: none;
}

.tree-node-label {
  color: #374151;
}

.tree-context-menu {
  position: absolute;
  z-index: 20;
  min-width: 140px;
  background: #ffffff;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12);
  padding: 6px;
}

.file-context-menu {
  position: absolute;
  z-index: 30;
  min-width: 120px;
  background: #ffffff;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12);
  padding: 6px;
}

.menu-item {
  width: 100%;
  border: 0;
  background: transparent;
  text-align: left;
  padding: 8px 10px;
  border-radius: 6px;
  cursor: pointer;
  color: #111827;
}

.menu-item:hover {
  background: #f3f4f6;
}

.menu-item:disabled {
  color: #9ca3af;
  cursor: not-allowed;
}

.menu-item-danger {
  color: #b91c1c;
}

.panel-title-main {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
  color: #374151;
  font-weight: 600;
}

.root-folder-trigger {
  border: 0;
  background: transparent;
  color: #4b5563;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  line-height: 1;
  padding: 4px 0 0 1px;
}

.root-folder-trigger:hover {
  color: #2563eb;
}

.panel-title {
  display:flex;
  gap:24px;
  
}

.panel-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}

.panel-title-block {
  min-width: 0;
}

.panel-title-row .panel-title {
  margin-bottom: 0;
}

.panel-subtitle {
  margin-top: 4px;
  color: #6b7280;
  font-size: 12px;
  line-height: 1.4;
}

.panel-title-actions {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.apple-button-group {
  display: inline-flex;
  border-radius: 19px;
  padding: 2px;
  background: rgba(255, 255, 255, 0.9);
  border: 1px solid rgba(15, 23, 42, 0.08);
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.12), 0 2px 6px rgba(15, 23, 42, 0.08);
}

.apple-button-group :deep(.el-button) {
  border: none;
  border-radius: 0;
  min-height: 34px;
  position: relative;
  color: #1f2937;
  background: linear-gradient(180deg, #ffffff 0%, #f9fefa 100%);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.95);
  transition: background 0.2s ease, color 0.2s ease, transform 0.2s ease;
}

.apple-button-group :deep(.el-button + .el-button) {
  margin-left: 0;
}

.apple-button-group :deep(.el-button + .el-button::before) {
  content: '';
  position: absolute;
  left: 0;
  top: 6px;
  bottom: 6px;
  width: 1px;
  background: rgba(15, 23, 42, 0.12);
  pointer-events: none;
}

.apple-button-group :deep(.el-button:first-child) {
  border-top-left-radius: 12px;
  border-bottom-left-radius: 12px;
}

.apple-button-group :deep(.el-button:last-child) {
  border-top-right-radius: 12px;
  border-bottom-right-radius: 12px;
}

.apple-button-group :deep(.el-button:hover),
.apple-button-group :deep(.el-button:focus-visible) {
  background: linear-gradient(180deg, #ffffff 0%, #e9eef8 100%);
  color: #1d4ed8;
}

.apple-button-group :deep(.el-button:active) {
  transform: translateY(1px);
}

.folder-upload-input {
  display: none;
}

.batch-match-log :deep(textarea) {
  font-family: Consolas, 'Courier New', monospace;
  line-height: 1.55;
}

.move-dialog-content {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.move-dialog-row {
  font-size: 13px;
  color: #374151;
  word-break: break-all;
}

.move-dialog-label {
  color: #6b7280;
}

.move-dialog-actions {
  display: flex;
  justify-content: flex-start;
}

.move-target-tree {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 8px;
  max-height: 48vh;
  overflow: auto;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 12px;
}

.card-main {
  min-width: 0;
  flex: 1;
  display: flex;

}

.card-title {

  font-size: 18px;
  font-weight: 600;
  text-align: left;
  margin-right:10px;
}

.card-subtitle {
    flex:1;
  margin-top: 4px;
  color: #6b7280;
  font-size: 13px;
  text-align: left;
  word-break: break-all;
}

.header-actions {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  margin-left: auto;
}

.header-search {
  width: 260px;
}

.file-cell {
  display: inline-flex;
  width: 100%;
  max-width: 100%;
  justify-content: flex-start;
  text-align: left;
}

.file-cell-inner {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  min-width: 0;
  overflow: hidden;
}

.file-table :deep(.el-table__header-wrapper th.el-table__cell.is-leaf) {
  border-right: 1px solid #dcdfe6;
}

.file-table :deep(.el-table__header-wrapper th.el-table__cell.is-leaf:last-child) {
  border-right: none;
}

.file-table :deep(.el-table__header-wrapper th.el-table__cell) {
  user-select: none;
}

.file-table-empty {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: #6b7280;
  font-size: 13px;
}

.file-table-empty-icon {
  font-size: 18px;
  color: #9ca3af;
}

.file-list-no-permission {
  min-height: 240px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #6b7280;
  font-size: 14px;
}

.file-icon {
  flex: 0 0 18px;
  width: 18px;
  height: 18px;
}

.file-name {
  display: block;
  flex: 1 1 auto;
  min-width: 0;
  max-width: none;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  text-align: left;
}

.contract-name-link {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 6px;
  width: 100%;
  max-width: 100%;
  min-width: 0;
  font-size: 12px;
  text-align: left;
}

.contract-name-text {
  display: block;
  flex: 1 1 auto;
  min-width: 0;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  text-align: left;
}

.unmatched-contract-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  width: 100%;
  max-width: 100%;
  min-width: 0;
}

.contract-name-cell {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  width: 100%;
  min-width: 0;
  text-align: left;
}

.file-table :deep(.contract-number-col .cell) {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.archive-status-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  font-size: 13px;
  font-weight: 700;
  line-height: 1;
  border-radius: 50%;
}

.archive-status-icon-archived {
  color: #16a34a;
}

.archive-status-icon-unarchived {
  color: #9ca3af;
}

.action-buttons {
  display: inline-flex;
  gap: 6px;
}

.preview-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding-right: 32px;
}

.preview-title {
  min-width: 0;
  font-size: 18px;
  font-weight: 600;
  color: #111827;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.preview-wrapper {
  height: 88vh;
  overflow: auto;
  background: #f8fafc;
  border-radius: 8px;
  padding: 16px;
  box-sizing: border-box;
}

.pdf-preview-embed {
  max-width: 1400px;
  margin: 0 auto;
}

.pdf-preview-embed :deep(canvas) {
  width: 100% !important;
  height: auto !important;
  display: block;
  margin: 0 auto 12px;
}

.preview-placeholder {
  min-height: 60vh;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #6b7280;
}

@media (max-width: 1100px) {
  .folder-layout {
    grid-template-columns: 1fr;
    gap: 16px;
  }

  .panel-splitter {
    display: none;
  }

  .left-panel,
  .right-panel {
    min-height: auto;
    border: 1px solid #ebeef5;
    border-radius: 8px;
  }
}
</style>

<!--
  Icon imports for archive and help icons from iconify/mdi.
  These are not included in the main file because they are not used in the main code.
  They are only used in the preview and help sections.
  You can import them directly in your project.
  For example:
  import mdiArchive from '@iconify-icons/mdi/archive-check-outline'
  import mdiHelp from '@iconify-icons/mdi/help-circle-outline'
-->


