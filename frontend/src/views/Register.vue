<template>
  <div class="auth-page">
    <div class="auth-card">
      <div class="auth-head">
        <p class="auth-kicker">RouteAI</p>
        <h1>创建账号</h1>
        <p>注册后即可保存聊天历史、行程记录，并在不同页面继续你的旅行规划。</p>
      </div>

      <el-form @submit.prevent="handleRegister">
        <el-form-item>
          <el-input v-model="form.username" placeholder="用户名" size="large" />
        </el-form-item>
        <el-form-item>
          <el-input v-model="form.email" placeholder="邮箱" size="large" />
        </el-form-item>
        <el-form-item>
          <el-input v-model="form.password" type="password" show-password placeholder="密码（6-72字节）" size="large" @keyup.enter="handleRegister" />
        </el-form-item>
        <el-button type="primary" class="full-btn" size="large" :loading="authStore.loading" @click="handleRegister">
          注册
        </el-button>
      </el-form>

      <div class="auth-footer">
        <span>已有账号？</span>
        <router-link to="/login">去登录</router-link>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const authStore = useAuthStore()

const form = reactive({
  username: '',
  email: '',
  password: ''
})

function getPasswordBytes(text: string) {
  return new TextEncoder().encode(text).length
}

async function handleRegister() {
  if (!form.username.trim() || !form.email.trim() || !form.password.trim()) {
    ElMessage.warning('请完整填写注册信息')
    return
  }

  if (getPasswordBytes(form.password) > 72) {
    ElMessage.warning('密码长度不能超过72字节，请缩短后重试')
    return
  }

  try {
    await authStore.register({ ...form })
    ElMessage.success('注册成功，请登录')
    router.push('/login')
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || error.message || '注册失败')
  }
}
</script>

<style scoped>
.full-btn {
  width: 100%;
}
</style>
