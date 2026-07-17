<template>
  <div class="shell">
    <div class="bg-orb orb-left" />
    <div class="bg-orb orb-right" />

    <el-container class="shell-container">
      <el-header class="topbar">
        <div class="topbar-left">

          <div class="logo">
            <Icon :icon="docIcon" style="font-size:26px;color:#2563eb;margin-right:8px;vertical-align:middle;" />
            <span style="vertical-align:middle;">DocsCool</span>
          </div>

          <el-button v-if="isMobile" class="mobile-menu-btn" @click="drawer = true">菜单</el-button>

          <el-menu
            v-else
            :default-active="activePath"
            :ellipsis="false"
            popper-class="top-nav-popper"
            router
            mode="horizontal"
            class="menu top-nav"
          >
            <el-menu-item index="/home">
              <Icon :icon="homeIcon" style="font-size:18px;vertical-align:middle;margin-right:6px;" />
              <span>首页</span>
            </el-menu-item>
            <el-sub-menu index="/contracts">
              <template #title>
                <Icon :icon="docIcon" style="font-size:18px;vertical-align:middle;margin-right:6px;" />
                <span>合同管理</span>
              </template>
              <el-menu-item index="/contracts/all">
                <Icon :icon="ticketsIcon" style="font-size:18px;vertical-align:middle;margin-right:6px;" />
                <span>数据表格</span>
              </el-menu-item>
              <el-menu-item index="/contracts/folders">
                <Icon :icon="folderIcon" style="font-size:18px;vertical-align:middle;margin-right:6px;" />
                <span>文件档案</span>
              </el-menu-item>
              <el-menu-item index="/contracts/scan">
                <span class="menu-inline-icon menu-inline-icon-scanner" aria-hidden="true">
                  <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M5 8.5h14a2 2 0 0 1 2 2V16a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-5.5a2 2 0 0 1 2-2Z" stroke="currentColor" stroke-width="1.8"/>
                    <path d="M7 6h10" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
                    <path d="M7.5 12.2h9" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
                    <path d="M9 15.2h6" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
                    <path d="M7.2 17.8h9.6" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
                  </svg>
                </span>
                <span>合同扫描</span>
              </el-menu-item>
            </el-sub-menu>
            <el-sub-menu index="/settings">
              <template #title>
                <Icon :icon="settingIcon" style="font-size:18px;vertical-align:middle;margin-right:6px;" />
                <span>系统设置</span>
              </template>
              <el-menu-item index="/settings/departments">
                <Icon :icon="officeIcon" style="font-size:18px;vertical-align:middle;margin-right:6px;" />
                <span>部门设置</span>
              </el-menu-item>
              <el-menu-item index="/settings/projects">
                <Icon :icon="projectIcon" style="font-size:18px;vertical-align:middle;margin-right:6px;" />
                <span>项目设置</span>
              </el-menu-item>
              <el-menu-item index="/settings/stamp-tax-rates">
                <span class="menu-inline-icon menu-inline-icon-money" aria-hidden="true">
                  <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="1.8"/>
                    <path d="M8.8 8.4h6.4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
                    <path d="M12 8.4v7.2" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
                    <path d="M9.4 11.8H12" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
                    <path d="M10.1 15.6h3.8" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
                  </svg>
                </span>
                <span>印花税率</span>
              </el-menu-item>
              <el-menu-item v-if="canShowUserPermissionMenu" index="/settings/users">
                <Icon :icon="userPermissionIcon" style="font-size:18px;vertical-align:middle;margin-right:6px;" />
                <span>用户权限</span>
              </el-menu-item>
            </el-sub-menu>
          </el-menu>
        </div>

        <div class="topbar-right">

          
          

          
          
          
          
          <el-dropdown trigger="hover" @command="onUserMenuCommand">
            <div class="user-box" tabindex="0" role="button" aria-label="用户菜单">
              <el-avatar :size="32" class="user-avatar">{{ avatarText }}</el-avatar>
              <span class="user-name">{{ username }}</span>
            </div>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="password">
                  <Icon :icon="passwordIcon" style="font-size:16px;vertical-align:middle;margin-right:6px;" />
                  密码修改
                </el-dropdown-item>
                <el-dropdown-item command="logout">
                  <Icon :icon="logoutIcon" style="font-size:16px;vertical-align:middle;margin-right:6px;" />
                  退出
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>

      <el-main class="content">
        <router-view />
      </el-main>
    </el-container>

    <el-drawer v-model="drawer" :with-header="false" size="440px" direction="ltr">
      <div class="logo">
        <Icon :icon="docIcon" style="font-size:28px;color:#2563eb;margin-right:8px;vertical-align:middle;" />
        <span style="vertical-align:middle;">DocsCool</span>
      </div>

      <el-menu :default-active="activePath" router class="menu" @select="onSelectMenu">
        
        <el-menu-item index="/home">
          <Icon :icon="homeIcon" style="font-size:20px;vertical-align:middle;" />
          <span>首页</span>
        </el-menu-item>

        <el-sub-menu index="/contracts-mobile">
          <template #title>
            <Icon :icon="docIcon" style="font-size:20px;vertical-align:middle;" />
            <span>合同管理</span>
          </template>
          <el-menu-item index="/contracts/all">
            <Icon :icon="ticketsIcon" style="font-size:20px;vertical-align:middle;" />
            <span>数据表格</span>
          </el-menu-item>
          <el-menu-item index="/contracts/folders">
            <Icon :icon="folderIcon" style="font-size:20px;vertical-align:middle;" />
            <span>文件档案</span>
          </el-menu-item>
          <el-menu-item index="/contracts/scan">
            <span class="menu-inline-icon menu-inline-icon-scanner" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M5 8.5h14a2 2 0 0 1 2 2V16a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-5.5a2 2 0 0 1 2-2Z" stroke="currentColor" stroke-width="1.8"/>
                <path d="M7 6h10" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
                <path d="M7.5 12.2h9" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
                <path d="M9 15.2h6" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
                <path d="M7.2 17.8h9.6" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
              </svg>
            </span>
            <span>合同扫描</span>
          </el-menu-item>
        </el-sub-menu>

        <el-sub-menu index="/settings-mobile">
          <template #title>
            <Icon :icon="settingIcon" style="font-size:20px;vertical-align:middle;" />
            <span>系统设置</span>
          </template>
          <el-menu-item index="/settings/departments">
            <Icon :icon="officeIcon" style="font-size:20px;vertical-align:middle;" />
            <span>部门设置</span>
          </el-menu-item>
          <el-menu-item index="/settings/projects">
            <Icon :icon="projectIcon" style="font-size:20px;vertical-align:middle;" />
            <span>项目设置</span>
          </el-menu-item>
          <el-menu-item index="/settings/stamp-tax-rates">
            <span class="menu-inline-icon menu-inline-icon-money" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="1.8"/>
                <path d="M8.8 8.4h6.4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
                <path d="M12 8.4v7.2" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
                <path d="M9.4 11.8H12" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
                <path d="M10.1 15.6h3.8" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
              </svg>
            </span>
            <span>印花税率</span>
          </el-menu-item>
          <el-menu-item v-if="canShowUserPermissionMenu" index="/settings/users">
            <Icon :icon="userPermissionIcon" style="font-size:20px;vertical-align:middle;" />
            <span>用户权限</span>
          </el-menu-item>
        </el-sub-menu>
      </el-menu>
    </el-drawer>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import homeIcon from '@iconify-icons/tabler/home'
