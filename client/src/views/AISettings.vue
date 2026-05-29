<template>
  <div>正在跳转到设置页面...</div>
</template>

<script setup>
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()

onMounted(() => {
  router.replace('/settings?tab=ai')
})
</script>
