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
            <select id="roles" v-model="selectedRole" class="jp-input">
              <option value="" disabled>Select a standardized role</option>
              <option v-for="role in roleOptions" :key="role" :value="role">
                {{ role }}
              </option>
            </select>
            <button type="button" class="jp-btn-secondary" @click="addRole">Add</button>
          </div>
          <div class="role-chip-wrap">
            <span v-for="role in selectedRoles" :key="role" class="role-chip">
              {{ role }}
              <button type="button" aria-label="Remove role" @click="removeRole(role)">×</button>
            </span>
          </div>
          <p v-if="!selectedRoles.length" class="help-text">No roles selected yet.</p>
          <datalist id="role-options-list">
            <option v-for="role in roleOptions" :key="role" :value="role">
              {{ role }}
            </option>
          </datalist>
        </div>

        <div class="field">
          <label class="jp-label" for="companies">Target companies (optional)</label>
          <div class="role-input-row">
            <input
              id="companies"
              v-model="selectedCompany"
              class="jp-input"
              type="text"
              placeholder="E.g. Acme Corp"
              @keydown.enter.prevent="addCompany"
            />
            <button type="button" class="jp-btn-secondary" @click="addCompany">Add</button>
          </div>
          <div class="role-chip-wrap">
            <span v-for="company in selectedCompanies" :key="company" class="role-chip">
              {{ company }}
              <button type="button" aria-label="Remove company" @click="removeCompany(company)">×</button>
            </span>
          </div>
          <p v-if="!selectedCompanies.length" class="help-text">No companies added.</p>
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
const roleOptions = ref([])
const selectedRole = ref('')
const selectedRoles = ref([])
const selectedCompany = ref('')
const selectedCompanies = ref([])
const resumeFile = ref(null)
const resumeInput = ref(null)
const errorMessage = ref('')
const message = ref('')
const saving = ref(false)

function authHeaders() {
  const token = localStorage.getItem('access_token')
  return token ? { Authorization: `Bearer ${token}` } : {}
}

async function loadRoleOptions() {
  const res = await fetch('/api/profile/preferences/role-options', { headers: authHeaders() })
  if (!res.ok) return
  const body = await res.json()
  roleOptions.value = Array.isArray(body.roles)
    ? body.roles.filter((r) => typeof r === 'string' && r.trim())
    : []
}

function addRole() {
  const role = selectedRole.value
  if (!role) return
  if (!selectedRoles.value.includes(role)) {
    selectedRoles.value.push(role)
  }
  selectedRole.value = ''
}

function removeRole(role) {
  selectedRoles.value = selectedRoles.value.filter((r) => r !== role)
}

function addCompany() {
  const company = selectedCompany.value.trim()
  if (!company) return
  if (!selectedCompanies.value.includes(company)) {
    selectedCompanies.value.push(company)
  }
  selectedCompany.value = ''
}

function removeCompany(company) {
  selectedCompanies.value = selectedCompanies.value.filter((c) => c !== company)
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
  selectedRoles.value = Array.isArray(body.roles)
    ? body.roles.filter((r) => typeof r === 'string' && r.trim())
    : []
  selectedCompanies.value = Array.isArray(body.companies)
    ? body.companies.filter((c) => typeof c === 'string' && c.trim())
    : []
  for (const role of selectedRoles.value) {
    if (!roleOptions.value.includes(role)) {
      roleOptions.value.push(role)
    }
  }
}

async function savePreferences() {
  errorMessage.value = ''
  message.value = ''
  if (selectedRoles.value.length < 1) {
    errorMessage.value = 'Add at least one job role.'
    return
  }
  saving.value = true
  try {
    const formData = new FormData()
    for (const role of selectedRoles.value) {
      formData.append('roles', role)
    }
    for (const company of selectedCompanies.value) {
      formData.append('companies', company)
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
  loadRoleOptions()
    .then(() => loadExistingStatus())
    .catch(() => {})
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
