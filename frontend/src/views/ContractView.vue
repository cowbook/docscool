<template>
  <div class="contract-page" :loading="importingExcel || aiParsing">
    <el-card>
      <template #header>
        <div class="card-header">
          <div class="card-title">所有合同</div>
          <div class="card-num">
            <el-tag type="danger" size="default">{{ totalContracts }} 条</el-tag>
          </div>
          
          <div class="header-actions">
            <el-button-group>
            
              <el-button :loading="importingExcel" :disabled="aiParsing" @click="importDialogVisible = true">
                <Icon :icon="fileTypeExcel" />
                <span>{{ importingExcel ? '导入中...' : '导入Excel' }}</span>
              </el-button>
              <el-button :loading="aiParsing" @click="triggerAiUpload">
                <el-icon><Document /></el-icon>
                <span>{{ aiParsing ? '解析中...' : 'AI上传' }}</span>
              </el-button>
              <el-button :loading="quickMatching" :disabled="aiParsing" @click="openQuickMatchDialog">
                <span>快速批配</span>
              </el-button>
              <el-button type="primary" :disabled="aiParsing" @click="openCreate">
                <el-icon><Plus /></el-icon>
                <span>新建</span>
              </el-button>
            </el-button-group>
          </div>
        </div>
      <div class="header-notice">
        <el-alert
          type="info"
          :closable="false"
          show-icon
          style="margin-top: 12px;"
        >
          <div class="notice-content">
            <span>合同金额单位为元，合同编号必须唯一，归档状态为已归档的只有管理员可以修改</span>
          </div>
        </el-alert>
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
        <div class="toolbar-row">
        
          <el-switch
            v-model="filters.has_file"
            active-text="有文件"
            inactive-text="全部"
            @change="loadContracts"
          />
          <el-switch
            v-model="filters.is_archived"
            active-text="已归档"
            inactive-text="未归档"
            @change="loadContracts"
          />
        </div>
        <div class="toolbar-row">

            <el-select v-model="filters.handling_department" clearable placeholder="按承办部门筛选" style="width: 220px" @change="loadContracts">
            <el-option value="__empty__" label="(空)" />
            <el-option v-for="item in departments" :key="item" :label="item" :value="item" />
          </el-select>
          <el-select v-model="filters.project" clearable placeholder="按项目筛选" style="width: 200px" @change="loadContracts">
            <el-option value="__empty__" label="(空)" />
            <el-option v-for="item in options.project" :key="item" :label="item" :value="item" />
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
      </div>

      <div class="pager-top">
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
            <div v-else>
                <el-icon class="file-miss"><CircleCloseFilled /></el-icon>
                <span class="no-file-name">未上传</span>
            
            </div>
          </template>
        </el-table-column>

        <el-table-column prop="contract_name" label="合同名称" :min-width="contractNameColumnWidth" show-overflow-tooltip sortable>
          <template #default="scope">
            <button class="contract-name-link" type="button" @click.stop="openEdit(scope.row)">
              <span class="contract-name-cell">{{ scope.row.contract_name }}</span>
            </button>
          </template>
        </el-table-column>
        <el-table-column prop="contract_number" label="合同编号" :min-width="contractNumberColumnWidth" sortable show-overflow-tooltip>
          <template #default="scope">
            <span class="no-wrap-cell" :title="scope.row.contract_number || ''">
              {{ scope.row.contract_number || '' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="contract_unit" label="合同单位" min-width="180" show-overflow-tooltip sortable />
        <el-table-column prop="contract_amount" label="合同金额" min-width="120" sortable />
        <el-table-column prop="approval_status" label="审批状态" min-width="100" sortable />
        <el-table-column prop="handler" label="承办人" min-width="100" sortable />
        <el-table-column prop="handling_department" label="承办部门" min-width="130" sortable />
        <el-table-column prop="handling_date" label="承办日期" min-width="110" sortable />
        <el-table-column prop="contract_type" label="合同类型" min-width="110" sortable />
        <el-table-column prop="is_archived" label="是否归档" min-width="90" sortable />
        <el-table-column prop="project" label="项目" min-width="220" show-overflow-tooltip sortable />
     
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
          v-model:page-size="pageSize"
          :total="totalContracts"
          :page-sizes="[50, 100, 200, 500]"
          layout="total, sizes, prev, pager, next, jumper"
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
            border
            resizable
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
            <el-table-column prop="contract_amount" label="金额" min-width="130" />
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
            <div>• 合同编号: 必须唯一，如果编号存在，则更新合同内容</div>
            <div>• 归档状态: 所有导入的合同自动归档到"未归档",已归档的合同由管理员进行修改</div>
            <div>• 合同金额: 从MIS导出的“合同金额（万元”）必须转成元，字段名必须重新命名为“合同金额” </div>
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
         
          <el-button type="primary" @click="triggerExcelUpload">
            <el-icon><Document /></el-icon>
            选择文件
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

    <el-dialog       top="2vh"
 v-model="dialogVisible" :title="editing ? '编辑合同' : '新建合同'" width="min(1380px, 98vw)">
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
                  :show-file-list="false"
                  :http-request="(options) => handleDialogUpload(options.file)"
                >
                  <el-button :icon="Upload" size="small">上传文件</el-button>
                </el-upload>

                <el-button size="small" @click="openLinkFileDialog">链接文件</el-button>

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
          
              <el-form-item label="合同名称"  class="form-item-span-2">
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
              <el-form-item label="项目">
                <el-select v-model="form.project" clearable placeholder="可留空" style="width: 100%" filterable>
                  <el-option v-for="item in options.project" :key="item" :label="item" :value="item" />
                </el-select>
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


        <!-- PDF预览面板 -->
        <div
          class="link-file-preview-panel"
          :class="{ 'preview-panel-clickable': !!linkPreviewUrl && !linkPreviewLoading }"
          style="margin-top: 12px; min-height: 320px; max-height: 480px; overflow: auto; border: 1px solid #eee; border-radius: 4px; background: #fafbfc; display: flex; align-items: center; justify-content: center;"
          @click="openLinkFullscreenPreview"
        >
          <div v-if="linkPreviewLoading" class="preview-placeholder">预览加载中...</div>
          <VuePdfEmbed
            v-else-if="linkPreviewUrl"
            :source="linkPreviewUrl"
            class="pdf-preview-embed"
            style="width: 100%; height: 400px;"
            @rendering-failed="() => { linkPreviewMessage = 'PDF渲染失败'; }"
          />
          <div v-else class="preview-placeholder">{{ linkPreviewMessage }}</div>
        </div>
      </div>

      <template #footer>
        <el-button @click="() => { linkFileDialogVisible = false; if (linkPreviewUrl) { window.URL.revokeObjectURL(linkPreviewUrl); linkPreviewUrl = ''; linkPreviewMessage = '请选择PDF文件进行预览'; linkPreviewLoading = false; } }">取消</el-button>
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
          @rendering-failed="() => { linkPreviewMessage = 'PDF组件渲染失败，请检查文件内容或浏览器兼容性'; }"
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
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Icon } from '@iconify/vue'
import VuePdfEmbed from 'vue-pdf-embed'
import fileTypeWord from '@iconify-icons/vscode-icons/file-type-word'
import fileTypeExcel from '@iconify-icons/vscode-icons/file-type-excel'
import fileTypePdf from '@iconify-icons/vscode-icons/file-type-pdf2'
import microsoftOffice from '@iconify-icons/simple-icons/microsoftoffice'
import { CircleCloseFilled, Delete, Document, Download, Edit, Plus, Upload } from '@element-plus/icons-vue'
import { GlobalWorkerOptions } from 'pdfjs-dist/legacy/build/pdf.mjs'
import PdfWorker from 'pdfjs-dist/legacy/build/pdf.worker.min.mjs?url'

import http from '../api/http'

GlobalWorkerOptions.workerSrc = PdfWorker

const AI_NEW_CONTRACT_VALUE = '__new_contract__'

const contracts = ref([])
const departments = ref([])
const saving = ref(false)
const aiParsing = ref(false)
const quickMatching = ref(false)
const quickMatchDialogVisible = ref(false)
const quickMatchLogText = ref('')
const aiMatchDialogVisible = ref(false)
const aiMatchProcessing = ref(false)
const aiMatchCandidates = ref([])
const aiMatchSelection = ref(AI_NEW_CONTRACT_VALUE)
const aiParsedFields = ref(null)
const aiParsedFullbody = ref('')
const aiParsedUploadFile = ref(null)
const previewFileName = ref('')
const importingExcel = ref(false)
const importDialogVisible = ref(false)
const dialogVisible = ref(false)
const textDialogVisible = ref(false)
const editing = ref(null)
const currentPage = ref(1)
const sortState = reactive({ prop: '', order: '' })

const handleSortChange = ({ prop, order }) => {
  sortState.prop = prop
  sortState.order = order
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
const pendingAiUploadFile = ref(null)
const previewUrl = ref('')
const previewLoading = ref(false)
const previewMessage = ref('暂无文件')
const fullPreviewVisible = ref(false)
const currentPreviewRow = ref(null)
const pageSize = ref(100)

// 链接文件弹窗专用预览状态
const linkPreviewUrl = ref('')
const linkPreviewLoading = ref(false)
const linkPreviewMessage = ref('请选择PDF文件进行预览')
const linkFullPreviewVisible = ref(false)
const linkFileDialogVisible = ref(false)
const linkTreeLoading = ref(false)
const linkFilesLoading = ref(false)
const linkTreeRef = ref(null)
const linkTreeData = ref([])
const linkRootName = ref('/')
const linkSelectedFolderPath = ref('')
const linkSelectedFilePath = ref('')
const linkFiles = ref([])

const linkTreeProps = {
  label: 'name',
  children: 'children',
}

const filters = reactive({
  handling_department: '',
  project: '',
  approval_status: '',
  keyword: '',
  has_file: false,
  is_archived: null,
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

const totalContracts = computed(() => sortedContracts.value ? sortedContracts.value.length : 0)

const quickMatchTargetIds = computed(() => {
  return (contracts.value || [])
    .filter((row) => (row?.is_archived || '').trim() !== '已归档' && !String(row?.file_path || '').trim())
    .map((row) => Number(row?.id))
    .filter((id) => Number.isInteger(id) && id > 0)
})

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
  contract_amount: '',
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
  form.contract_amount = ''
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
      project: filters.project || undefined,
      approval_status: filters.approval_status || undefined,
      keyword: filters.keyword || undefined,
      has_file: filters.has_file || undefined,
      is_archived: filters.is_archived !== null ? (filters.is_archived ? '已归档' : '未归档') : undefined,
    },
  })
  contracts.value = data
  currentPage.value = 1
}

