<template>
  <div class="project-page">
    <el-card>
      <template #header>
        <div class="card-header">
          <div class="card-title">项目设置</div>
        </div>
      </template>

      <div v-if="canManage" class="toolbar">
        <el-input
          v-model="newProject"
          maxlength="255"
          show-word-limit
          placeholder="输入项目名称"
          style="max-width: 420px"
          @keyup.enter="addProject"
        />
        <el-button type="primary" :loading="saving" @click="addProject">新增项目</el-button>
      </div>
      <div v-else class="readonly-hint">当前账号仅有查看权限</div>

      <el-table :data="projects" stripe>
        <el-table-column prop="name" label="项目名称" min-width="320" show-overflow-tooltip />
        <el-table-column prop="created_at" label="创建时间" min-width="220" />
        <el-table-column v-if="canManage" label="操作" width="120" fixed="right">
          <template #default="scope">
            <el-button type="danger" size="small" @click="removeProject(scope.row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import http from '../api/http'

const projects = ref([])
const newProject = ref('')
const saving = ref(false)
const userPermission = ref('view')
const canManage = computed(() => userPermission.value === 'super_admin')

const loadProjects = async () => {
  const { data } = await http.get('/settings/projects')
  projects.value = Array.isArray(data) ? data : []
}

const loadCurrentPermission = async () => {
  try {
    const { data } = await http.get('/settings/users/current-permission')
    userPermission.value = String(data?.permission || 'view').trim() || 'view'
  } catch (_error) {
    userPermission.value = 'view'
  }
}

const addProject = async () => {
  if (!canManage.value) {
    ElMessage.warning('当前账号仅有查看权限')
    return
  }

  const name = newProject.value.trim()
  if (!name) {
    ElMessage.warning('请输入项目名称')
    return
  }

  saving.value = true
  try {
    await http.post('/settings/projects', { name })
    newProject.value = ''
    ElMessage.success('新增成功')
    await loadProjects()
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || '新增失败')
  } finally {
    saving.value = false
  }
}

const removeProject = async (row) => {
  if (!canManage.value) {
    ElMessage.warning('当前账号仅有查看权限')
    return
  }

  try {
    await ElMessageBox.confirm(`确认删除项目：${row.name}？`, '提示', {
      type: 'warning',
    })
    await http.delete(`/settings/projects/${row.id}`)
    ElMessage.success('删除成功')
    await loadProjects()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error?.response?.data?.message || '删除失败')
    }
  }
}

onMounted(async () => {
  try {
    await Promise.all([loadCurrentPermission(), loadProjects()])
  } catch (_error) {
    ElMessage.error('项目列表加载失败')
  }
})
</script>

<style scoped>
.project-page {
  display: grid;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.card-title {
  font-size: 18px;
  font-weight: 600;
}

.toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 16px;
}

.readonly-hint {
  margin-bottom: 16px;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
</style>
