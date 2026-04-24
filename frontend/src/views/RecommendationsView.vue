<template>
  <div class="recs-page">
    <header class="recs-nav">
      <router-link to="/welcome" class="recs-nav-logo">JobPing</router-link>
      <div class="recs-nav-right">
        <router-link to="/welcome" class="recs-nav-link">Home</router-link>
        <button type="button" class="recs-nav-out" @click="logout">Sign out</button>
      </div>
    </header>

    <main class="recs-main">
      <section class="recs-head">
        <div>
          <p class="recs-kicker">Recommendations</p>
          <h1 class="recs-title">Jobs picked for you</h1>
          <p class="recs-sub">
            Sorted by how well each role matches your profile. Only matches at
            <strong>80% or higher</strong> are shown.
          </p>
        </div>
        <button
          type="button"
          class="recs-refresh"
          :disabled="store.loading"
          @click="refresh"
        >
          {{ store.loading ? 'Refreshing…' : 'Refresh' }}
        </button>
      </section>

      <div v-if="store.loading && !store.items.length" class="recs-state">
        <p>Computing your recommendations…</p>
      </div>

      <div
        v-else-if="store.error && store.code === 'missing_role_preferences'"
        class="recs-state recs-empty"
      >
        <h2>Add a job role to get started</h2>
        <p>
          You need at least one preferred job role before we can recommend
          anything (FR6.1). Head over to your profile and add one — your
          recommendations will populate automatically afterwards.
        </p>
      </div>

      <div v-else-if="store.error" class="recs-state recs-error" role="alert">
        <h2>We couldn't load your recommendations</h2>
        <p>{{ store.error }}</p>
        <button type="button" class="recs-refresh" @click="refresh">Try again</button>
      </div>

      <div
        v-else-if="!store.items.length"
        class="recs-state recs-empty"
      >
        <h2>No matches yet</h2>
        <p>
          We couldn't find any jobs scoring 80% or higher against your
          profile. Try broadening your role list, adding more companies, or
          uploading a resume — then refresh.
        </p>
      </div>

      <ul v-else class="recs-list">
        <li
          v-for="rec in store.sortedByScore"
          :key="rec.job_id"
          class="recs-card"
        >
          <div class="recs-card-top">
            <span class="recs-card-company">{{ rec.company }}</span>
            <span class="recs-card-score" :title="`Cosine similarity ${rec.similarity_score.toFixed(3)}`">
              {{ Math.round(rec.similarity_score * 100) }}% match
            </span>
          </div>
          <h3 class="recs-card-role">{{ rec.role }}</h3>
          <p class="recs-card-meta">
            <span v-if="locationLabel(rec)">{{ locationLabel(rec) }}</span>
            <span v-if="rec.salary_usd">·  ${{ formatSalary(rec.salary_usd) }}</span>
            <span v-if="rec.posted_at">·  Posted {{ formatDate(rec.posted_at) }}</span>
          </p>
          <p class="recs-card-snippet">{{ snippet(rec.description) }}</p>
          <div class="recs-card-actions">
            <button type="button" class="recs-btn-secondary" @click="openDetails(rec)">
              View details
            </button>
            <a
              v-if="rec.link"
              class="recs-btn-primary"
              :href="rec.link"
              target="_blank"
              rel="noopener noreferrer"
            >
              Open posting
            </a>
          </div>
        </li>
      </ul>
    </main>

    <!-- Details modal (FR8 + FR9) -->
    <div
      v-if="selected"
      class="recs-modal-backdrop"
      role="dialog"
      aria-modal="true"
      aria-labelledby="recs-modal-title"
      @click.self="closeDetails"
      @keydown.esc="closeDetails"
    >
      <div class="recs-modal" tabindex="-1" ref="modalEl">
        <button
          type="button"
          class="recs-modal-close"
          aria-label="Close"
          @click="closeDetails"
        >
          ×
        </button>
        <p class="recs-modal-company">{{ selected.company }}</p>
        <h2 id="recs-modal-title" class="recs-modal-role">{{ selected.role }}</h2>
        <p class="recs-modal-meta">
          <span v-if="locationLabel(selected)">{{ locationLabel(selected) }}</span>
          <span v-if="selected.salary_usd">·  ${{ formatSalary(selected.salary_usd) }}</span>
          <span v-if="selected.posted_at">·  Posted {{ formatDate(selected.posted_at) }}</span>
        </p>
        <p class="recs-modal-score">
          Match score: <strong>{{ Math.round(selected.similarity_score * 100) }}%</strong>
        </p>
        <hr class="recs-modal-rule" />
        <p class="recs-modal-description">{{ selected.description }}</p>
        <div class="recs-modal-actions">
          <button type="button" class="recs-btn-secondary" @click="closeDetails">
            Close
          </button>
          <a
            v-if="selected.link"
            class="recs-btn-primary"
            :href="selected.link"
            target="_blank"
            rel="noopener noreferrer"
          >
            Open posting
          </a>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useRecommendationsStore } from '../stores/recommendations'

