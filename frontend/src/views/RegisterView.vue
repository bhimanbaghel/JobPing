<template>
  <div class="auth-container">
    <h2>Register</h2>
    <form @submit.prevent="handleRegister">

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

      <button type="submit">Sign Up</button>


            <div class="login-link">
                    <p> Already have an account?
                      <router-link to="/login">Login Now</router-link>
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

const handleRegister = async () => {
  errorMessage.value = '';

  if (!email.value || !password.value) {
    errorMessage.value = 'Please fill in all fields.';
    return;
  }

  if (password.value.length < 15) {
    errorMessage.value = 'Password must more than 14 characters';
    return;
  }

  try {
    const response = await fetch('/api/auth/register', {
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
      throw new Error(data.error || 'Registration failed.');
    }

    // Success - Store tokens and redirect
    localStorage.setItem('access_token', data.access_token);
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



