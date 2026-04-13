<template>
  <div class="welcome-page">
    <div class="welcome-bg" aria-hidden="true" />

    <header class="welcome-top jp-glass">
      <p class="brand-name">JobPing</p>
      <button type="button" class="jp-btn jp-btn-ghost" @click="logout">Sign out</button>
    </header>

    <main class="welcome-main">
      <section class="panel jp-glass jp-glass-strong">
        <h1 class="greeting">
          Welcome<span v-if="displayName">, {{ displayName }}</span>
        </h1>
        <p v-if="userEmail" class="signed-in">Signed in as {{ userEmail }}</p>
        <p v-else-if="loading" class="signed-in muted">Loading…</p>

        <div class="soon-block">
          <h2 class="soon-title">Coming soon</h2>
          <p class="soon-intro">
            JobPing will use your preferences to surface roles that fit you. These features are not
            available yet:
          </p>
          <ul class="soon-list">
            <li>Preferred job roles</li>
            <li>Preferred companies</li>
            <li>Personalized job recommendations</li>
          </ul>
        </div>
      </section>
    </main>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const userEmail = ref('')
const loading = ref(true)

const displayName = computed(() => {
  const e = userEmail.value
  if (!e) return ''
  const at = e.indexOf('@')
  if (at <= 0) return e
  return e.slice(0, at)
})

async function loadEmailFromUserRow() {
  loading.value = true
  const token = localStorage.getItem('access_token')
  if (!token) {
    loading.value = false
    return
  }
  try {
    const res = await fetch('/api/auth/me', {
      headers: { Authorization: `Bearer ${token}` },
    })
    if (res.status === 401) {
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
      router.replace({ name: 'login', query: { next: '/welcome' } })
      return
    }
    if (!res.ok) return
    const data = await res.json()
    if (data?.email) {
      userEmail.value = data.email
    }
  } catch {
    /* ignore */
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadEmailFromUserRow()
})

function logout() {
  localStorage.removeItem('access_token')
  localStorage.removeItem('refresh_token')
  router.push('/login')
}
</script>

<style scoped>
.welcome-page {
  position: relative;
  min-height: 100vh;
  padding: clamp(1.25rem, 4vw, 2.5rem);
  overflow-x: hidden;
}

.welcome-bg {
  position: fixed;
  inset: 0;
  pointer-events: none;
  background: radial-gradient(520px 420px at 18% 22%, rgba(56, 189, 248, 0.2), transparent 70%),
    radial-gradient(480px 380px at 82% 18%, rgba(99, 102, 241, 0.18), transparent 65%);
  z-index: 0;
}

.welcome-top {
  position: relative;
  z-index: 1;
  max-width: 560px;
  margin: 0 auto 1.25rem;
  padding: 0.85rem 1.1rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
}

.brand-name {
  margin: 0;
  font-size: 1rem;
  font-weight: 800;
  letter-spacing: -0.02em;
  color: var(--jp-text);
}

.welcome-main {
  position: relative;
  z-index: 1;
  max-width: 560px;
  margin: 0 auto;
}

.panel {
  padding: clamp(1.5rem, 4vw, 2rem);
  text-align: left;
}

.greeting {
  margin: 0 0 0.5rem;
  font-size: clamp(1.5rem, 4vw, 1.85rem);
  font-weight: 800;
  letter-spacing: -0.03em;
  line-height: 1.2;
  color: var(--jp-text);
}

.signed-in {
  margin: 0 0 1.5rem;
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--jp-text-muted);
  word-break: break-word;
}

.signed-in.muted {
  color: var(--jp-text-soft);
}

.soon-block {
  padding-top: 1.25rem;
  border-top: 1px solid var(--jp-border-soft);
}

.soon-title {
  margin: 0 0 0.5rem;
  font-size: 0.75rem;
  font-weight: 800;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--jp-accent2);
}

.soon-intro {
  margin: 0 0 0.85rem;
  font-size: 0.95rem;
  line-height: 1.55;
  color: var(--jp-text-muted);
}

.soon-list {
  margin: 0;
  padding-left: 1.15rem;
  font-size: 0.95rem;
  line-height: 1.65;
  color: var(--jp-text);
}

.soon-list li {
  margin-bottom: 0.35rem;
}

.soon-list li:last-child {
  margin-bottom: 0;
}
</style>
