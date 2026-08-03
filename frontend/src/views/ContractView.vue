<template>
  <div class="contract-page" :loading="importingExcel || aiParsing">
    <el-card>
      <template #header>
        <div class="card-header">
          <div class="card-title">所有信息</div>
          <div class="card-num">
            <el-tag type="danger" size="default">{{ totalContracts }} 条</el-tag>
          </div>
          
        </div>
     
      </template>


       <div class="header-notice">
     
          <div class="notice-content">
            ℹ️ <span>合同金额单位为元，合同编号必须唯一，归档状态为已归档的只有超管可以修改</span>
          </div>

          <div v-if="showDepartmentRestrictedNotice" class="notice-content">
            🚦 <span>以下只显示具有权限的部门合同：{{ currentUserDepartmentListText }}</span>
          </div>

      </div>

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
        <div class="toolbar-row">


       
          <el-switch
            v-model="filters.is_archived"
            active-text="已归档"
            inactive-text="未归档"
            @change="loadContracts"
          />
          <div style="margin-left: 24px">

            <el-switch
              v-model="filters.completeness"
              active-text="完整"
              inactive-text="不完整"
              @change="loadContracts"
            />
          </div>

          <div style="flex-grow:1">

          </div>

          
          <div v-if="!isViewPermissionUser" class="header-actions">
            <el-button-group class="apple-button-group">

              <el-button type="primary" :disabled="aiParsing" @click="openCreate">
                <el-icon><Plus /></el-icon>
                <span>新建合同</span>
              </el-button>


               <el-button :loading="aiParsing" @click="triggerAiUpload">
                <el-icon><Document /></el-icon>
                <span>{{ aiParsing ? '解析中...' : 'AI上传' }}</span>
              </el-button>
            
              <el-button :loading="importingExcel" :disabled="aiParsing" @click="importDialogVisible = true">
                <el-icon><Upload /></el-icon>
                <span>{{ importingExcel ? '导入中...' : '导入Excel' }}</span>
              </el-button>

              <el-dropdown
                split-button
                type="primary"
                trigger="click"
                :loading="exportingExcel || exportingGroupExcel"
                :disabled="aiParsing"
                @click="exportContractsExcel"
                @command="handleGroupReportExportCommand"
              >
                <el-icon><Download /></el-icon>
                <span>{{ exportingExcel || exportingGroupExcel ? '导出中...' : '导出EXCEL' }}</span>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item
                      v-for="year in groupReportYears"
                      :key="year"
                      :command="year"
                    >
                      {{ year }}集团上报
                    </el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>

             

              <el-button :loading="quickMatching" :disabled="aiParsing" @click="openQuickMatchDialog">
                <el-icon><Search /></el-icon>
                <span>快速批配</span>
              </el-button>
          
            </el-button-group>

            
          </div>
      
        </div>
        <div class="toolbar-row">

          <el-select v-model="filters.current_management_department" clearable placeholder="按现管部门筛选" style="width: 220px" @change="loadContracts">
            <el-option value="__empty__" label="(空)" />
            <el-option v-for="item in existingDepartmentFilterOptions" :key="item" :label="item" :value="item" />
          </el-select>

          <el-select v-model="filters.handling_department" clearable placeholder="按承办部门筛选" style="width: 220px" @change="loadContracts">
            <el-option value="__empty__" label="(空)" />
            <el-option v-for="item in departmentFilterOptions" :key="item" :label="item" :value="item" />
          </el-select>

          <el-select
            v-model="filters.has_file"
            placeholder="附件状态"
            style="width: 140px"
            @change="loadContracts"
          >
            <el-option label="全部" value="" />
            <el-option label="无附件" value="false" />
            <el-option label="有附件" value="true" />
          </el-select>
       


          <el-select v-model="filters.project" clearable placeholder="按项目筛选" style="width: 200px" @change="loadContracts">
            <el-option value="__empty__" label="(空)" />
            <el-option v-for="item in options.project" :key="item" :label="item" :value="item" />
          </el-select>

          <el-input
            v-model="filters.keyword"
            clearable
            placeholder="搜索任意合同字段"
            style="width: 280px"
            @clear="loadContracts"
            @keyup.enter="searchContracts"
          />
          <el-button type="primary" @click="searchContracts">搜索</el-button>
        </div>
      </div>

      <div class="pager-top">
        <div class="pager-top-actions">
          <el-tooltip content="字段排序" placement="top">
            <el-button class="field-sort-button" circle :icon="Operation" @click="openFieldSortDialog" />
          </el-tooltip>
          <el-dropdown trigger="click" @command="setColorFlagFilter">
            <button type="button" class="color-filter-trigger" title="按颜色标记筛选">
              <span class="color-flag-icon" :class="getColorFlagClass(filters.color_flag)">⚑</span>
            </button>
            <template #dropdown>
              <el-dropdown-menu class="color-flag-dropdown-menu">
                <el-dropdown-item :command="''">
                  <span class="color-flag-icon is-none">⚑</span>
                </el-dropdown-item>
                <el-dropdown-item v-for="item in colorFlagFilterOptions" :key="item" :command="item">
                  <span class="color-flag-icon" :class="getColorFlagClass(item)">⚑</span>
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :total="totalContracts"
          :page-sizes="[50, 100, 200, 500]"
          layout="total, sizes, prev, pager, next, jumper"
          background
        />
      </div>

      <el-table :data="pagedContracts" stripe border resizable size="small" class="contract-table" @sort-change="handleSortChange">
        <el-table-column
          prop="color_flag"
          label=""
          width="54"
          align="center"
        >
          <template #default="scope">
            <el-dropdown
              v-if="hasDepartmentEditPermissionForContract(scope.row)"
              trigger="click"
              @command="(command) => updateColorFlag(scope.row, command)"
            >
              <button type="button" class="color-flag-trigger" title="颜色标记">
                <span class="color-flag-icon" :class="getColorFlagClass(scope.row.color_flag)">⚑</span>
              </button>
              <template #dropdown>
                <el-dropdown-menu class="color-flag-dropdown-menu">
                  <el-dropdown-item :command="''">
                    <span class="color-flag-icon is-none">⚑</span>
                  </el-dropdown-item>
                  <el-dropdown-item v-for="item in colorFlagFilterOptions" :key="item" :command="item">
                    <span class="color-flag-icon" :class="getColorFlagClass(item)">⚑</span>
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
            <span v-else class="color-flag-icon" :class="getColorFlagClass(scope.row.color_flag)">⚑</span>
          </template>
        </el-table-column>

        <template v-for="column in visibleTableColumns" :key="column.key">
          <el-table-column
            v-if="column.key === 'contract_number'"
            prop="contract_number"
            label="合同编号"
            :min-width="contractNumberColumnWidth"
            sortable
            show-overflow-tooltip
          >
            <template #default="scope">
              <span class="no-wrap-cell" :title="scope.row.contract_number || ''">
                {{ scope.row.contract_number || '' }}
              </span>
            </template>
          </el-table-column>

          <el-table-column
            v-else-if="column.key === 'contract_name'"
            prop="contract_name"
            label="合同名称"
            :min-width="contractNameColumnWidth"
            show-overflow-tooltip
            sortable
          >
            <template #default="scope">
              <button class="contract-name-link" type="button" @click.stop="openEdit(scope.row)">
                <span class="contract-name-cell">{{ scope.row.contract_name }}</span>
              </button>
            </template>
          </el-table-column>

          <el-table-column v-else-if="column.key === 'file_path'" prop="file_path" label="文件" min-width="220">
            <template #default="scope">
              <el-link class="file-cell" @click.stop.prevent="openFilePreview(scope.row, $event)" v-if="scope.row.file_path">
                <el-tooltip :content="scope.row.file_path" placement="top">
                  <Icon
                    v-if="scope.row.file_path"
                    :icon="getFileIcon(scope.row.file_path)"
                    class="file-ok file-download"
                  />
                </el-tooltip>

                <span class="file-name" :title="scope.row.file_path || ''">
                  {{ getFileName(scope.row.file_path) || '缺失' }}
                </span>
              </el-link>
              <div v-else>
                <el-icon class="file-miss"><CircleCloseFilled /></el-icon>
                <span class="no-file-name">未上传</span>
              </div>
            </template>
          </el-table-column>

          <el-table-column v-else-if="column.key === 'created_at'" prop="created_at" label="创建时间" min-width="170" sortable>
            <template #default="scope">
              <span>{{ formatDateTime(scope.row.created_at) }}</span>
            </template>
          </el-table-column>

          <el-table-column v-else-if="column.key === 'updated_at'" prop="updated_at" label="修改时间" min-width="170" sortable>
            <template #default="scope">
              <span>{{ formatDateTime(scope.row.updated_at) }}</span>
            </template>
          </el-table-column>

          <el-table-column
            v-else-if="column.key === 'original_contract'"
            prop="original_contract_id"
            label="原合同"
            min-width="220"
            show-overflow-tooltip
          >
            <template #default="scope">
              <span class="no-wrap-cell" :title="formatOriginalContractLabel(scope.row)">
                {{ formatOriginalContractLabel(scope.row) || '-' }}
              </span>
            </template>
          </el-table-column>

          <el-table-column
            v-else
            :prop="column.prop"
            :label="column.label"
            :min-width="column.minWidth"
            :show-overflow-tooltip="column.showOverflowTooltip"
            :sortable="column.sortable"
          />
        </template>
     
        <el-table-column v-if="!isViewPermissionUser" label="操作" width="140" fixed="right" align="center">
          <template #default="scope">
            <div class="action-buttons">
              <el-tooltip content="编辑" placement="top">
                <el-button
                  circle
                  size="small"
                  type="primary"
                  :icon="Edit"
                  :disabled="!hasDepartmentEditPermissionForContract(scope.row)"
                  @click.stop="openEdit(scope.row)"
                />
              </el-tooltip>
              <el-tooltip content="删除" placement="top">
                <el-button
                  circle
                  size="small"
                  type="danger"
                  :icon="Delete"
                  :disabled="!hasDepartmentEditPermissionForContract(scope.row)"
                  @click.stop="handleDelete(scope.row)"
                />
              </el-tooltip>
            </div>
          </template>
        </el-table-column>
      </el-table>

      <div class="pager">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :total="totalContracts"
          :page-sizes="[50, 100, 200, 500]"
          layout="total, sizes, prev, pager, next, jumper"
          background
        />
      </div>
    </el-card>

    <el-dialog
      v-model="fieldSortDialogVisible"
      title="字段排序"
      width="min(760px, 96vw)"
      :close-on-click-modal="false"
    >
      <div class="field-sort-tip">勾选表示显示，取消勾选表示隐藏。拖动左侧手柄可调整表格列顺序。</div>
      <div class="field-sort-list">
        <div
          ref="fieldSortListRef"
          v-for="column in fieldSortDraftColumns"
          :key="column.key"
          class="field-sort-item"
          :class="{
            'is-hidden': !column.visible,
            'is-dragging': draggingColumnKey === column.key,
          }"
          :data-column-key="column.key"
        >
          <span
            class="field-sort-drag-handle"
            aria-hidden="true"
            @pointerdown.prevent="handleColumnPointerDown(column.key, $event)"
          >
            <el-icon><Rank /></el-icon>
          </span>
          <el-checkbox v-model="column.visible" :label="column.label" class="field-sort-checkbox" />
        </div>
      </div>
      <div
        v-if="dragPreview.visible"
        class="field-sort-drag-preview"
        :style="{
          left: `${dragPreview.x}px`,
          top: `${dragPreview.y}px`,
        }"
      >
        <span class="field-sort-drag-preview-icon" aria-hidden="true"><el-icon><Rank /></el-icon></span>
        <span class="field-sort-drag-preview-label">{{ dragPreview.label }}</span>
      </div>
      <template #footer>
        <el-button @click="resetFieldSortDraft">恢复默认</el-button>
        <el-button @click="fieldSortDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmFieldSortDialog">完成</el-button>
      </template>
    </el-dialog>

    <AiMatchDialog
      v-model="aiMatchDialogVisible"
      :candidates="aiMatchCandidates"
      :loading="aiMatchLoading"
      :processing="aiMatchProcessing"
      :file="aiParsedUploadFile"
      @confirm-selection="proceedAiMatchSelection"
      @cancel="closeAiMatchDialog"
    />

    <el-dialog v-model="importDialogVisible" title="导入合同" width="500px" :close-on-click-modal="false">
      <div class="import-dialog-content">
        <el-alert
          type="info"
          :closable="false"
          show-icon
          title="导入规则"
          style="margin-bottom: 20px"
        >
          <div class="import-rules">
            <div>• 合同编号: 必须唯一，如果编号存在并且标题相同，则更新合同内容，否则失败</div>
            <div>• 归档状态: 所有导入的合同自动归档到"未归档",已归档的合同由管理员进行修改</div>
            <div>• 合同金额: 从MIS导出的“合同金额（万元”）必须转成元，字段名必须重新命名为“合同金额” </div>
            <div>• 份数(copy_count): 选填，纯数字（整数）</div>
            <div>• 存档位置(save_place): 选填，最多50个字符</div>
          </div>
        </el-alert>
      </div>
      <template #footer>
        <div class="import-dialog-footer">

           <el-button link @click="downloadImportTemplate">
            <el-icon><Download /></el-icon>
            下载模板
          </el-button>

          
          <el-button @click="importDialogVisible = false">取消</el-button>
         
          <el-button type="primary" :loading="importingExcel" :disabled="importingExcel" @click="triggerExcelUpload">
            <el-icon><Document /></el-icon>
            {{ importingExcel ? '导入中...' : '选择文件' }}
          </el-button>
        </div>
      </template>
    </el-dialog>

    <el-dialog
      v-model="quickMatchDialogVisible"
      title="快速批配"
      width="min(880px, 96vw)"
      :close-on-click-modal="false"
    >
      <el-input
        v-model="quickMatchLogText"
        type="textarea"
        class="quick-match-log"
        :rows="18"
        resize="none"
        readonly
      />

      <template #footer>
        <el-button @click="quickMatchDialogVisible = false">关闭</el-button>
        <el-button type="primary" :loading="quickMatching" @click="startQuickMatch">开始</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="aiFolderDialogVisible"
      title="选择AI上传目录"
      width="min(760px, 96vw)"
      :close-on-click-modal="false"
    >
      <div class="ai-folder-dialog-tip">请先选择目标目录，再选择本地 PDF 文件。</div>
      <div class="ai-folder-dialog-selected">当前选择：{{ aiFolderSelectedPath || '未选择' }}</div>

      <div class="ai-folder-tree-wrap" v-loading="aiFolderTreeLoading">
        <el-tree
          :key="aiFolderTreeRenderKey"
          :data="aiFolderTreeData"
          node-key="path"
          :props="aiFolderTreeProps"
          lazy
          :load="loadAiFolderChildren"
          :expand-on-click-node="true"
          highlight-current
          @node-click="onAiFolderNodeClick"
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
        <el-button @click="aiFolderDialogVisible = false">取消</el-button>
        <el-button type="primary" :disabled="!canConfirmAiFolder" @click="confirmAiFolderSelection">下一步：选择本地文件</el-button>
      </template>
    </el-dialog>

    <ContractItem
      ref="contractItemRef"
      :departments="departments"
      :current-management-departments="existingDepartments"
      :contracts="contracts"
      :options="options"
      :current-user-role="currentUserRole"
      :link-tree-snapshot="linkTreeSnapshot"
      v-model:aiParsing="aiParsing"
      @saved="handleContractSaved"
    />

  </div>
