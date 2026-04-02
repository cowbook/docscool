<template>
  <div class="logout-view">正在退出...</div>
</template>

<script setup>
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()

onMounted(() => {
  localStorage.removeItem('token')
  localStorage.removeItem('username')
  router.replace('/login')
})
</script>

<style scoped>
.logout-view {
  color: #6b7280;
}
</style>