const router = useRouter()
const store = useRecommendationsStore()

const selected = ref(null)
const modalEl = ref(null)

function locationLabel(rec) {
  const parts = [rec.location?.city, rec.location?.state, rec.location?.country].filter(
    Boolean,
  )
  return parts.join(', ')
}

function formatSalary(n) {
  return Number(n).toLocaleString('en-US')
}

function formatDate(iso) {
  try {
    return new Date(iso).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    })
  } catch {
    return iso
  }
}

function snippet(text, max = 220) {
  if (!text) return ''
  const normalized = text.replace(/\n{3,}/g, '\n\n').trim()
  if (normalized.length <= max) return normalized
  return `${normalized.slice(0, max).trimEnd()}…`
}

function openDetails(rec) {
  selected.value = rec
  nextTick(() => modalEl.value?.focus())
}

function closeDetails() {
  selected.value = null
}

function refresh() {
  store.fetch({ recompute: true })
}

function logout() {
  localStorage.removeItem('access_token')
  localStorage.removeItem('refresh_token')
  router.push('/login')
}

onMounted(() => {
  store.fetch()
})
</script>

<style scoped>
.recs-page {
  min-height: 100vh;
  padding-bottom: 4rem;
  background: transparent;
  color: var(--jp-text);
}

.recs-nav {
  max-width: 1200px;
  margin: 0 auto;
  padding: 1.25rem clamp(1.25rem, 4vw, 2rem) 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.recs-nav-logo {
  font-size: 0.95rem;
  font-weight: 800;
  letter-spacing: -0.03em;
  text-decoration: none;
  background: linear-gradient(120deg, #0f172a 0%, #2563eb 45%, #0891b2 100%);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
}

.recs-nav-right {
  display: flex;
  gap: 0.75rem;
  align-items: center;
}

.recs-nav-link {
  font-size: 0.85rem;
  font-weight: 700;
  color: var(--jp-text-muted);
  text-decoration: none;
}

.recs-nav-link:hover {
  color: var(--jp-primary);
}

.recs-nav-out {
  font-family: inherit;
  font-size: 0.8rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--jp-text-muted);
  background: rgba(255, 255, 255, 0.65);
  border: 1px solid var(--jp-border-soft);
  border-radius: 999px;
  padding: 0.5rem 1rem;
  cursor: pointer;
  backdrop-filter: blur(12px);
}

.recs-nav-out:hover {
  color: var(--jp-text);
  border-color: rgba(37, 99, 235, 0.4);
}

.recs-main {
  max-width: 1200px;
  margin: 0 auto;
  padding: clamp(1.5rem, 4vw, 2.5rem) clamp(1.25rem, 4vw, 2rem) 0;
}

.recs-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 1.5rem;
  margin-bottom: clamp(1.25rem, 3vw, 2rem);
  flex-wrap: wrap;
}

.recs-kicker {
  margin: 0 0 0.5rem;
  font-size: 0.75rem;
  font-weight: 700;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--jp-accent2);
}

.recs-title {
  margin: 0;
  font-size: clamp(1.85rem, 4vw, 2.6rem);
  font-weight: 800;
  letter-spacing: -0.03em;
  color: var(--jp-text);
}

.recs-sub {
  margin: 0.5rem 0 0;
  font-size: 1rem;
  color: var(--jp-text-soft);
  max-width: 540px;
}

.recs-refresh {
  font-family: inherit;
  font-size: 0.85rem;
  font-weight: 700;
  letter-spacing: 0.02em;
  color: #fff;
  background: linear-gradient(135deg, var(--jp-primary), var(--jp-accent2));
  border: none;
  border-radius: 12px;
  padding: 0.7rem 1.2rem;
  cursor: pointer;
  box-shadow: var(--jp-shadow);
}

.recs-refresh:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.recs-state {
  margin-top: 1.5rem;
  padding: clamp(1.5rem, 4vw, 2.25rem);
  border-radius: var(--jp-radius-lg);
  background: var(--jp-surface);
  border: 1px solid var(--jp-border);
  box-shadow: var(--jp-shadow);
  text-align: center;
}

