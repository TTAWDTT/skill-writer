import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    name: 'Home',
    component: () => import('../views/Home.vue')
  },
  {
    path: '/create-skill',
    name: 'SkillCreator',
    component: () => import('../views/SkillCreator.vue')
  },
  {
    path: '/skill/:skillId',
    name: 'SkillDetail',
    component: () => import('../views/SkillDetail.vue')
  },
  {
    path: '/write/:skillId',
    name: 'Write',
    component: () => import('../views/Write.vue')
  },
  {
    path: '/documents',
    name: 'Documents',
    component: () => import('../views/Documents.vue')
  },
  {
    path: '/settings',
    name: 'Settings',
    component: () => import('../views/Settings.vue')
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