</template>

<script setup>

import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Icon } from '@iconify/vue'
import fileTypeWord from '@iconify-icons/vscode-icons/file-type-word'
import fileTypeExcel from '@iconify-icons/vscode-icons/file-type-excel'
import fileTypePdf from '@iconify-icons/vscode-icons/file-type-pdf2'
import microsoftOffice from '@iconify-icons/simple-icons/microsoftoffice'
import { CircleCloseFilled, Delete, Document, Download, Edit, Operation, Plus, Rank, Search, Upload } from '@element-plus/icons-vue'

import http from '../api/http'
import ContractItem from '../components/ContractItem.vue'
import AiMatchDialog from '../components/AiMatchDialog.vue'

const AI_NEW_CONTRACT_VALUE = '__new_contract__'
const TABLE_COLUMN_STORAGE_KEY = 'docscool.contract-list.columns.v1'
const appBasePrefix = import.meta.env.BASE_URL || '/'

const DEFAULT_TABLE_COLUMNS = [
  { key: 'contract_number', prop: 'contract_number', label: '合同编号', minWidth: 90, visible: true, sortable: true, showOverflowTooltip: true },
  { key: 'contract_name', prop: 'contract_name', label: '合同名称', minWidth: 220, visible: true, sortable: true, showOverflowTooltip: true },
  { key: 'file_path', prop: 'file_path', label: '文件', minWidth: 220, visible: true, sortable: false, showOverflowTooltip: false },
  { key: 'contract_unit', prop: 'contract_unit', label: '合同单位', minWidth: 180, visible: true, sortable: true, showOverflowTooltip: true },
  { key: 'contract_execution_status', prop: 'contract_execution_status', label: '合同执行状态', minWidth: 130, visible: true, sortable: true, showOverflowTooltip: false },
  { key: 'contract_amount', prop: 'contract_amount', label: '合同金额', minWidth: 120, visible: true, sortable: true, showOverflowTooltip: false },
  { key: 'copy_count', prop: 'copy_count', label: '份数', minWidth: 80, visible: true, sortable: true, showOverflowTooltip: false },
  { key: 'handler', prop: 'handler', label: '承办人', minWidth: 100, visible: true, sortable: true, showOverflowTooltip: false },
  { key: 'handling_department', prop: 'handling_department', label: '承办部门', minWidth: 130, visible: true, sortable: true, showOverflowTooltip: false },
  { key: 'current_management_department', prop: 'current_management_department', label: '现管部门', minWidth: 130, visible: true, sortable: true, showOverflowTooltip: false },
  { key: 'handling_date', prop: 'handling_date', label: '承办日期', minWidth: 110, visible: true, sortable: true, showOverflowTooltip: false },
  { key: 'contract_type', prop: 'contract_type', label: '合同类型', minWidth: 110, visible: true, sortable: true, showOverflowTooltip: false },
  { key: 'purchase_type', prop: 'purchase_type', label: '采购类型', minWidth: 110, visible: true, sortable: true, showOverflowTooltip: false },
  { key: 'stamp_tax_rate', prop: 'stamp_tax_rate', label: '印花税率', minWidth: 100, visible: true, sortable: true, showOverflowTooltip: false },
  { key: 'completeness', prop: 'completeness', label: '完整性', minWidth: 90, visible: true, sortable: true, showOverflowTooltip: false },
  { key: 'is_archived', prop: 'is_archived', label: '是否归档', minWidth: 90, visible: true, sortable: true, showOverflowTooltip: false },
  { key: 'save_place', prop: 'save_place', label: '存档位置', minWidth: 140, visible: true, sortable: true, showOverflowTooltip: true },
  { key: 'project', prop: 'project', label: '项目', minWidth: 220, visible: true, sortable: true, showOverflowTooltip: true },
  { key: 'original_contract', prop: 'original_contract_id', label: '原合同', minWidth: 220, visible: true, sortable: true, showOverflowTooltip: true },
  { key: 'created_by', prop: 'created_by', label: '创建人', minWidth: 120, visible: true, sortable: true, showOverflowTooltip: true },
  { key: 'created_at', prop: 'created_at', label: '创建时间', minWidth: 170, visible: true, sortable: true, showOverflowTooltip: false },
  { key: 'updated_by', prop: 'updated_by', label: '修改人', minWidth: 120, visible: true, sortable: true, showOverflowTooltip: true },
  { key: 'updated_at', prop: 'updated_at', label: '修改时间', minWidth: 170, visible: true, sortable: true, showOverflowTooltip: false },
]