.recs-state h2 {
  margin: 0 0 0.5rem;
  font-size: 1.25rem;
  font-weight: 800;
  color: var(--jp-text);
}

.recs-state p {
  margin: 0 auto 1rem;
  max-width: 480px;
  color: var(--jp-text-muted);
  line-height: 1.55;
}

.recs-error {
  border-color: rgba(220, 38, 38, 0.35);
}

.recs-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 1rem;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
}

.recs-card {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 0.65rem;
  padding: 1.25rem 1.25rem 1.4rem;
  border-radius: var(--jp-radius-lg);
  background: var(--jp-surface-strong);
  border: 1px solid var(--jp-border);
  box-shadow: var(--jp-shadow);
  transition: transform 0.15s ease, box-shadow 0.15s ease;
}

.recs-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 28px 56px -16px rgba(15, 23, 42, 0.16),
    0 16px 28px -10px rgba(15, 23, 42, 0.1);
}

.recs-card-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.5rem;
}

.recs-card-company {
  font-size: 0.7rem;
  font-weight: 800;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--jp-text-muted);
}

.recs-card-score {
  font-size: 0.7rem;
  font-weight: 800;
  letter-spacing: 0.06em;
  color: var(--jp-primary);
  background: rgba(37, 99, 235, 0.1);
  border: 1px solid rgba(37, 99, 235, 0.2);
  border-radius: 999px;
  padding: 0.3rem 0.65rem;
}

.recs-card-role {
  margin: 0;
  font-size: 1.15rem;
  font-weight: 800;
  letter-spacing: -0.02em;
  color: var(--jp-text);
}

.recs-card-meta,
.recs-modal-meta {
  margin: 0;
  font-size: 0.85rem;
  color: var(--jp-text-soft);
}

.recs-card-snippet {
  margin: 0;
  font-size: 0.92rem;
  line-height: 1.55;
  color: var(--jp-text-muted);
  white-space: pre-line;
}

.recs-card-actions,
.recs-modal-actions {
  margin-top: auto;
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.recs-btn-primary,
.recs-btn-secondary {
  font-family: inherit;
  font-size: 0.85rem;
  font-weight: 700;
  letter-spacing: 0.02em;
  border-radius: 12px;
  padding: 0.55rem 1rem;
  cursor: pointer;
  text-decoration: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.recs-btn-primary {
  color: #fff;
  background: linear-gradient(135deg, var(--jp-primary), var(--jp-accent));
  border: none;
}

.recs-btn-secondary {
  color: var(--jp-text);
  background: rgba(255, 255, 255, 0.7);
  border: 1px solid var(--jp-border-soft);
}

.recs-btn-secondary:hover {
  border-color: var(--jp-primary);
  color: var(--jp-primary);
}

/* —— Modal —— */
.recs-modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 50;
  padding: 1.25rem;
  backdrop-filter: blur(6px);
}

.recs-modal {
  position: relative;
  width: min(640px, 100%);
  max-height: 86vh;
  overflow-y: auto;
  padding: clamp(1.5rem, 4vw, 2.25rem);
  border-radius: var(--jp-radius-lg);
  background: #fff;
  box-shadow: 0 40px 80px -20px rgba(15, 23, 42, 0.4);
  outline: none;
}

.recs-modal-close {
  position: absolute;
  top: 0.75rem;
  right: 0.85rem;
  background: transparent;
  border: none;
  font-size: 1.4rem;
  color: var(--jp-text-muted);
  cursor: pointer;
  line-height: 1;
}

.recs-modal-company {
  margin: 0 0 0.25rem;
  font-size: 0.7rem;
  font-weight: 800;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--jp-accent2);
}

.recs-modal-role {
  margin: 0 0 0.5rem;
  font-size: 1.4rem;
  font-weight: 800;
  letter-spacing: -0.02em;
  color: var(--jp-text);
}

.recs-modal-score {
  margin: 0.75rem 0 0;
  font-size: 0.9rem;
  color: var(--jp-text-muted);
}

.recs-modal-rule {
  margin: 1.25rem 0;
  border: none;
  border-top: 1px solid var(--jp-border-soft);
}

.recs-modal-description {
  margin: 0 0 1.5rem;
  font-size: 0.95rem;
  line-height: 1.6;
  color: var(--jp-text-muted);
  white-space: pre-wrap;
}
</style>
