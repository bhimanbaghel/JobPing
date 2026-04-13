<template>
  <div class="welcome-page">
    <div class="mesh" aria-hidden="true" />
    <div class="grid-overlay" aria-hidden="true" />
    <div class="orb orb-a" aria-hidden="true" />
    <div class="orb orb-b" aria-hidden="true" />
    <div class="orb orb-c" aria-hidden="true" />

    <header class="nav">
      <span class="nav-logo">JobPing</span>
      <button type="button" class="nav-out" @click="logout">Sign out</button>
    </header>

    <main class="landing">
      <div class="landing-row">
        <section class="hero">
          <p class="hero-kicker">
            <span class="kicker-dot" aria-hidden="true" />
            {{ loading && !userEmail ? 'Loading your session' : 'Signed in' }}
          </p>

          <h1 class="hero-title">
            <span class="hero-welcome">Welcome</span>
            <span v-if="displayName" class="hero-name-wrap">
              <span class="hero-name">{{ displayName }}</span>
            </span>
          </h1>

          <p v-if="userEmail" class="hero-email">{{ userEmail }}</p>

          <div class="hero-glow-line" aria-hidden="true" />
        </section>

        <aside class="soon" aria-labelledby="soon-heading">
          <div class="soon-head">
            <h2 id="soon-heading" class="soon-heading">Coming soon</h2>
            <span class="soon-badge">Roadmap</span>
          </div>
          <p class="soon-lead">
            Preferences and matches are on the way—nothing to configure yet.
          </p>
          <ul class="soon-pills">
            <li><span class="pill-glow" aria-hidden="true" />Job roles you care about</li>
            <li><span class="pill-glow" aria-hidden="true" />Companies you want</li>
            <li><span class="pill-glow" aria-hidden="true" />Recommendations tuned to you</li>
          </ul>
        </aside>
      </div>
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
  overflow-x: hidden;
  background: #f8fafc;
}