const cloneTableColumns = () => DEFAULT_TABLE_COLUMNS.map((item) => ({ ...item }))

const loadStoredTableColumns = () => {
  try {
    const raw = window.localStorage.getItem(TABLE_COLUMN_STORAGE_KEY)
    if (!raw) {
      return cloneTableColumns()
    }

    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) {
      return cloneTableColumns()
    }

    const parsedMap = new Map()
    parsed.forEach((item) => {
      if (item?.key) {
        parsedMap.set(item.key, item)
      }
    })

    return DEFAULT_TABLE_COLUMNS.map((item) => {
      const stored = parsedMap.get(item.key)
      return stored ? { ...item, ...stored, visible: stored.visible !== false } : { ...item }
    })
  } catch (_error) {
    return cloneTableColumns()
  }
}

const contracts = ref([])
const departments = ref([])
const existingDepartments = ref([])
const aiParsing = ref(false)
const quickMatching = ref(false)
const quickMatchDialogVisible = ref(false)
const quickMatchLogText = ref('')
const aiMatchDialogVisible = ref(false)
const aiMatchLoading = ref(false)
const aiMatchProcessing = ref(false)
const aiMatchCandidates = ref([])
const aiParsedFields = ref(null)
const aiParsedFullbody = ref('')
const aiParsedUploadFile = ref(null)
const aiUploadedFilePath = ref('')
const aiFolderDialogVisible = ref(false)
const aiFolderTreeLoading = ref(false)
const aiFolderTreeData = ref([])
const aiFolderTreeRenderKey = ref(0)
const aiFolderSelectedPath = ref('')
const aiUploadTargetFolderPath = ref('')
const fieldSortDialogVisible = ref(false)
const fieldSortListRef = ref(null)
const draggingColumnKey = ref('')
const draggingPointerId = ref(null)
const dragPreview = reactive({
  visible: false,
  x: 0,
  y: 0,
  label: '',
})
const fieldSortDraftColumns = ref([])
const importingExcel = ref(false)
const exportingExcel = ref(false)
const exportingGroupExcel = ref(false)
const importDialogVisible = ref(false)
const currentPage = ref(1)
const contractItemRef = ref(null)
const currentUserPermission = ref('view')
const currentUserRole = ref('admin')
const currentUserDepartmentList = ref([])
const currentUserPermissionList = ref([])
const sortState = reactive({ prop: '', order: '' })
const tableColumns = ref(loadStoredTableColumns())
const linkTreeSnapshot = reactive({
  root: { name: '/', path: '' },
  rootChildren: [],
  childrenByParent: {},
  refreshedAt: 0,
})