import docIcon from '@iconify-icons/tabler/file-text'
import ticketsIcon from '@iconify-icons/tabler/certificate'
import folderIcon from '@iconify-icons/tabler/folder'
import settingIcon from '@iconify-icons/tabler/settings'
import officeIcon from '@iconify-icons/tabler/building'
import projectIcon from '@iconify-icons/tabler/tag'
import userPermissionIcon from '@iconify-icons/tabler/users-group'
import passwordIcon from '@iconify-icons/tabler/password-user'
import logoutIcon from '@iconify-icons/tabler/logout'
import http from '../api/http'

const route = useRoute()
const router = useRouter()
const drawer = ref(false)
const isMobile = ref(false)
const username = localStorage.getItem('username') || '未登录用户'
const currentUserRole = ref('admin')
const avatarText = computed(() => {
  const text = username.trim()
  if (!text) {
    return 'U'
  }
  return text.slice(0, 1).toUpperCase()
})

const canShowUserPermissionMenu = computed(() => {
  const normalizedUsername = String(username || '').trim().toLowerCase()
  if (normalizedUsername === 'zhangyan') {
    return true
  }
  return ['super_admin', 'synology_super_admin'].includes(String(currentUserRole.value || '').trim())
})

const activePath = computed(() => route.path)

const pageTitle = computed(() => {
  if (route.path === '/home') return '首页'
  if (route.path === '/contracts/folders') return '文件夹'
  if (route.path === '/contracts/scan') return '合同扫描'
  if (route.path.startsWith('/contracts')) return '合同管理'
  if (route.path === '/settings/departments') return '部门设置'
  if (route.path === '/settings/projects') return '项目设置'
  if (route.path === '/settings/stamp-tax-rates') return '印花税率'
  if (route.path === '/settings/users') return '用户权限'
  if (route.path === '/settings/password') return '密码修改'
  if (route.path.startsWith('/settings')) return '系统设置'
  return 'DocsCool'
})

const detectMobile = () => {
  isMobile.value = window.innerWidth <= 900
}

const onSelectMenu = () => {
  drawer.value = false
}

const onUserMenuCommand = (command) => {
  if (command === 'password') {
    router.push('/settings/password')
    return
  }
  if (command === 'logout') {
    router.push('/settings/logout')
  }
}

const loadCurrentUserPermission = async () => {
  try {
    const { data } = await http.get('/settings/users/current-permission')
    currentUserRole.value = String(data?.role || 'admin').trim() || 'admin'
  } catch (_error) {
    currentUserRole.value = 'admin'
  }
}

