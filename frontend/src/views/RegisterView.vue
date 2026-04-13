<template>
  <div class="auth-shell">
    <div class="auth-bg" aria-hidden="true" />

    <div class="auth-card jp-glass">
      <div class="auth-header">
        <div class="logo-dot" aria-hidden="true" />
        <div>
          <p class="product">JobPing</p>
          <h1 class="headline">Create account</h1>
          <p class="sub">Join JobPing — use a strong password (15+ characters).</p>
        </div>
      </div>

      <form class="auth-form" @submit.prevent="handleRegister">
        <div class="field">
          <label class="jp-label" for="reg-email">Email</label>
          <input
            id="reg-email"
            v-model="email"
            class="jp-input"
            type="email"
            autocomplete="email"
            required
            placeholder="you@company.com"
          />
        </div>

        <div class="field">
          <label class="jp-label" for="reg-password">Password</label>
          <input
            id="reg-password"
            v-model="password"
            class="jp-input"
            type="password"
            autocomplete="new-password"
            required
            placeholder="At least 15 characters"
          />
        </div>

        <div v-if="errorMessage" class="jp-error" role="alert">
          {{ errorMessage }}
        </div>

        <button class="jp-btn" type="submit">Sign up</button>
      </form>

      <p class="footer-line">
        Already have an account?
        <router-link to="/login">Sign in</router-link>
      </p>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'

const email = ref('')
const password = ref('')
const errorMessage = ref('')
const router = useRouter()

const handleRegister = async () => {
  errorMessage.value = ''

  if (!email.value || !password.value) {
    errorMessage.value = 'Please fill in all fields.'
    return
  }

  if (password.value.length < 15) {
    errorMessage.value = 'Password must be at least 15 characters.'
    return
  }

  try {
    const response = await fetch('/api/auth/register', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        email: email.value,
        password: password.value,
      }),
    })

    const data = await response.json()

    if (!response.ok) {
      throw new Error(data.error || 'Registration failed.')
    }

    localStorage.setItem('access_token', data.access_token)
    if (data.refresh_token) {
      localStorage.setItem('refresh_token', data.refresh_token)
    }
    if (data.user?.email) {
      localStorage.setItem('user_email', data.user.email)
    }
    router.push('/welcome')
  } catch (error) {
    errorMessage.value = error.message
  }
}
</script>

<style scoped>
.auth-shell {
  position: relative;
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: clamp(1.25rem, 4vw, 2.5rem);
}

.auth-bg {
  position: absolute;
  inset: 0;
  pointer-events: none;
  background: radial-gradient(520px 420px at 88% 22%, rgba(56, 189, 248, 0.26), transparent 72%),
    radial-gradient(460px 360px at 10% 14%, rgba(99, 102, 241, 0.2), transparent 68%);
}

.auth-card {
  position: relative;
  width: min(440px, 100%);
  padding: clamp(1.5rem, 4vw, 2.25rem);
  text-align: left;
}

.auth-header {
  display: flex;
  gap: 1rem;
  margin-bottom: 1.5rem;
}

.logo-dot {
  flex-shrink: 0;
  width: 48px;
  height: 48px;
  border-radius: 16px;
  background: linear-gradient(145deg, #6366f1, #38bdf8 55%, #2563eb);
  box-shadow: 0 14px 34px -12px rgba(79, 70, 229, 0.5), inset 0 1px 0 rgba(255, 255, 255, 0.35);
}

.product {
  margin: 0 0 0.2rem;
  font-size: 0.8rem;
  font-weight: 800;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--jp-accent2);
}

.headline {
  margin: 0 0 0.35rem;
  font-size: 1.65rem;
  font-weight: 800;
  letter-spacing: -0.03em;
  color: var(--jp-text);
}

.sub {
  margin: 0;
  font-size: 0.95rem;
  line-height: 1.55;
  color: var(--jp-text-soft);
}

.auth-form {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.field {
  display: flex;
  flex-direction: column;
}

.footer-line {
  margin: 1.35rem 0 0;
  text-align: center;
  font-size: 0.95rem;
  color: var(--jp-text-muted);
}

.footer-line a {
  margin-left: 0.25rem;
}
</style>
