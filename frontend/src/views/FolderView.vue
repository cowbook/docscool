<template>
  <div class="folder-page">
    <el-card>
      <template #header>
        <div class="card-header">
          <div class="card-main">
            <div class="card-title">文件夹</div>
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

      <div class="folder-layout">
        <div class="left-panel">
          <div class="panel-title">{{ rootName }}</div>
          <div class="tree-wrap" @contextmenu.prevent="onPanelContextMenu">
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
              <span class="tree-node-content">
                <span class="tree-folder-icon" aria-hidden="true">{{ node.expanded ? '📂' : '📁' }}</span>
                <span class="tree-node-label">{{ data.name }}</span>
              </span>
            </template>
          </el-tree>
            <div v-if="contextMenuVisible" class="tree-context-menu" :style="contextMenuStyle">
              <button type="button" class="menu-item" @click="handleContextCommand('create')">新建文件夹</button>
              <button
                type="button"
                class="menu-item"
                :disabled="!contextTargetPath"
                @click="handleContextCommand('rename')"
              >
                改名
              </button>
              <button
                type="button"
                class="menu-item menu-item-danger"
                :disabled="!contextTargetPath"
                @click="handleContextCommand('delete')"
              >
                删除文件夹
              </button>
            </div>
          </div>
        </div>

        <div class="right-panel">
          <div class="panel-title">文件列表（当前目录：）</div>
          <el-table
            v-loading="loadingFiles"
            :data="filteredFiles"
            border
            stripe
            size="small"
            class="file-table"
            @header-dragend="onTableHeaderDragEnd"
          >
            <el-table-column
              column-key="fileName"
              label="文件"
              :width="fileColumnWidth"
              :min-width="210"
              :resizable="true"
            >
              <template #default="scope">
                <el-link class="file-cell" @click.stop="openFilePreview(scope.row)">
                  <span class="file-cell-inner">
                    <Icon :icon="getFileIcon(scope.row.file_path)" class="file-icon" />
                    <span class="file-name" :title="scope.row.name">{{ scope.row.name }}</span>
                  </span>
                </el-link>
              </template>
            </el-table-column>

            <el-table-column prop="contract_name" label="名称" min-width="260" show-overflow-tooltip />
            <el-table-column prop="contract_number" label="合同编号" min-width="140" />
            <el-table-column prop="contract_unit" label="合同单位" min-width="180" show-overflow-tooltip />
            <el-table-column prop="contract_amount" label="合同金额" min-width="120" />
            <el-table-column prop="approval_status" label="审批状态" min-width="110" />
            <el-table-column prop="handler" label="承办人" min-width="100" />
            <el-table-column prop="handling_department" label="承办部门" min-width="130" />
            <el-table-column prop="handling_date" label="承办日期" min-width="120" />
            <el-table-column prop="contract_type" label="合同类型" min-width="110" />
            <el-table-column prop="is_archived" label="是否归档" min-width="100" />
            <el-table-column prop="project" label="项目" min-width="220" show-overflow-tooltip />

            <el-table-column label="操作" width="150" fixed="right" align="center">
              <template #default="scope">
                <div class="action-buttons">
                  <el-tooltip content="下载" placement="top">
                    <el-button circle size="small" :icon="Download" @click.stop="downloadFile(scope.row)" />
                  </el-tooltip>
                  <el-tooltip content="预览" placement="top">
                    <el-button
                      circle
                      size="small"
                      type="primary"
                      :icon="View"
                      :disabled="!isPdfFile(scope.row.file_path)"
                      @click.stop="openFilePreview(scope.row)"
                    />
                  </el-tooltip>
                </div>
              </template>
            </el-table-column>
          </el-table>
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
    
  </div>

</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Download, View } from '@element-plus/icons-vue'
import { Icon } from '@iconify/vue'
import VuePdfEmbed from 'vue-pdf-embed'
import fileTypeWord from '@iconify-icons/vscode-icons/file-type-word'
import fileTypeExcel from '@iconify-icons/vscode-icons/file-type-excel'
import fileTypePdf from '@iconify-icons/vscode-icons/file-type-pdf2'
import microsoftOffice from '@iconify-icons/simple-icons/microsoftoffice'
import { GlobalWorkerOptions } from 'pdfjs-dist/legacy/build/pdf.mjs'
import PdfWorker from 'pdfjs-dist/legacy/build/pdf.worker.min.mjs?url'