const normalizePath = (value) => String(value || '').replace(/\\/g, '/').replace(/^\/+|\/+$/g, '')

const fetchLinkFolderChildren = async (parentPath = '') => {
  const { data } = await http.get('/folders/children', {
    params: { parent_path: normalizePath(parentPath) },
  })
  return Array.isArray(data?.children) ? data.children : []
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

const openLinkFileDialog = async () => {
  linkFileDialogVisible.value = true
  linkTreeLoading.value = true
  linkSelectedFilePath.value = form.file_path || ''
  // 弹窗打开时清空预览
  if (linkPreviewUrl.value) {
    window.URL.revokeObjectURL(linkPreviewUrl.value)
  }
  linkPreviewUrl.value = ''
  linkPreviewMessage.value = '请选择PDF文件进行预览'
  linkPreviewLoading.value = false
  try {
    const { data } = await http.get('/folders/tree')
    const root = data?.root || { name: '/', path: '' }
    linkRootName.value = root.name || '/'
    linkTreeData.value = await fetchLinkFolderChildren('')

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
  await loadLinkFiles(node?.path || '')
}

const openLinkFilePreview = async (filePath) => {
  const targetPath = String(filePath || '').trim()
  if (!targetPath) {
    return
  }
  // 只影响弹窗内预览，不影响主窗口
  if (getFileExt(targetPath) !== 'pdf') {
    linkPreviewUrl.value = ''
    linkPreviewMessage.value = '该文件不是PDF，无法预览'
    linkPreviewLoading.value = false
    return
  }
  linkPreviewLoading.value = true
  linkPreviewMessage.value = ''
  try {
    const response = await http.get('/folders/file-preview', {
      params: { path: targetPath },
      responseType: 'blob',
    })
    // 生成blob url
    if (linkPreviewUrl.value) {
      window.URL.revokeObjectURL(linkPreviewUrl.value)
    }
    const blob = response.data
    linkPreviewUrl.value = window.URL.createObjectURL(blob)
    linkPreviewMessage.value = ''
  } catch (error) {
    const message = await parseErrorMessage(error, '文件预览加载失败')
    linkPreviewUrl.value = ''
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

const getParentPath = (value) => {
  const path = normalizePath(value)
  if (!path) {
    return ''
  }
  const idx = path.lastIndexOf('/')
  return idx >= 0 ? path.slice(0, idx) : ''
}

const confirmLinkFile = async () => {
  const selectedPath = linkSelectedFilePath.value || ''
  if (!selectedPath) {
    ElMessage.warning('请选择一个文件')
    return
  }

  form.file_path = selectedPath
  if (editing.value?.id) {
    try {
      await http.put(`/contracts/${editing.value.id}`, {
        file_path: selectedPath,
      })
      if (editing.value) {
        editing.value.file_path = selectedPath
      }
      if (currentPreviewRow.value?.id === editing.value?.id) {
        currentPreviewRow.value.file_path = selectedPath
      }
      ElMessage.success('链接文件成功')
      await loadContracts()
    } catch (error) {
      ElMessage.error(error?.response?.data?.message || '链接文件失败')
      return
    }
  } else {
    ElMessage.success('已选择文件，保存合同后生效')
  }

  await syncMainPreviewFromLinkedFile(selectedPath)

  linkFileDialogVisible.value = false
}

const quickMatchInstructionText = () => {
  return [
    '快速批配说明：',
    '1. 本功能会处理“未归档 且 无附件”的合同。',
    '2. 处理方式：在合同管理存储空间中扫描所有文件夹/子文件夹的 PDF 文件。',
    '3. 匹配规则：文件名包含合同名称时视为候选；仅 1 个候选则直接匹配；多个候选按文件名相似度选择最佳项。',
    '4. 成功后会把匹配到的文件路径写入合同 file_path。',
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
    appendQuickMatchLog(`执行失败：${error?.response?.data?.message || '请求失败'}`)
    ElMessage.error(error?.response?.data?.message || '快速批配执行失败')
  } finally {
    quickMatching.value = false
  }
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
    ['contract_amount', 'contract_amount'],
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

const applyParsedFields = (fields) => {
  form.contract_name = fields?.contract_name || ''
  form.contract_number = fields?.contract_number || ''
  form.contract_unit = fields?.contract_unit || ''
  form.contract_amount = normalizeAmountInputValue(fields?.contract_amount || '')
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

const runAiRecognitionFromPreview = async () => {
  if (aiParsing.value) {
    return
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

  aiParsing.value = true
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
    aiParsing.value = false
  }
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
  form.contract_amount = normalizeAmountInputValue(form.contract_amount)
}

const saveContract = async () => {
  const normalizedAmount = normalizeAmountInputValue(form.contract_amount)

  if (!form.contract_name || !form.handling_department || !normalizedAmount) {
    ElMessage.warning('请填写必要字段')
    return
  }

  if (!/^\d+(?:\.\d+)?$/.test(normalizedAmount)) {
    ElMessage.warning('合同金额请输入纯数字，可带小数点')
    return
  }

  form.contract_amount = normalizedAmount

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
        file_path: form.file_path,
        contract_number: form.contract_number,
        contract_name: form.contract_name,
        contract_unit: form.contract_unit,
        contract_amount: normalizedAmount,
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
        file_path: form.file_path,
        contract_number: form.contract_number,
        contract_name: form.contract_name,
        contract_unit: form.contract_unit,
        contract_amount: normalizedAmount,
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

.el-link__inner{
  max-width:100%;
}

.link-file-dialog {
  height: 90vh;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
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

.quick-match-log :deep(textarea) {
  font-family: Consolas, 'Courier New', monospace;
  line-height: 1.55;
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