const handleSortChange = ({ prop, order }) => {
  sortState.prop = prop
  sortState.order = order
}

const openFieldSortDialog = () => {
  fieldSortDraftColumns.value = tableColumns.value.map((item) => ({ ...item }))
  fieldSortDialogVisible.value = true
}

const resetFieldSortDraft = () => {
  fieldSortDraftColumns.value = cloneTableColumns()
}

const confirmFieldSortDialog = () => {
  tableColumns.value = fieldSortDraftColumns.value.map((item) => ({ ...item }))
  fieldSortDialogVisible.value = false
}

const visibleTableColumns = computed(() => tableColumns.value.filter((item) => item.visible))

const colorFlagFilterOptions = computed(() => {
  const source = Array.isArray(options.color_flag) ? options.color_flag : []
  return source.length ? source : ['红旗', '橙旗', '黄旗', '绿旗', '蓝旗']
})

const persistTableColumns = () => {
  try {
    window.localStorage.setItem(TABLE_COLUMN_STORAGE_KEY, JSON.stringify(tableColumns.value))
  } catch (_error) {
    // Ignore storage failures.
  }
}

const resetTableColumns = () => {
  tableColumns.value = cloneTableColumns()
  persistTableColumns()
}

const moveTableColumn = (fromKey, toKey) => {
  if (!fromKey || !toKey || fromKey === toKey) {
    return
  }

  const nextColumns = [...fieldSortDraftColumns.value]
  const fromIndex = nextColumns.findIndex((item) => item.key === fromKey)
  const toIndex = nextColumns.findIndex((item) => item.key === toKey)

  if (fromIndex < 0 || toIndex < 0) {
    return
  }

  const [moved] = nextColumns.splice(fromIndex, 1)
  nextColumns.splice(toIndex, 0, moved)
  fieldSortDraftColumns.value = nextColumns
}

const updateDragPreviewPosition = (clientX, clientY) => {
  const offsetX = 18
  const offsetY = 18
  const previewWidth = 220
  const previewHeight = 44
  const maxX = Math.max(12, window.innerWidth - previewWidth - 12)
  const maxY = Math.max(12, window.innerHeight - previewHeight - 12)
  dragPreview.x = Math.min(clientX + offsetX, maxX)
  dragPreview.y = Math.min(clientY + offsetY, maxY)
}

const getColumnKeyFromPoint = (clientX, clientY) => {
  const element = document.elementFromPoint(clientX, clientY)
  const itemElement = element?.closest?.('.field-sort-item')
  return itemElement?.dataset?.columnKey || ''
}

const handleColumnPointerMove = (event) => {
  if (!draggingColumnKey.value || draggingPointerId.value !== event.pointerId) {
    return
  }

  updateDragPreviewPosition(event.clientX, event.clientY)

  const targetKey = getColumnKeyFromPoint(event.clientX, event.clientY)
  if (targetKey && targetKey !== draggingColumnKey.value) {
    moveTableColumn(draggingColumnKey.value, targetKey)
  }
}

const stopColumnPointerDrag = () => {
  draggingColumnKey.value = ''
  draggingPointerId.value = null
  dragPreview.visible = false
  dragPreview.label = ''
  window.removeEventListener('pointermove', handleColumnPointerMove)
  window.removeEventListener('pointerup', stopColumnPointerDrag)
  window.removeEventListener('pointercancel', stopColumnPointerDrag)
}

const handleColumnPointerDown = (key, event) => {
  if (event.button !== 0) {
    return
  }

  draggingColumnKey.value = key
  draggingPointerId.value = event.pointerId
  dragPreview.label = fieldSortDraftColumns.value.find((item) => item.key === key)?.label || ''
  dragPreview.visible = true
  updateDragPreviewPosition(event.clientX, event.clientY)
  event.currentTarget?.setPointerCapture?.(event.pointerId)
  window.addEventListener('pointermove', handleColumnPointerMove)
  window.addEventListener('pointerup', stopColumnPointerDrag)
  window.addEventListener('pointercancel', stopColumnPointerDrag)
}

watch(tableColumns, persistTableColumns, { deep: true })

watch(fieldSortDialogVisible, (visible) => {
  if (visible) {
    fieldSortDraftColumns.value = tableColumns.value.map((item) => ({ ...item }))
    stopColumnPointerDrag()
  }
})

onBeforeUnmount(() => {
  stopColumnPointerDrag()
})

const formatDateTime = (value) => {
  const text = String(value || '').trim()
  if (!text) {
    return ''
  }

  const date = new Date(text)
  if (Number.isNaN(date.getTime())) {
    return text
  }

  const pad = (n) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}

const sortedContracts = computed(() => {
  if (!contracts.value || contracts.value.length === 0) return []
  if (!sortState.prop || !sortState.order) return contracts.value
  
  const sorted = [...contracts.value].sort((a, b) => {
    let valA = a[sortState.prop]
    let valB = b[sortState.prop]
    
    if (valA === null || valA === undefined) valA = ''
    if (valB === null || valB === undefined) valB = ''
    
    if (typeof valA === 'number' && typeof valB === 'number') {
      return sortState.order === 'ascending' ? valA - valB : valB - valA
    }
    
    valA = String(valA)
    valB = String(valB)
    
    return sortState.order === 'ascending' 
      ? valA.localeCompare(valB, 'zh-CN')
      : valB.localeCompare(valA, 'zh-CN')
  })
  
  return sorted
})

const pagedContracts = computed(() => {
  if (!sortedContracts.value || sortedContracts.value.length === 0) return []
  const start = (currentPage.value - 1) * pageSize.value
  return sortedContracts.value.slice(start, start + pageSize.value)
})
const excelUploadInput = ref(null)
const aiUploadInput = ref(null)
const pageSize = ref(100)
const aiFolderTreeProps = {
  label: 'name',
  children: 'children',
}