import http from '../api/http'

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
const contextMenuVisible = ref(false)
const contextMenuStyle = ref({ left: '0px', top: '0px' })
const contextTargetPath = ref('')

const treeProps = {
  label: 'name',
  children: 'children',
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

const fetchFolderChildren = async (parentPath = '') => {
  const { data } = await http.get('/folders/children', {
    params: { parent_path: normalizePath(parentPath) },
  })
  return Array.isArray(data?.children) ? data.children : []
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

const showContextMenu = (event, path = '') => {
  event.preventDefault()
  contextTargetPath.value = path || ''

  const container = event.target?.closest?.('.tree-wrap')
  const rect = container?.getBoundingClientRect?.()
  const left = rect ? event.clientX - rect.left : 0
  const top = rect ? event.clientY - rect.top : 0

  contextMenuStyle.value = {
    left: `${left}px`,
    top: `${top}px`,
  }
  contextMenuVisible.value = true
}

const onPanelContextMenu = (event) => {
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

const applySearch = () => {
  activeKeyword.value = String(searchKeyword.value || '').trim().toLowerCase()
}

const filteredFiles = computed(() => {
  const keyword = activeKeyword.value
  if (!keyword) {
    return files.value
  }

  return files.value.filter((row) => {
    const text = [
      row?.name,
      row?.file_path,
      row?.contract_name,
      row?.contract_number,
      row?.contract_unit,
      row?.contract_amount,
      row?.approval_status,
      row?.handler,
      row?.handling_department,
      row?.handling_date,
      row?.contract_type,
      row?.is_archived,
      row?.project,
    ]
      .map((item) => String(item || '').toLowerCase())
      .join(' ')

    return text.includes(keyword)
  })
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

const loadFolderFiles = async (folderPath) => {
  loadingFiles.value = true
  try {
    const { data } = await http.get('/folders/files', {
      params: { folder_path: folderPath || '' },
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

const loadTree = async (keepSelected = true) => {
  loadingTree.value = true
  try {
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
  await loadFolderFiles(node?.path || '')
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
  } catch (error) {
    if (error === 'cancel' || error === 'close') {
      return
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

const openFilePreview = async (row) => {
  if (!row?.file_path) {
    return
  }

  if (!isPdfFile(row.file_path)) {
    ElMessage.warning('仅支持PDF预览，请使用下载功能')
    return
  }

  try {
    const response = await http.get('/folders/file-preview', {
      params: { path: row.file_path },
      responseType: 'blob',
    })

    resetPreview()
    previewRow.value = row
    previewUrl.value = window.URL.createObjectURL(new Blob([response.data], { type: 'application/pdf' }))
    previewDialogVisible.value = true
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || '预览失败')
  }
}

const onPdfRenderFailed = () => {
  ElMessage.warning('PDF 渲染失败，请尝试下载原文件')
}

onMounted(async () => {
  window.addEventListener('click', hideContextMenu)
  await loadTree(false)
})

onBeforeUnmount(() => {
  window.removeEventListener('click', hideContextMenu)
})

watch(previewDialogVisible, (visible) => {
  if (!visible) {
    resetPreview()
  }
})
</script>

<style scoped>
.folder-layout {
  display: grid;
  grid-template-columns: 320px minmax(0, 1fr);
  gap: 16px;
}

.left-panel,
.right-panel {
  border: 1px solid #ebeef5;
  border-radius: 8px;
  padding: 12px;
  background: #fff;
  min-height: 68vh;
}

.tree-wrap {
  position: relative;
}

.tree-wrap :deep(.el-tree-node__expand-icon) {
  display: none;
}

.tree-node-content {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.tree-folder-icon {
  font-size: 16px;
  line-height: 1;
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

.panel-title {
  margin-bottom: 10px;
  color: #374151;
  font-weight: 600;
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
  }

  .left-panel,
  .right-panel {
    min-height: auto;
  }
}
</style>
