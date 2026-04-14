<template>
  <div class="shell">
    <el-container class="shell-container">
      <el-aside v-if="!isMobile" width="240px" class="sidebar">
        <div class="logo">DocsCool</div>
        <el-menu :default-active="activePath" router class="menu">
          <el-menu-item index="/home">
            <el-icon><House /></el-icon>
            <span>首页</span>
          </el-menu-item>
          <el-sub-menu index="/contracts">
            <template #title>
              <el-icon><Document /></el-icon>
              <span>合同管理</span>
            </template>
            <el-menu-item index="/contracts/all">
              <el-icon><Tickets /></el-icon>
              <span>所有合同</span>
            </el-menu-item>
            <el-menu-item index="/contracts/folders">
              <el-icon><Folder /></el-icon>
              <span>文件夹</span>
            </el-menu-item>
          </el-sub-menu>
          <el-sub-menu index="/settings">
            <template #title>
              <el-icon><Setting /></el-icon>
              <span>系统设置</span>
            </template>
            <el-menu-item index="/settings/departments">
              <el-icon><OfficeBuilding /></el-icon>
              <span>部门设置</span>
            </el-menu-item>
            <el-menu-item index="/settings/projects">
              <el-icon><CollectionTag /></el-icon>
              <span>项目设置</span>
            </el-menu-item>
            <el-menu-item index="/settings/logout">
              <el-icon><SwitchButton /></el-icon>
              <span>退出</span>
            </el-menu-item>
          </el-sub-menu>
        </el-menu>
      </el-aside>

      <el-container>
        <el-header class="topbar">
          <div class="topbar-left">
            <el-button v-if="isMobile" text @click="drawer = true">菜单</el-button>
            <div class="page-title">{{ pageTitle }}</div>
          </div>
          <div class="user-box">
            <el-avatar :size="32" class="user-avatar">{{ avatarText }}</el-avatar>
            <span>{{ username }}</span>
          </div>
        </el-header>
        <el-main class="content">
          <router-view />
        </el-main>
      </el-container>
    </el-container>

    <el-drawer v-model="drawer" :with-header="false" size="240px" direction="ltr">
      <div class="logo">DocsCool</div>
      <el-menu :default-active="activePath" router class="menu" @select="onSelectMenu">
        <el-menu-item index="/home">
          <el-icon><House /></el-icon>
          <span>首页</span>
        </el-menu-item>
        <el-sub-menu index="/contracts-mobile">
          <template #title>
            <el-icon><Document /></el-icon>
            <span>合同管理</span>
          </template>
          <el-menu-item index="/contracts/all">
            <el-icon><Tickets /></el-icon>
            <span>所有合同</span>
          </el-menu-item>
          <el-menu-item index="/contracts/folders">
            <el-icon><Folder /></el-icon>
            <span>文件夹</span>
          </el-menu-item>
        </el-sub-menu>
        <el-sub-menu index="/settings-mobile">
          <template #title>
            <el-icon><Setting /></el-icon>
            <span>系统设置</span>
          </template>
          <el-menu-item index="/settings/departments">
            <el-icon><OfficeBuilding /></el-icon>
            <span>部门设置</span>
          </el-menu-item>
          <el-menu-item index="/settings/projects">
            <el-icon><CollectionTag /></el-icon>
            <span>项目设置</span>
          </el-menu-item>
          <el-menu-item index="/settings/logout">
            <el-icon><SwitchButton /></el-icon>
            <span>退出</span>
          </el-menu-item>
        </el-sub-menu>
      </el-menu>
    </el-drawer>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { CollectionTag, Document, Folder, House, OfficeBuilding, Setting, SwitchButton, Tickets } from '@element-plus/icons-vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const drawer = ref(false)
const isMobile = ref(false)
const username = localStorage.getItem('username') || '未登录用户'
const avatarText = computed(() => {
  const text = username.trim()
  if (!text) {
    return 'U'
  }
  return text.slice(0, 1).toUpperCase()
})

const activePath = computed(() => route.path)

const pageTitle = computed(() => {
  if (route.path === '/home') return '首页'
  if (route.path === '/contracts/folders') return '文件夹'
  if (route.path.startsWith('/contracts')) return '合同管理'
  if (route.path === '/settings/departments') return '部门设置'
  if (route.path === '/settings/projects') return '项目设置'
  if (route.path.startsWith('/settings')) return '系统设置'
  return 'DocsCool'
})

const detectMobile = () => {
  isMobile.value = window.innerWidth <= 900
}

const onSelectMenu = () => {
  drawer.value = false
}

onMounted(() => {
  detectMobile()
  window.addEventListener('resize', detectMobile)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', detectMobile)
})
</script>

<style scoped>
.shell {
  min-height: 100vh;
}

.shell-container {
  min-height: 100vh;
}

.sidebar {
  border-right: 1px solid #e5e7eb;
  background: #ffffff;
}

.logo {
  height: 64px;
  padding: 0 20px;
  display: flex;
  align-items: center;
  font-size: 22px;
  font-weight: 700;
  color: #0f172a;
  border-bottom: 1px solid #e5e7eb;
}

.menu {
  border-right: none;
}

.topbar {
  height: 64px;
  background: #ffffff;
  border-bottom: 1px solid #e5e7eb;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
}

.topbar-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.page-title {
  font-size: 18px;
  font-weight: 600;
  color: #111827;
}

.user-box {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #4b5563;
}

.user-avatar {
  background: linear-gradient(135deg, #2563eb, #0ea5e9);
  color: #ffffff;
  font-weight: 600;
}

.content {
  padding: 16px;
}

@media (max-width: 900px) {
  .content {
    padding: 12px;
  }
}
</style>