const filters = reactive({
  current_management_department: '',
  handling_department: '',
  project: '',
  color_flag: '',
  completeness: null,
  keyword: '',
  has_file: '',
  is_archived: null,
})

const currentYear = new Date().getFullYear()
const groupReportYears = computed(() => {
  const startYear = 2025
  if (currentYear < startYear) {
    return []
  }
  return Array.from({ length: currentYear - startYear + 1 }, (_, index) => startYear + index)
})

const options = reactive({
  contract_form: [],
  contract_determination_method: [],
  contract_type: [],
  purchase_type: [],
  stamp_tax_rate_by_contract_type: {},
  pricing_method: [],
  is_archived: [],
  color_flag: [],
  completeness: [],
  project: [],
})

const totalContracts = computed(() => sortedContracts.value ? sortedContracts.value.length : 0)
const SUPER_ROLE_SET = new Set(['super_admin', 'synology_super_admin'])

const normalizeTextList = (value) => {
  const source = Array.isArray(value)
    ? value
    : (String(value || '').trim() ? [String(value || '').trim()] : [])
  const normalized = []
  const seen = new Set()
  source.forEach((item) => {
    const text = String(item || '').trim()
    if (!text || seen.has(text)) {
      return
    }
    seen.add(text)
    normalized.push(text)
  })
  return normalized
}

const normalizeCurrentPermissionList = (value) => {
  const source = Array.isArray(value) ? value : []
  return source
    .map((item) => {
      const permission = String(item?.permission || '').trim()
      if (!['edit', 'view'].includes(permission)) {
        return null
      }
      return {
        permission,
        departments: normalizeTextList(item?.departments),
        folders: normalizeTextList(item?.folders),
      }
    })
    .filter(Boolean)
}

const isViewPermissionUser = computed(() => {
  const role = String(currentUserRole.value || '').trim()
  if (SUPER_ROLE_SET.has(role)) {
    return false
  }
  return String(currentUserPermission.value || '').trim() === 'view'
})

const showDepartmentRestrictedNotice = computed(() => {
  const isSuperAdmin = SUPER_ROLE_SET.has(String(currentUserRole.value || '').trim())
  if (isSuperAdmin) {
    return false
  }
  return !currentUserDepartmentList.value.includes('全部')
})

const currentUserDepartmentListText = computed(() => {
  const items = Array.isArray(currentUserDepartmentList.value)
    ? currentUserDepartmentList.value
        .map((item) => String(item || '').trim())
        .filter(Boolean)
    : []

  if (!items.length) {
    return '（未配置部门权限）'
  }
  return items.join(', ')
})

const departmentFilterOptions = computed(() => {
  const merged = new Set()
  ;(departments.value || []).forEach((item) => {
    const value = String(item || '').trim()
    if (value) {
      merged.add(value)
    }
  })
  ;(contracts.value || []).forEach((row) => {
    const value = String(row?.handling_department || row?.department || '').trim()
    if (value) {
      merged.add(value)
    }
  })
  return Array.from(merged).sort((a, b) => a.localeCompare(b, 'zh-CN'))
})

const existingDepartmentFilterOptions = computed(() => {
  return Array.from(new Set((existingDepartments.value || []).map((item) => String(item || '').trim()).filter(Boolean)))
    .sort((a, b) => a.localeCompare(b, 'zh-CN'))
})

const quickMatchTargetIds = computed(() => {
  return (contracts.value || [])
    .filter((row) => (row?.is_archived || '').trim() !== '已归档' && !String(row?.file_path || '').trim())
    .map((row) => Number(row?.id))
    .filter((id) => Number.isInteger(id) && id > 0)
})

const canConfirmAiFolder = computed(() => {
  const path = normalizeFolderPath(aiFolderSelectedPath.value)
  return !!path
})