/* —— Atmosphere —— */
.mesh {
  position: fixed;
  inset: 0;
  z-index: 0;
  background: conic-gradient(
      from 200deg at 70% 8%,
      rgba(99, 102, 241, 0.22),
      transparent 40%,
      rgba(56, 189, 248, 0.18) 55%,
      transparent 75%,
      rgba(236, 72, 153, 0.12) 100%
    ),
    radial-gradient(ellipse 100% 80% at 50% -30%, rgba(59, 130, 246, 0.2), transparent 55%),
    radial-gradient(ellipse 70% 50% at 100% 60%, rgba(34, 211, 238, 0.15), transparent 50%),
    linear-gradient(180deg, #f0f9ff 0%, #f8fafc 45%, #eef2ff 100%);
  pointer-events: none;
}

.grid-overlay {
  position: fixed;
  inset: 0;
  z-index: 0;
  background-image: linear-gradient(rgba(148, 163, 184, 0.07) 1px, transparent 1px),
    linear-gradient(90deg, rgba(148, 163, 184, 0.07) 1px, transparent 1px);
  background-size: 48px 48px;
  mask-image: radial-gradient(ellipse 85% 70% at 50% 35%, black 20%, transparent 75%);
  pointer-events: none;
}

.orb {
  position: fixed;
  border-radius: 50%;
  filter: blur(80px);
  opacity: 0.55;
  pointer-events: none;
  z-index: 0;
  animation: orb-float 14s ease-in-out infinite;
}

.orb-a {
  width: min(42vw, 380px);
  height: min(42vw, 380px);
  top: -5%;
  left: -8%;
  background: #38bdf8;
  animation-delay: 0s;
}

.orb-b {
  width: min(48vw, 420px);
  height: min(48vw, 420px);
  top: 15%;
  right: -12%;
  background: #818cf8;
  animation-delay: -4s;
}

.orb-c {
  width: min(36vw, 320px);
  height: min(36vw, 320px);
  bottom: 5%;
  left: 25%;
  background: #22d3ee;
  animation-delay: -7s;
}

@keyframes orb-float {
  0%,
  100% {
    transform: translate(0, 0) scale(1);
  }
  33% {
    transform: translate(2%, 3%) scale(1.05);
  }
  66% {
    transform: translate(-2%, 1%) scale(0.98);
  }
}

/* —— Nav —— */
.nav {
  position: relative;
  z-index: 2;
  max-width: 1200px;
  margin: 0 auto;
  padding: 1.25rem clamp(1.25rem, 4vw, 2rem) 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.nav-logo {
  font-size: 0.95rem;
  font-weight: 800;
  letter-spacing: -0.03em;
  background: linear-gradient(120deg, #0f172a 0%, #2563eb 45%, #0891b2 100%);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
}

.nav-out {
  font-family: inherit;
  font-size: 0.8rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: #475569;
  background: rgba(255, 255, 255, 0.65);
  border: 1px solid rgba(148, 163, 184, 0.35);
  border-radius: 999px;
  padding: 0.5rem 1rem;
  cursor: pointer;
  backdrop-filter: blur(12px);
  transition: color 0.2s, border-color 0.2s, box-shadow 0.2s;
}

.nav-out:hover {
  color: #0f172a;
  border-color: rgba(37, 99, 235, 0.35);
  box-shadow: 0 0 0 4px rgba(37, 99, 235, 0.08);
}

/* —— Landing / hero —— */
.landing {
  position: relative;
  z-index: 1;
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 clamp(1.25rem, 4vw, 2rem) clamp(2rem, 6vw, 4rem);
}

.landing-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(240px, 300px);
  gap: clamp(1.5rem, 4vw, 3rem);
  align-items: start;
  min-height: calc(100vh - 5.5rem);
}

@media (max-width: 900px) {
  .landing-row {
    grid-template-columns: 1fr;
    min-height: unset;
  }
}

.hero {
  min-height: min(72vh, 600px);
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: flex-start;
  padding-top: clamp(1rem, 4vh, 2.5rem);
  animation: hero-in 0.9s ease-out both;
}

@media (max-width: 900px) {
  .hero {
    min-height: min(62vh, 520px);
  }
}

@keyframes hero-in {
  from {
    opacity: 0;
    transform: translateY(18px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.hero-kicker {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  margin: 0 0 1.25rem;
  font-size: 0.75rem;
  font-weight: 700;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: #64748b;
}

.kicker-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: linear-gradient(135deg, #22c55e, #14b8a6);
  box-shadow: 0 0 12px rgba(34, 197, 94, 0.65);
}

.hero-title {
  margin: 0;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.02em;
  line-height: 0.95;
}

.hero-welcome {
  font-size: clamp(3.25rem, 14vw, 7.5rem);
  font-weight: 800;
  letter-spacing: -0.045em;
  color: #0f172a;
  text-shadow: 0 1px 0 rgba(255, 255, 255, 0.8);
}

.hero-name-wrap {
  display: block;
  margin-top: -0.02em;
}

.hero-name {
  font-size: clamp(2rem, 9vw, 5rem);
  font-weight: 800;
  letter-spacing: -0.04em;
  background: linear-gradient(105deg, #2563eb 0%, #7c3aed 38%, #db2777 72%, #f97316 100%);
  background-size: 160% auto;
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
  animation: sheen 8s ease-in-out infinite alternate;
}

@keyframes sheen {
  0% {
    background-position: 0% 50%;
  }
  100% {
    background-position: 100% 50%;
  }
}

.hero-email {
  margin: 1.5rem 0 0;
  max-width: 100%;
  font-size: clamp(0.95rem, 2.2vw, 1.15rem);
  font-weight: 600;
  color: #475569;
  letter-spacing: -0.01em;
  word-break: break-word;
  padding: 0.65rem 1rem;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.55);
  border: 1px solid rgba(255, 255, 255, 0.9);
  box-shadow: 0 4px 24px -8px rgba(15, 23, 42, 0.12), inset 0 1px 0 rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(14px);
}

.hero-glow-line {
  width: min(100%, 520px);
  height: 3px;
  margin-top: 2.5rem;
  border-radius: 999px;
  background: linear-gradient(
    90deg,
    transparent,
    rgba(37, 99, 235, 0.5),
    rgba(6, 182, 212, 0.7),
    rgba(99, 102, 241, 0.5),
    transparent
  );
  box-shadow: 0 0 24px rgba(59, 130, 246, 0.35);
}

/* —— Coming soon (right rail) —— */
.soon {
  margin: 0;
  width: 100%;
  padding: clamp(1rem, 3vh, 1.75rem) 0 clamp(1rem, 3vh, 1.75rem) clamp(1.25rem, 3vw, 2rem);
  border-left: 1px solid rgba(148, 163, 184, 0.28);
  animation: hero-in 0.9s ease-out 0.12s both;
  position: sticky;
  top: 1.25rem;
}

@media (max-width: 900px) {
  .soon {
    padding: clamp(1.5rem, 4vw, 2rem) 0 0;
    border-left: none;
    border-top: 1px solid rgba(148, 163, 184, 0.28);
    position: static;
  }
}

.soon-head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 0.65rem;
}

.soon-heading {
  margin: 0;
  font-size: clamp(1.1rem, 2.5vw, 1.35rem);
  font-weight: 800;
  letter-spacing: -0.02em;
  color: #0f172a;
}

.soon-badge {
  font-size: 0.65rem;
  font-weight: 800;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: #6366f1;
  padding: 0.35rem 0.65rem;
  border-radius: 999px;
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.12), rgba(56, 189, 248, 0.12));
  border: 1px solid rgba(99, 102, 241, 0.25);
}

.soon-lead {
  margin: 0 0 1.1rem;
  max-width: none;
  font-size: 0.85rem;
  line-height: 1.55;
  color: #64748b;
}

.soon-pills {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}

.soon-pills li {
  position: relative;
  display: flex;
  align-items: center;
  gap: 0.65rem;
  font-size: 0.82rem;
  font-weight: 700;
  color: #334155;
  padding: 0.7rem 0.95rem 0.7rem 0.75rem;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.72);
  border: 1px solid rgba(255, 255, 255, 0.95);
  box-shadow: 0 8px 32px -12px rgba(15, 23, 42, 0.15), inset 0 1px 0 rgba(255, 255, 255, 0.9);
  backdrop-filter: blur(12px);
  overflow: hidden;
}

.pill-glow {
  flex-shrink: 0;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: linear-gradient(135deg, #38bdf8, #a78bfa);
  box-shadow: 0 0 10px rgba(56, 189, 248, 0.8);
}
</style>
