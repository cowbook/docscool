import { createRouter, createWebHistory } from 'vue-router'

import LoginView from './views/LoginView.vue'
import MainLayout from './views/MainLayout.vue'
import HomeView from './views/HomeView.vue'
import ContractView from './views/ContractView.vue'
import LogoutView from './views/LogoutView.vue'
import DepartmentSettingsView from './views/DepartmentSettingsView.vue'
import ProjectSettingsView from './views/ProjectSettingsView.vue'

const routes = [
  { path: '/login', component: LoginView },
  {
    path: '/',
    component: MainLayout,
    children: [
      { path: '', redirect: '/home' },
      { path: 'home', component: HomeView },
      { path: 'contracts/all', component: ContractView },
      { path: 'settings/departments', component: DepartmentSettingsView },
      { path: 'settings/projects', component: ProjectSettingsView },
      { path: 'settings/logout', component: LogoutView },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to, _from, next) => {
  const token = localStorage.getItem('token')
  if (to.path !== '/login' && !token) {
    next('/login')
    return
  }
  if (to.path === '/login' && token) {
    next('/home')
    return
  }
  next()
})

export default router
