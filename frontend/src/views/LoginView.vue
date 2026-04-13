<template>
  <div class="auth-container">
    <h2>Login</h2>
    <form @submit.prevent="handleLogin">

      <div class="form-group">
        <label>Email:</label>
        <input type="email" v-model="email" required placeholder="Please enter your email" />
      </div>

      <div class="form-group">
        <label>Password:</label>
        <input type="password" v-model="password" required placeholder="To be confirmed" />
      </div>

      <div v-if="errorMessage" class="error-message">
        {{ errorMessage }}
      </div>

      <button type="submit">Sign In</button>


      <div class="register-link">
              <p> Need an account?
                <router-link to="/register">Register Now</router-link>
              </p>
            </div>



    </form>
  </div>
</template>

<script setup>
import { ref } from 'vue';
import { useRouter } from 'vue-router';

const email = ref('');
const password = ref('');
const errorMessage = ref('');
const router = useRouter();

const handleLogin = async () => {
  errorMessage.value = '';

  if (!email.value || !password.value) {
    errorMessage.value = 'Please fill in all fields.';
    return;
  }

  try {
    const response = await fetch('/api/auth/login', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        email: email.value,
        password: password.value
      })
    });

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.error || 'Login failed.');
    }

    // Success - Store tokens
    localStorage.setItem('access_token', data.access_token);
    if (data.refresh_token) {
      localStorage.setItem('refresh_token', data.refresh_token);
    }

    // Redirect to home or dashboard
    router.push('/');
  } catch (error) {
    errorMessage.value = error.message;
  }
};
</script>

<style scoped>
.auth-container {
  max-width: 400px;
  margin: 50px auto;

  padding: 30px;

  border: 2px solid #ebebeb;
  border-radius: 8px;

  font-family: sans-serif;
}


.form-group {
  margin-bottom: 20px;
  text-align: left;
}


label {
  display: block;
  margin-bottom: 5px;
  font-weight: bold;
}


input {
  width: 100%;
  padding: 10px;
  box-sizing: border-box;
  border: 2px solid #cccccc;
  border-radius: 8px;
}


button {
  width: 100%;
  padding: 12px;
  background-color: #409eff;
  color: #ffffff;
  border: 2px solid blue;
  border-radius: 8px;
  cursor: pointer;
  font-size: 16px;
}





.error-message {
  color: red;
  margin-bottom: 15px;
  font-size: 14px;
  text-align: left;
}

</style>

