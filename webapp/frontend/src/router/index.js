import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    name: 'Home',
    component: () => import('@/views/HomeView.vue'),
    meta: { title: 'ホーム' },
  },
  {
    path: '/projects/:projectId',
    name: 'Project',
    component: () => import('@/views/ProjectView.vue'),
    meta: { title: 'プロジェクト' },
  },
  {
    path: '/videos/:videoId',
    name: 'VideoEditor',
    component: () => import('@/views/VideoEditorView.vue'),
    meta: { title: '動画編集' },
  },
  {
    path: '/settings',
    name: 'Settings',
    component: () => import('@/views/SettingsView.vue'),
    meta: { title: '設定' },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// ページタイトルを自動設定
router.afterEach((to) => {
  document.title = to.meta.title
    ? `${to.meta.title} — AI-MovGen`
    : 'AI-MovGen'
})

export default router
