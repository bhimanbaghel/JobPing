<template>
  <div class="prefs-page">
    <main class="prefs-card jp-glass">
      <p class="prefs-kicker">Profile setup</p>
      <h1 class="prefs-title">Set your job preferences</h1>
      <p class="prefs-sub">Add at least one role to generate recommendations.</p>

      <form class="prefs-form" @submit.prevent="savePreferences">
        <div class="field">
          <label class="jp-label" for="roles">Job roles (required)</label>
          <div class="role-input-row">
            <input
              id="roles"
              v-model="roleInput"
              class="jp-input"
              type="text"
              placeholder="e.g. Backend Engineer"
              @keydown.enter.prevent="addRole"
            />
            <button type="button" class="jp-btn-secondary" @click="addRole">Add</button>
          </div>
          <div class="role-chip-wrap">
            <span v-for="role in roles" :key="role" class="role-chip">
              {{ role }}
              <button type="button" aria-label="Remove role" @click="removeRole(role)">×</button>
            </span>
          </div>
        </div>

        <div class="field">
          <label class="jp-label" for="resume">Resume (optional PDF, less than 5MB)</label>
          <input
            id="resume"
            ref="resumeInput"
            class="jp-input"
            type="file"
            accept="application/pdf,.pdf"
            @change="onResumeSelected"
          />
          <p class="help-text">Resume is optional but recommended.</p>
        </div>

        <div v-if="message" class="jp-success">{{ message }}</div>
        <div v-if="errorMessage" class="jp-error" role="alert">{{ errorMessage }}</div>

        <button class="jp-btn" type="submit" :disabled="saving">
          {{ saving ? 'Saving...' : 'Save preferences' }}
        </button>
      </form>
    </main>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const roleInput = ref('')
const roles = ref([])
const resumeFile = ref(null)
const resumeInput = ref(null)
const errorMessage = ref('')
const message = ref('')
const saving = ref(false)

function authHeaders() {
  const token = localStorage.getItem('access_token')
  return token ? { Authorization: `Bearer ${token}` } : {}
}

function addRole() {
  const next = roleInput.value.trim()
  if (!next) return
  if (!roles.value.includes(next)) {
    roles.value.push(next)
  }
  roleInput.value = ''
}

function removeRole(role) {
  roles.value = roles.value.filter((r) => r !== role)
}

function onResumeSelected(event) {
  errorMessage.value = ''
  message.value = ''
  const file = event.target.files?.[0]
  if (!file) {
    resumeFile.value = null
    return
  }
  if (file.type !== 'application/pdf') {
    errorMessage.value = 'Resume must be a PDF file.'
    resumeFile.value = null
    if (resumeInput.value) resumeInput.value.value = ''
    return
  }
  if (file.size >= 5 * 1024 * 1024) {
    errorMessage.value = 'Resume must be smaller than 5MB.'
    resumeFile.value = null
    if (resumeInput.value) resumeInput.value.value = ''
    return
  }
  resumeFile.value = file
}

async function loadExistingStatus() {
  const res = await fetch('/api/profile/preferences/status', { headers: authHeaders() })
  if (res.status === 401) {
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    router.replace('/login')
    return
  }
  if (!res.ok) return
  const body = await res.json()
  roles.value = Array.isArray(body.roles)
    ? body.roles.filter((r) => typeof r === 'string' && r.trim())
    : []
}

async function savePreferences() {
  errorMessage.value = ''
  message.value = ''
  addRole()
  if (roles.value.length < 1) {
    errorMessage.value = 'Add at least one job role.'
    return
  }
  saving.value = true
  try {
    const formData = new FormData()
    for (const role of roles.value) {
      formData.append('roles', role)
    }
    if (resumeFile.value) {
      formData.append('resume', resumeFile.value)
    }

    const res = await fetch('/api/profile/preferences', {
      method: 'POST',
      headers: authHeaders(),
      body: formData,
    })
    const body = await res.json().catch(() => ({}))
    if (!res.ok) {
      throw new Error(body.error || 'Could not save preferences.')
    }
    message.value = 'Preferences saved.'
    router.push('/recommendations')
  } catch (err) {
    errorMessage.value = err.message || 'Could not save preferences.'
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  loadExistingStatus()
})
</script>

<style scoped>
.prefs-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1.5rem;
}

.prefs-card {
  width: min(640px, 100%);
  padding: 1.5rem;
}

.prefs-kicker {
  margin: 0;
  font-size: 0.75rem;
  font-weight: 700;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--jp-accent2);
}

.prefs-title {
  margin: 0.45rem 0 0.25rem;
  font-size: 1.8rem;
}

.prefs-sub {
  margin: 0 0 1.2rem;
  color: var(--jp-text-muted);
}

.prefs-form {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.role-input-row {
  display: flex;
  gap: 0.5rem;
}

.jp-btn-secondary {
  border: 1px solid var(--jp-border-soft);
  border-radius: 12px;
  padding: 0.55rem 0.9rem;
  font-weight: 600;
  background: rgba(255, 255, 255, 0.75);
  cursor: pointer;
}

.role-chip-wrap {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
}

.role-chip {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.3rem 0.65rem;
  border-radius: 999px;
  font-size: 0.82rem;
  background: rgba(37, 99, 235, 0.1);
  color: var(--jp-primary);
}

.role-chip button {
  border: none;
  background: transparent;
  cursor: pointer;
  color: inherit;
}

.help-text {
  margin: 0;
  font-size: 0.85rem;
  color: var(--jp-text-muted);
}
</style>
