<template>
  <router-view />
  <AIChatWidget v-if="isLoggedIn" />
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import AIChatWidget from './components/AIChatWidget.vue'

const route = useRoute()
const isLoggedIn = computed(() => {
  return !!localStorage.getItem('token') && route.path !== '/login' && route.path !== '/init'
})
</script>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

#app {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
  overflow: hidden !important;
}
</style>