onMounted(() => {
  detectMobile()
  window.addEventListener('resize', detectMobile)
  loadCurrentUserPermission()
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', detectMobile)
})
</script>

<style scoped>
.shell {
  min-height: 100vh;
  position: relative;
  overflow: hidden;
}

.shell-container {
  min-height: 100vh;
  position: relative;
  z-index: 1;
}

.bg-orb {
  position: absolute;
  border-radius: 999px;
  filter: blur(80px);
  opacity: 0.42;
  pointer-events: none;
}

.orb-left {
  width: 360px;
  height: 360px;
  top: -110px;
  left: -80px;
  background: #a7d8ff;
}

.orb-right {
  width: 380px;
  height: 380px;
  right: -120px;
  top: 40px;
  background: #d6e3ff;
}

.logo {
  height: 56px;
  padding: 0 10px 0 6px;
  display: flex;
  align-items: center;
  font-size: 21px;
  font-weight: 700;
  color: #0b2148;
  letter-spacing: 0.01em;
}

.menu {
  border-right: none;
  margin-left:90px;
}

.menu-inline-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  vertical-align: middle;
  margin-right: 6px;
  color: currentColor;
}

.menu-inline-icon svg {
  display: block;
  width: 18px;
  height: 18px;
}

.topbar {
  height: 74px;
  margin: 14px 14px 6px;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.66);
  border: 1px solid rgba(255, 255, 255, 0.65);
  box-shadow: 0 14px 36px rgba(38, 66, 118, 0.12);
  backdrop-filter: blur(16px);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 14px;
}

.topbar-left {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  min-width: 0;
}

.topbar-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.user-box {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #35507e;
  background: rgba(255, 255, 255, 0.64);
  border: 1px solid rgba(255, 255, 255, 0.8);
  border-radius: 999px;
  padding: 4px 10px 4px 4px;
  cursor: pointer;
  transition: background-color 0.2s ease, border-color 0.2s ease;
}

.user-box:hover,
.user-box:focus-visible {
  background: rgba(255, 255, 255, 0.82);
  border-color: rgba(106, 149, 225, 0.5);
  outline: none;
}

.user-name {
  max-width: 120px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.user-avatar {
  background: linear-gradient(135deg, #3f7cff, #56a2ff);
  color: #ffffff;
  font-weight: 600;
}

.page-title {
  font-size: 15px;
  font-weight: 600;
  color: #37598d;
  background: rgba(255, 255, 255, 0.52);
  border: 1px solid rgba(255, 255, 255, 0.72);
  border-radius: 999px;
  padding: 6px 12px;
}

.top-nav {
  border-bottom: none;
  background: transparent;
  flex: 1;
  min-width: 0;
}

.mobile-menu-btn {
  border-radius: 999px;
  border: 1px solid rgba(56, 104, 183, 0.18);
  color: #2f5ea8;
  background: rgba(255, 255, 255, 0.68);
}

.content {
  padding: 14px;
}

:deep(.top-nav.el-menu--horizontal > .el-menu-item),
:deep(.top-nav.el-menu--horizontal > .el-sub-menu .el-sub-menu__title) {
  height: 52px;
  line-height: 52px;
  border-radius: 12px;
  color: #2f4f82;
  border-bottom: none;
  margin: 0 2px;
}

:deep(.top-nav.el-menu--horizontal > .el-menu-item.is-active),
:deep(.top-nav.el-menu--horizontal > .el-sub-menu.is-active .el-sub-menu__title) {
  color: #1e64d9;
  background: rgba(79, 141, 255, 0.12);
}

:deep(.top-nav.el-menu--horizontal > .el-menu-item:hover),
:deep(.top-nav.el-menu--horizontal > .el-sub-menu .el-sub-menu__title:hover) {
  color: #1d5fcc;
  background: rgba(79, 141, 255, 0.08);
}

:deep(.el-menu--popup) {
  padding: 8px;
  border-radius: 14px;
  border: 1px solid rgba(255, 255, 255, 0.72);
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(12px);
  box-shadow: 0 14px 28px rgba(37, 60, 105, 0.12);
}

:deep(.el-menu--popup .el-menu-item) {
  border-radius: 10px;
  color: #365b91;
}

:deep(.el-menu--popup .el-menu-item:hover) {
  background: rgba(79, 141, 255, 0.1);
}

@media (max-width: 900px) {
  .topbar {
    margin: 10px 10px 4px;
    height: 64px;
  }

  .logo {
    font-size: 19px;
    padding-right: 0;
  }

  .topbar-right {
    gap: 8px;
  }

  .page-title {
    display: none;
  }

  .user-name {
    display: none;
  }

  .content {
    padding: 12px;
  }
}
</style>

<style>
.top-nav-popper {
  border-radius: 14px;
  overflow: hidden;
  box-shadow: 0px 0px 4px rgba(0, 0, 0, 0.08), 0px 4px 12px rgba(0, 0, 0, 0.12);
}

.top-nav-popper.el-popper,
.top-nav-popper .el-menu {
  border-radius: 14px;
}
</style>
