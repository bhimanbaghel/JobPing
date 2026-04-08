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
    </form>
  </div>
</template>






<script setup>
import { ref } from 'vue';

const email = ref('');
const password = ref('');
const errorMessage = ref('');

const handleRegister = () => {
  errorMessage.value = '';

  if (!email.value || !password.value) {
    errorMessage.value = 'Please fill in all fields.';
    return;
  }

  if (password.value.length < 15) {
    errorMessage.value = 'Password must more than 14 characters';




    return;
  }

  console.log("Register payload:", { email: email.value, password: password.value });
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



