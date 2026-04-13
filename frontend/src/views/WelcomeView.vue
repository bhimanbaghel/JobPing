<template>
  <div class="welcome-page">
    <div class="welcome-bg" aria-hidden="true" />

    <header class="welcome-top jp-glass">
      <div class="brand">
        <span class="brand-mark" aria-hidden="true" />
        <div>
          <p class="brand-name">JobPing</p>
          <p class="brand-tag">Smart job signals</p>
        </div>
      </div>
      <button type="button" class="jp-btn jp-btn-ghost" @click="logout">Sign out</button>
    </header>

    <main class="welcome-main">
      <section class="hero jp-glass jp-glass-strong">
        <p class="eyebrow">You are in</p>
        <h1 class="title">Welcome back</h1>
        <p class="lead">
          Your JobPing workspace is ready. Track opportunities, stay ahead of the market, and
          keep your pipeline warm—all from one bright, focused hub.
        </p>
        <div class="hero-actions">
          <a class="jp-btn hero-cta" href="#tiles">Explore overview</a>
          <span class="hint">More modules ship soon.</span>
        </div>
      </section>

      <section id="tiles" class="tiles" aria-label="Quick overview">
        <article class="tile jp-glass">
          <h2>Pipeline</h2>
          <p class="tile-stat">—</p>
          <p class="tile-desc">Saved roles and follow-ups will appear here.</p>
        </article>
        <article class="tile jp-glass">
          <h2>Alerts</h2>
          <p class="tile-stat">Live</p>
          <p class="tile-desc">Ping notifications when new matches land.</p>
        </article>
        <article class="tile jp-glass">
          <h2>Profile</h2>
          <p class="tile-stat">{{ emailHint }}</p>
          <p class="tile-desc">Signed in and session secured with JWT.</p>
        </article>
      </section>
    </main>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const emailHint = ref('Connected')

function parseJwtEmail(token) {
  try {
    const payload = token.split('.')[1]
    const json = JSON.parse(atob(payload.replace(/-/g, '+').replace(/_/g, '/')))
    return json.sub || json.email || null
  } catch {
    return null
  }
}

onMounted(() => {
  const token = localStorage.getItem('access_token')
  const sub = token ? parseJwtEmail(token) : null
  if (sub) {
    emailHint.value = sub.length > 28 ? `${sub.slice(0, 26)}…` : sub
  }
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
  max-width: 1100px;
  margin: 0 auto 1.5rem;
  padding: 1rem 1.25rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
}

.brand {
  display: flex;
  align-items: center;
  gap: 0.85rem;
}

.brand-mark {
  width: 44px;
  height: 44px;
  border-radius: 14px;
  background: linear-gradient(145deg, #38bdf8, #6366f1 55%, #2563eb);
  box-shadow: 0 12px 28px -10px rgba(37, 99, 235, 0.55), inset 0 1px 0 rgba(255, 255, 255, 0.35);
}

.brand-name {
  margin: 0;
  font-size: 1.15rem;
  font-weight: 800;
  letter-spacing: -0.02em;
  color: var(--jp-text);
}

.brand-tag {
  margin: 0.1rem 0 0;
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--jp-text-soft);
}

.welcome-main {
  position: relative;
  z-index: 1;
  max-width: 1100px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.hero {
  padding: clamp(1.5rem, 4vw, 2.75rem);
  text-align: left;
}

.eyebrow {
  margin: 0 0 0.35rem;
  font-size: 0.8rem;
  font-weight: 800;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--jp-accent2);
}

.title {
  margin: 0 0 0.75rem;
  font-size: clamp(2rem, 4vw, 2.75rem);
  font-weight: 800;
  letter-spacing: -0.03em;
  line-height: 1.1;
  color: var(--jp-text);
}

.lead {
  margin: 0 0 1.5rem;
  max-width: 52ch;
  font-size: 1.05rem;
  line-height: 1.65;
  color: var(--jp-text-muted);
}

.hero-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 1rem;
}

.hero-cta {
  width: auto;
  min-width: 200px;
  text-decoration: none;
  color: #fff;
}

.hero-cta:hover {
  text-decoration: none;
  color: #fff;
}

.hint {
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--jp-text-soft);
}

.tiles {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 1rem;
}

.tile {
  padding: 1.25rem 1.35rem;
  text-align: left;
}

.tile h2 {
  margin: 0 0 0.5rem;
  font-size: 0.95rem;
  font-weight: 800;
  color: var(--jp-text-muted);
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.tile-stat {
  margin: 0 0 0.35rem;
  font-size: 1.65rem;
  font-weight: 800;
  letter-spacing: -0.02em;
  color: var(--jp-text);
}

.tile-desc {
  margin: 0;
  font-size: 0.9rem;
  line-height: 1.5;
  color: var(--jp-text-soft);
}
</style>
