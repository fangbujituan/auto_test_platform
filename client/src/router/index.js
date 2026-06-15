import { createRouter, createWebHistory } from 'vue-router'
import Login from '../views/Login.vue'
import Dashboard from '../views/Dashboard.vue'
import ProjectList from '../views/ProjectList.vue'
import ProjectMembers from '../views/ProjectMembers.vue'
import SystemInit from '../views/SystemInit.vue'
import ProjectDetail from '../views/ProjectDetail.vue'
import TestCaseManagement from '../views/TestCaseManagement.vue'
import BugManagementNew from '../views/BugManagementNew.vue'
import RequirementManagement from '../views/RequirementManagement.vue'
import RequirementDetail from '../views/RequirementDetail.vue'
import Toolbox from '../views/Toolbox.vue'
import AutomationManagement from '../views/AutomationManagement.vue'
import Settings from '../views/Settings.vue'

const routes = [
  {
    path: '/',
    redirect: '/dashboard'
  },
  {
    path: '/login',
    name: 'Login',
    component: Login
  },
  {
    path: '/init',
    name: 'SystemInit',
    component: SystemInit
  },
  {
    path: '/dashboard',
    name: 'Dashboard',
    component: Dashboard,
    meta: { requiresAuth: true }
  },

  {
    path: '/projects',
    name: 'ProjectList',
    component: ProjectList,
    meta: { requiresAuth: true }
  },
  {
    path: '/projects/:projectId',
    name: 'ProjectDetail',
    component: ProjectDetail,
    meta: { requiresAuth: true }
  },
  {
    path: '/projects/:projectId/members',
    name: 'ProjectMembers',
    component: ProjectMembers,
    meta: { requiresAuth: true }
  },
  {
    path: '/projects/:projectId/requirements',
    name: 'RequirementManagement',
    component: RequirementManagement,
    meta: { requiresAuth: true }
  },
  {
    path: '/projects/:projectId/requirements/:reqId',
    name: 'RequirementDetail',
    component: RequirementDetail,
    meta: { requiresAuth: true }
  },
  {
    path: '/projects/:projectId/bugs',
    name: 'BugManagement',
    component: BugManagementNew,
    meta: { requiresAuth: true }
  },
  {
    path: '/projects/:projectId/bugs-new',
    name: 'BugManagementNew',
    component: BugManagementNew,
    meta: { requiresAuth: true }
  },
  {
    path: '/projects/:projectId/test-cases',
    name: 'TestCaseManagement',
    component: TestCaseManagement,
    meta: { requiresAuth: true }
  },
  {
    path: '/projects/:projectId/automations',
    name: 'AutomationManagement',
    component: AutomationManagement,
    meta: { requiresAuth: true }
  },
  {
    path: '/toolbox',
    name: 'Toolbox',
    component: Toolbox,
    meta: { requiresAuth: true }
  },
  {
    path: '/settings',
    name: 'Settings',
    component: Settings,
    meta: { requiresAuth: true }
  },
  {
    path: '/ai-settings',
    redirect: '/settings?tab=ai'
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// 路由守卫
router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('token')
  
  if (to.meta.requiresAuth && !token) {
    next('/login')
  } else {
    next()
  }
})

// 动态页签标题
router.afterEach((to) => {
  const defaultTitle = 'Auto P'
  if (to.params.projectId && to.query.projectName) {
    document.title = `${to.query.projectName}`
  } else {
    document.title = defaultTitle
  }
})

export default router