const contractBriefById = computed(() => {
  const map = new Map()
  ;(contracts.value || []).forEach((item) => {
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

const contractNameColumnWidth = computed(() => {
  if (!pagedContracts.value || pagedContracts.value.length === 0) return 220
  const baseWidth = 220
  const maxWidth = 560
  const longestLength = pagedContracts.value.reduce((maxLength, item) => {
    const text = String(item?.contract_name || '')
    return Math.max(maxLength, text.length)
  }, 0)

  return Math.min(maxWidth, Math.max(baseWidth, longestLength * 12 + 16))
})

const contractNumberColumnWidth = computed(() => {
  if (!pagedContracts.value || pagedContracts.value.length === 0) return 200
  const baseWidth = 90
  const maxWidth = 400
  const longestLength = pagedContracts.value.reduce((maxLength, item) => {
    const text = String(item?.contract_number || '')
    return Math.max(maxLength, text.length)
  }, 0)

  return Math.min(maxWidth, Math.max(baseWidth, longestLength * 7 + 16))
})

const resetAiMatchState = () => {
  aiMatchCandidates.value = []
  aiParsedFields.value = null
  aiParsedFullbody.value = ''
  aiParsedUploadFile.value = null
  aiUploadedFilePath.value = ''
  aiMatchLoading.value = false
  aiMatchProcessing.value = false
}

const loadContractDetail = async (contractId) => {
  const { data } = await http.get(`/contracts/${contractId}`)
  return data
}

const loadDepartments = async () => {
  const { data } = await http.get('/settings/departments')
  const rows = Array.isArray(data) ? data : []
  departments.value = rows.map((item) => item.name)
  existingDepartments.value = rows
    .filter((item) => {
      const value = item?.is_existing
      if (typeof value === 'boolean') return value
      if (typeof value === 'number') return value !== 0
      const text = String(value ?? '').trim().toLowerCase()
      return text === '1' || text === 'true' || text === 'yes' || text === 'y'
    })
    .map((item) => String(item?.name || '').trim())
    .filter(Boolean)
}

const loadFieldOptions = async () => {
  const { data } = await http.get('/options/contract-fields')
  options.contract_form = data?.contract_form || []
  options.contract_determination_method = data?.contract_determination_method || []
  options.contract_type = data?.contract_type || []
  options.purchase_type = data?.purchase_type || []
  options.stamp_tax_rate_by_contract_type = data?.stamp_tax_rate_by_contract_type || {}
  options.pricing_method = data?.pricing_method || []
  options.is_archived = data?.is_archived || []
  options.color_flag = data?.color_flag || []
  options.completeness = data?.completeness || []
  options.project = data?.project || []
}

const loadCurrentUserPermission = async () => {
  const { data } = await http.get('/settings/users/current-permission')
  currentUserRole.value = String(data?.role || 'admin').trim() || 'admin'
  currentUserPermission.value = String(data?.permission || 'view').trim() || 'view'
  currentUserDepartmentList.value = Array.isArray(data?.department_list)
    ? data.department_list.map((item) => String(item || '').trim()).filter(Boolean)
    : []
  currentUserPermissionList.value = normalizeCurrentPermissionList(data?.permission_list)
}

const normalizeFolderPath = (value) => String(value || '').replace(/\\/g, '/').replace(/^\/+|\/+$/g, '')

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
    result.push({
      ...item,
      name,
      path,
    })
  })

  return result
}

const buildOcrPreviewUrlFromFilePath = (filePath) => {
  const normalizedPath = normalizeFolderPath(filePath)
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

const loadAiFolderChildren = async (node, resolve) => {
  if (node?.level === 0) {
    aiFolderTreeLoading.value = true
  }
  const parentPath = node?.level === 0 ? '' : normalizeFolderPath(node?.data?.path || '')
  try {
    const { data } = await http.get('/folders/children', {
      params: { parent_path: parentPath },
    })
    resolve(dedupeFolderNodes(data?.children))
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || '读取子目录失败')
    resolve([])
  } finally {
    if (node?.level === 0) {
      aiFolderTreeLoading.value = false
    }
  }
}

const onAiFolderNodeClick = (node) => {
  aiFolderSelectedPath.value = normalizeFolderPath(node?.path || '')
}

const openAiFolderDialog = () => {
  aiFolderSelectedPath.value = normalizeFolderPath(aiUploadTargetFolderPath.value)
  aiFolderTreeData.value = []
  aiFolderTreeRenderKey.value += 1
  aiFolderTreeLoading.value = false
  aiFolderDialogVisible.value = true
}

const confirmAiFolderSelection = () => {
  const selected = normalizeFolderPath(aiFolderSelectedPath.value)
  if (!selected) {
    ElMessage.warning('请选择目标目录')
    return
  }
  aiUploadTargetFolderPath.value = selected
  aiFolderDialogVisible.value = false
  aiUploadInput.value?.click()
}




const shouldForceLogout = (error) => {
  const msg = error?.response?.data?.message || ''
  const status = error?.response?.status
  return (
    status === 401 ||
    /凭据已过期|登录凭据已过期|token失效|token过期|unauthorized|未授权/i.test(msg)
  )
}




const forceLogoutToLogin = () => {
  localStorage.removeItem('token')
  localStorage.removeItem('username')
  const basePath = (import.meta.env.BASE_URL || '/').replace(/\/$/, '')
  const loginPath = `${basePath}/login` || '/login'
  if (window.location.pathname !== loginPath) {
    window.location.href = loginPath
  }
}

const loadLinkTreeSnapshot = async () => {
  try {
    const [{ data: treeData }, { data: childrenData }] = await Promise.all([
      http.get('/folders/tree'),
      http.get('/folders/children', { params: { parent_path: '' } }),
    ])

    const root = treeData?.root || { name: '/', path: '' }
    const rootChildren = Array.isArray(childrenData?.children) ? childrenData.children : []

    linkTreeSnapshot.root = {
      name: root?.name || '/',
      path: normalizeFolderPath(root?.path || ''),
    }
    linkTreeSnapshot.rootChildren = rootChildren
    linkTreeSnapshot.childrenByParent = {
      '': rootChildren,
    }
    linkTreeSnapshot.refreshedAt = Date.now()
  } catch (error) {
    const msg = error?.response?.data?.message || ''
    if (shouldForceLogout(error)) {
      forceLogoutToLogin()
      return
    }
    linkTreeSnapshot.root = { name: '/', path: '' }
    linkTreeSnapshot.rootChildren = []
    linkTreeSnapshot.childrenByParent = { '': [] }
    ElMessage.warning(msg || '文件夹结构预加载失败，链接文件时将按需加载')
  }
}

const buildContractListParams = (searchOnly = false) => {
  if (searchOnly && filters.keyword) {
    return {
      keyword: filters.keyword || undefined,
    }
  }

  return {
    current_management_department: filters.current_management_department || undefined,
    handling_department: filters.handling_department || undefined,
    project: filters.project || undefined,
    color_flag: filters.color_flag || undefined,
    completeness: filters.completeness !== null ? (filters.completeness ? '是' : '否') : undefined,
    keyword: filters.keyword || undefined,
    has_file: filters.has_file || undefined,
    is_archived: filters.is_archived !== null ? (filters.is_archived ? '已归档' : '未归档') : undefined,
  }
}

const loadContracts = async (options = {}) => {
  const { searchOnly = false } = options
  const { data } = await http.get('/contracts', {
    params: buildContractListParams(searchOnly),
  })
  contracts.value = data
  currentPage.value = 1
}

const searchContracts = async () => {
  await loadContracts({ searchOnly: true })
}

const handleContractSaved = async () => {
  await loadDepartments()
  await loadFieldOptions()
  await loadContracts()
}

const quickMatchInstructionText = () => {
  return [
    '快速批配说明：',
    '1. 本功能会处理“未归档 且 无附件”的合同。',
    '2. 处理方式：在合同管理存储空间中扫描所有文件夹/子文件夹的 PDF 文件。',
    '3. 匹配规则：文件名包含合同编号直接匹配，文件名包含合同名称时视为候选；仅 1 个候选则直接匹配；多个候选按文件名相似度选择最佳项。',
    '4. 成功后会把匹配到的文件路径写入绑定到合同信息的附件',
    '',
    `当前可处理合同数量：${quickMatchTargetIds.value.length}`,
    '',
    '点击下方“开始”按钮执行批配。',
  ].join('\n')
}

const appendQuickMatchLog = (line = '') => {
  quickMatchLogText.value = `${quickMatchLogText.value}${quickMatchLogText.value ? '\n' : ''}${line}`
}

const openQuickMatchDialog = () => {
  quickMatchLogText.value = quickMatchInstructionText()
  quickMatchDialogVisible.value = true
}

const startQuickMatch = async () => {
  if (quickMatching.value) {
    return
  }

  const ids = quickMatchTargetIds.value
  quickMatchLogText.value = quickMatchInstructionText()
  appendQuickMatchLog('')
  appendQuickMatchLog(`开始执行，待处理合同数：${ids.length}`)

  if (!ids.length) {
    appendQuickMatchLog('无可处理合同，任务结束。')
    return
  }

  quickMatching.value = true
  try {
    const { data } = await http.post('/contracts/quick-match-files', { ids }, { timeout: 300000 })
    const rows = Array.isArray(data?.results) ? data.results : []

    rows.forEach((item, index) => {
      const prefix = `[${index + 1}/${rows.length}]`
      const code = item?.contract_number || `ID:${item?.id || ''}`
      const name = item?.contract_name || ''
      const base = `${prefix} ${code} ${name}`.trim()

      if (item?.status === 'success') {
        const filePath = item?.file_path || ''
        const info = item?.matched_count > 1 ? `（多候选取最优，相似度:${item?.similarity}）` : ''
        appendQuickMatchLog(`${base} -> 成功: ${filePath} ${info}`.trim())
      } else {
        appendQuickMatchLog(`${base} -> 失败: ${item?.message || '未知错误'}`)
      }
    })

    appendQuickMatchLog('')
    appendQuickMatchLog(`完成：成功 ${data?.success || 0}，失败 ${data?.failed || 0}，总计 ${data?.total || ids.length}`)
    ElMessage.success('快速批配已完成')
    await loadContracts()
  } catch (error) {
    if (shouldForceLogout(error)) {
      appendQuickMatchLog('执行失败：登录凭据已过期，正在跳转登录页...')
      forceLogoutToLogin()
      return
    }
    appendQuickMatchLog(`执行失败：${error?.response?.data?.message || '请求失败'}`)
    ElMessage.error(error?.response?.data?.message || '快速批配执行失败')
  } finally {
    quickMatching.value = false
  }
}

const openCreate = () => {
  contractItemRef.value?.openCreate()
}

const openCreateFromAi = (file, fields) => {
  contractItemRef.value?.openCreateFromAi(file, fields)
}

const isArchivedContract = (row) => {
  return String(row?.is_archived || '').trim() === '已归档'
}

const hasDepartmentEditPermissionForContract = (row) => {
  const role = String(currentUserRole.value || '').trim()
  if (SUPER_ROLE_SET.has(role)) {
    return true
  }

  if (isArchivedContract(row)) {
    return false
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

const getColorFlagClass = (value) => {
  const text = String(value || '').trim()
  if (text === '红旗') return 'is-red'
  if (text === '橙旗') return 'is-orange'
  if (text === '黄旗') return 'is-yellow'
  if (text === '绿旗') return 'is-green'
  if (text === '蓝旗') return 'is-blue'
  return 'is-none'
}

const setColorFlagFilter = async (command) => {
  filters.color_flag = String(command || '').trim()
  await loadContracts()
}

const updateColorFlag = async (row, value) => {
  if (!row?.id) {
    return
  }

  const nextValue = String(value || '').trim()
  const prevValue = String(row?.color_flag || '').trim()
  if (nextValue === prevValue) {
    return
  }

  try {
    await http.put(`/contracts/${row.id}`, {
      color_flag: nextValue,
    })
    row.color_flag = nextValue
    ElMessage.success('颜色标记已更新')
  } catch (error) {
    row.color_flag = prevValue
    ElMessage.error(error?.response?.data?.message || '颜色标记更新失败')
  }
}

const openEditWithSupplementalFields = async (row, fields) => {
  await contractItemRef.value?.openEditWithSupplementalFields(row, fields, {
    readOnly: !hasDepartmentEditPermissionForContract(row),
  })
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
  openAiFolderDialog()
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

    const summary = `导入完成：新增 ${data?.imported_count || 0} 条，更新 ${data?.updated_count || 0} 条，跳过 ${data?.skipped_count || 0} 条。`
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
    importDialogVisible.value = false
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

const buildExportParams = () => ({
  current_management_department: filters.current_management_department || undefined,
  handling_department: filters.handling_department || undefined,
  project: filters.project || undefined,
  color_flag: filters.color_flag || undefined,
  completeness: filters.completeness !== null ? (filters.completeness ? '是' : '否') : undefined,
  keyword: filters.keyword || undefined,
  has_file: filters.has_file || undefined,
  is_archived: filters.is_archived !== null ? (filters.is_archived ? '已归档' : '未归档') : undefined,
})

const exportContractsExcel = async () => {
  exportingExcel.value = true
  try {
    const response = await http.get('/contracts/export-excel', {
      responseType: 'blob',
      params: buildExportParams(),
    })
    const headerName = parseFilenameFromDisposition(response.headers?.['content-disposition'])
    triggerBrowserDownload(response.data, headerName || '合同信息导出.xlsx')
    ElMessage.success('EXCEL 导出成功')
  } catch (error) {
    const message = await parseErrorMessage(error, 'EXCEL 导出失败')
    ElMessage.error(message)
  } finally {
    exportingExcel.value = false
  }
}

const exportGroupReportExcel = async (year) => {
  exportingGroupExcel.value = true
  try {
    const response = await http.get('/contracts/export-group-report-excel', {
      responseType: 'blob',
      params: {
        ...buildExportParams(),
        year,
      },
    })
    const headerName = parseFilenameFromDisposition(response.headers?.['content-disposition'])
    triggerBrowserDownload(response.data, headerName || '集团上报EXCEL.xlsx')
    ElMessage.success(`${year}年集团上报EXCEL导出成功`)
  } catch (error) {
    const message = await parseErrorMessage(error, '集团上报EXCEL导出失败')
    ElMessage.error(message)
  } finally {
    exportingGroupExcel.value = false
  }
}

const handleGroupReportExportCommand = (year) => {
  exportGroupReportExcel(year)
}

const closeAiMatchDialog = () => {
  aiMatchDialogVisible.value = false
  resetAiMatchState()
}

const proceedAiMatchSelection = async (selectedValue) => {
  if (aiMatchLoading.value) {
    ElMessage.info('数据加载中，请稍候')
    return
  }

  const selectedFile = aiParsedUploadFile.value
  const uploadedFilePath = normalizeFolderPath(aiUploadedFilePath.value)
  const parsedFields = aiParsedFields.value || {}

  if (!selectedFile) {
    ElMessage.error('AI上传文件状态已丢失，请重新上传')
    closeAiMatchDialog()
    return
  }
  if (!uploadedFilePath) {
    ElMessage.error('AI上传后的存储路径丢失，请重新上传')
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

const handleAiPdfSelected = async (event) => {
  const file = event?.target?.files?.[0]
  if (!file) {
    return
  }

  const targetFolderPath = normalizeFolderPath(aiUploadTargetFolderPath.value)
  if (!targetFolderPath) {
    ElMessage.warning('请先选择上传目录')
    event.target.value = ''
    return
  }

  if (!/\.pdf$/i.test(file.name)) {
    ElMessage.warning('请上传PDF文件')
    event.target.value = ''
    return
  }

  resetAiMatchState()
  aiParsedUploadFile.value = file
  aiMatchDialogVisible.value = true
  aiMatchLoading.value = true
  aiParsing.value = true
  ElMessage.info('正在上传并解析PDF，请稍候')
  try {
    const uploadFd = new FormData()
    uploadFd.append('folder_path', targetFolderPath)
    uploadFd.append('files', file)

    const uploadResponse = await http.post('/folders/upload', uploadFd, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 300000,
    })

    const uploadedRows = Array.isArray(uploadResponse?.data?.uploaded) ? uploadResponse.data.uploaded : []
    const uploadedPath = normalizeFolderPath(uploadedRows?.[0]?.file_path || '')
    if (!uploadedPath) {
      throw new Error('上传成功但未返回文件路径')
    }
    aiUploadedFilePath.value = uploadedPath

    const { data } = await http.post('/contracts/ai-parse', {
      file_path: uploadedPath,
    }, {
      timeout: 300000,
    })

    const parsedFullbody = data?.fullbody || ''
    const parsedFields = {
      ...(data?.fields || {}),
      fullbody: parsedFullbody,
    }

    aiParsedFields.value = parsedFields
    aiParsedFullbody.value = parsedFullbody
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

const openEdit = (row) => openEditWithSupplementalFields(row, null)

const openFilePreview = (row, event) => {
  event?.preventDefault?.()
  event?.stopPropagation?.()

  const filePath = String(row?.file_path || '').trim()
  if (!filePath) {
    return
  }

  if (!/\.pdf$/i.test(filePath)) {
    ElMessage.warning('仅支持PDF预览，请使用下载功能')
    return
  }

  const previewUrl = buildOcrPreviewUrlFromFilePath(filePath)
  if (!previewUrl) {
    ElMessage.warning('预览地址无效')
    return
  }

  const opened = window.open(previewUrl, '_blank', 'noopener,noreferrer')
  if (!opened) {
    ElMessage.warning('浏览器拦截了新窗口，请允许弹窗后重试')
  }
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

  if (!hasDepartmentEditPermissionForContract(row)) {
    ElMessage.warning('已归档合同仅超管或群晖超管可修改')
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

    contractItemRef.value?.handleContractDeleted(row.id)

    ElMessage.success('删除成功')
    await loadContracts()
  } catch (error) {
    if (error === 'cancel' || error === 'close') {
      return
    }
    ElMessage.error(error?.response?.data?.message || '删除失败')
  }
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


onMounted(async () => {
  try {
    await Promise.all([
      loadCurrentUserPermission(),
      loadDepartments(),
      loadFieldOptions(),
      loadContracts(),
      loadLinkTreeSnapshot(),
    ])
  } catch (_error) {
    ElMessage.error('数据加载失败')
  }
})

watch(aiMatchDialogVisible, (visible) => {
  if (!visible && !aiMatchProcessing.value) {
    resetAiMatchState()
  }
})
</script>

<style scoped>
.header-notice{
  font-size: 14px;
  color: #6b7280;
  margin:0 0 8px 0;
}
.contract-page {
  display: grid;
  border-radius: 18px;
  overflow: hidden;
  background: #fff;
  box-shadow: 0 6px 32px rgba(37, 99, 235, 0.06);
}
/* 让 el-card 也有圆角 */
.contract-page .el-card {
  border-radius: 18px;
  overflow: hidden;
}

.contract-page :deep(.el-scrollbar) {
  padding-bottom: 32px;
}

.contract-page :deep(.el-link__inner) {
  max-width: 100%;
}

:deep(.link-file-dialog) {
  height: 90vh;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.header-actions {
  position: relative;
  top: -4px;
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.pager-top-actions {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.color-filter-trigger {
  width: 32px;
  height: 32px;
  border-radius: 999px;
  border: 1px solid rgba(15, 23, 42, 0.12);
  background: #ffffff;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}

.color-filter-trigger:hover {
  border-color: #dbeafe;
  background: #eff6ff;
}

.apple-button-group {
  display: inline-flex;
  border-radius: 19px;
  padding: 2px;
  background: rgba(255, 255, 255, 0.9);
  border: 1px solid rgba(15, 23, 42, 0.08);
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.12), 0 2px 6px rgba(15, 23, 42, 0.08);
  /*backdrop-filter: blur(8px);*/
}

.apple-button-group :deep(.el-button) {
  border: none;
  border-radius: 0;
  min-height: 34px;
  color: #1f2937;
  background: linear-gradient(180deg, #ffffff 0%, #f9fefa 100%);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.95);
  transition: background 0.2s ease, color 0.2s ease, transform 0.2s ease;
}

.apple-button-group :deep(.el-button + .el-button) {
  margin-left: 0;
  border-left: 1px solid rgba(15, 23, 42, 0.08);
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

.card-title {
  font-size: 18px;
  font-weight: 600;
  margin-right: 12px;
}


.card-num {
  flex-grow: 1;
  display: inline-flex;
  align-items: flex-start;
  gap: 4px;
}

.card-num-tag {
  font-size: 14px;
}
.toolbar {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 16px;
}

.toolbar-row {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
}

.toolbar-row:first-child {
    justify-content: space-between;
}

.contract-table :deep(.el-table__cell) {
  padding-top: 6px;
  padding-bottom: 6px;
}

.color-flag-trigger {
  width: 26px;
  height: 26px;
  border: 1px solid transparent;
  border-radius: 6px;
  background: transparent;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}

.color-flag-trigger:hover {
  border-color: #dbeafe;
  background: #eff6ff;
}

.color-flag-icon {
  font-size: 15px;
  line-height: 1;
}

.color-flag-icon.is-red { color: #ef4444; }
.color-flag-icon.is-orange { color: #f97316; }
.color-flag-icon.is-yellow { color: #eab308; }
.color-flag-icon.is-green { color: #22c55e; }
.color-flag-icon.is-blue { color: #3b82f6; }
.color-flag-icon.is-none { color: #9ca3af; }

.color-flag-dropdown-menu :deep(.el-dropdown-menu__item) {
  min-width: 40px;
  justify-content: center;
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
  flex-grow: 1;
  overflow: hidden;
  
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
  flex-shrink: 0;
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

.no-wrap-cell {
  display: inline-block;
  max-width: 100%;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.pager {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
}

.pager-top {
  margin-bottom: 12px;
  display: flex;
  justify-content: space-between;
}

.field-sort-list {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
  max-height: 60vh;
  overflow: auto;
  padding-right: 4px;
}

.field-sort-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  background: #fff;
  cursor: grab;
  user-select: none;
}

.field-sort-item:active {
  cursor: grabbing;
}

.field-sort-item.is-hidden {
  background: #f9fafb;
  color: #9ca3af;
  opacity: 0.85;
}

.field-sort-item.is-dragging {
  border-color: rgba(37, 99, 235, 0.35);
  box-shadow: 0 10px 24px rgba(37, 99, 235, 0.12);
}

.field-sort-drag-handle {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  color: #6b7280;
  flex-shrink: 0;
  cursor: grab;
}

.field-sort-checkbox {
  flex: 1;
  min-width: 0;
}

.field-sort-checkbox :deep(.el-checkbox__label) {
  white-space: normal;
}

.field-sort-drag-preview {
  position: fixed;
  z-index: 3000;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-width: 180px;
  max-width: 280px;
  padding: 10px 14px;
  border-radius: 12px;
  border: 1px solid rgba(37, 99, 235, 0.18);
  background: rgba(255, 255, 255, 0.96);
  box-shadow: 0 18px 40px rgba(15, 23, 42, 0.2);
  color: #1d4ed8;
  pointer-events: none;
  backdrop-filter: blur(8px);
}

.field-sort-drag-preview-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  flex-shrink: 0;
}

.field-sort-drag-preview-label {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13px;
  font-weight: 600;
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
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  cursor: pointer;
  color: #111827;
  font-weight: 500;
}

.quick-match-log :deep(textarea) {
  font-family: Consolas, 'Courier New', monospace;
  line-height: 1.55;
}

.ai-folder-dialog-tip {
  margin-bottom: 8px;
  color: #4b5563;
  font-size: 13px;
}

.ai-folder-dialog-selected {
  margin-bottom: 10px;
  color: #1f2937;
  font-size: 13px;
  word-break: break-all;
}

.ai-folder-tree-wrap {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 8px;
  min-height: 280px;
  max-height: 56vh;
  overflow: auto;
}

.ai-folder-tree-node {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}

.ai-folder-tree-icon {
  font-size: 16px;
  line-height: 1;
}

.ai-folder-tree-label {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
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
  font-size: 7px!important;
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

  .field-sort-list {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .field-sort-list {
    grid-template-columns: 1fr;
  }
}

.import-dialog-content {
  padding: 10px 0;
}

.import-rules {
  font-size: 14px;
  line-height: 1.8;
  color: #606266;
}

.import-dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
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

.link-file-name-link {
  width: 100%;
  justify-content: flex-start;
}

@media (max-width: 1100px) {
  .link-file-layout {
    grid-template-columns: 1fr;
    height: 100%;
  }
}
</style>
