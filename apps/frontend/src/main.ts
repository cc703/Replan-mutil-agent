import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import { ElButton, ElDialog } from 'element-plus'
import 'element-plus/es/components/button/style/css'
import 'element-plus/es/components/dialog/style/css'
import App from './app.vue'
import './style.css'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/plan' },
    { path: '/plan', component: () => import('./pages/plan.vue') },
    { path: '/workbench', component: () => import('./pages/workbench.vue') },
    { path: '/chat', component: () => import('./pages/chat.vue') },
    { path: '/versions', component: () => import('./pages/versions.vue') },
    { path: '/resources', component: () => import('./pages/inventory.vue') },
    { path: '/tasks', component: () => import('./pages/inventory.vue') },
    { path: '/import', component: () => import('./pages/import.vue') },
    { path: '/sim', component: () => import('./pages/sim.vue') },
  ],
})
createApp(App).use(router).use(ElButton).use(ElDialog).mount('#app')
