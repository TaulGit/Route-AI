<template>
  <div class="auth-page">
    <div class="auth-card">
      <div class="auth-head">
        <p class="auth-kicker">RouteAI</p>
        <h1>登录账号</h1>
        <p>登录后可查看聊天历史、行程记录，并继续编辑你的旅行方案。</p>
      </div>

      <el-form @submit.prevent="handleLogin">
        <el-form-item>
          <el-input v-model="form.username_or_email" placeholder="用户名或邮箱" size="large" />
        </el-form-item>
        <el-form-item>
          <el-input v-model="form.password" type="password" show-password placeholder="密码" size="large" @keyup.enter="handleLogin" />
        </el-form-item>
        <el-button type="primary" class="full-btn" size="large" :loading="authStore.loading" @click="handleLogin">
          登录
        </el-button>
      </el-form>

      <div class="auth-footer">
        <span>还没有账号？</span>
        <router-link to="/register">去注册</router-link>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

const form = reactive({
  username_or_email: '',
  password: ''
})

async function handleLogin() {
  if (!form.username_or_email.trim() || !form.password.trim()) {
    ElMessage.warning('请输入用户名和密码')
    return
  }

  try {
    await authStore.login({ ...form })
    ElMessage.success('登录成功')
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/'
    router.push(redirect)
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || error.message || '登录失败')
  }
}
</script>

<style scoped>
.full-btn {
  width: 100%;
}
</style>
