import { createRouter, createWebHistory } from 'vue-router'

import LoginView from '../views/LoginView.vue'
import RegisterView from '../views/RegisterView.vue'
import WelcomeView from '../views/WelcomeView.vue'
import RecommendationsView from '../views/RecommendationsView.vue'
import PreferencesView from '../views/PreferencesView.vue'

function isAuthenticated() {
  return Boolean(localStorage.getItem('access_token'))
}

async function fetchPreferenceStatus() {
  const token = localStorage.getItem('access_token')
  if (!token) return null
  try {
    const res = await fetch('/api/profile/preferences/status', {
      headers: { Authorization: `Bearer ${token}` },
    })
    if (!res.ok) return null
    return await res.json()
  } catch {
    return null
  }
}

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'root',
      redirect: () => (isAuthenticated() ? '/welcome' : '/login'),
    },
    { path: '/login', name: 'login', component: LoginView, meta: { guestOnly: true } },
    { path: '/register', name: 'register', component: RegisterView, meta: { guestOnly: true } },
    {
      path: '/welcome',
      name: 'welcome',
      component: WelcomeView,
      meta: { requiresAuth: true },
    },
    {
      path: '/recommendations',
      name: 'recommendations',
      component: RecommendationsView,
      meta: { requiresAuth: true, requiresPreferences: true },
    },
    {
      path: '/preferences',
      name: 'preferences',
      component: PreferencesView,
      meta: { requiresAuth: true },
    },
  ],
})

router.beforeEach(async (to) => {
  if (to.meta.requiresAuth && !isAuthenticated()) {
    return { name: 'login', query: { next: to.fullPath } }
  }
  if (to.meta.guestOnly && isAuthenticated()) {
    return { name: 'welcome' }
  }
  if (to.meta.requiresPreferences && isAuthenticated()) {
    const status = await fetchPreferenceStatus()
    if (!status?.has_preferences) {
      return { name: 'preferences' }
    }
  }
  return true
})

export default router
