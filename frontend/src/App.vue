<template>
  <el-config-provider :locale="zhCn">
    <router-view />
  </el-config-provider>
</template>

<script setup lang="ts">
import { ElConfigProvider } from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
</script>

<style>
* {
  margin: 0;
  padding: 0;
}

body {
  font-family: var(--ra-font-text);
}

h1,
h2,
h3,
h4,
h5,
h6 {
  font-family: var(--ra-font-display);
  font-weight: 600;
}

.brand-text,
.section-label,
.auth-kicker,
.history-kicker {
  font-family: var(--ra-font-sans);
}

a {
  color: inherit;
}

button {
  transition: transform 0.24s ease, box-shadow 0.24s ease, background-color 0.24s ease, border-color 0.24s ease, color 0.24s ease;
}

button:hover {
  transform: translateY(-1px);
}

button:active {
  transform: translateY(0);
}

#app {
  min-height: 100vh;
}
</style>
