<template>
  <div class="main-layout">
    <app-header />
    <div class="main-content">
      <slot />
    </div>
    <footer class="footer">
      <div class="footer-content">
        <a href="https://creativecommons.org/chooser/" target="_blank">ATP</a> © 2026 by 
        <a href="https://creativecommons.org/chooser/" target="_blank">@yandc</a> is licensed under 
        <a href="https://creativecommons.org/licenses/by/4.0/" target="_blank">Creative Commons Attribution 4.0 International</a>
        <img src="https://mirrors.creativecommons.org/presskit/icons/cc.svg" alt="CC" class="license-icon">
        <img src="https://mirrors.creativecommons.org/presskit/icons/by.svg" alt="BY" class="license-icon">
      </div>
    </footer>
  </div>
</template>

<script setup>
import AppHeader from './AppHeader.vue'
</script>

<style scoped>
.main-layout {
  height: 100vh;
  background-color: var(--el-bg-color-page);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.main-content {
  flex: 1;
  min-height: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.footer {
  background-color: var(--el-bg-color);
  border-top: 1px solid var(--el-border-color-light);
  padding: 6px 0;
  flex-shrink: 0;
}

.footer-content {
  text-align: center;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  line-height: 1.4;
}

.footer-content a {
  color: var(--el-color-primary);
  text-decoration: none;
  transition: color 0.3s;
}

.footer-content a:hover {
  color: var(--el-color-primary-light-3);
}

.license-icon {
  max-width: 1em;
  max-height: 1em;
  margin-left: 0.2em;
  vertical-align: middle;
}
</style>
