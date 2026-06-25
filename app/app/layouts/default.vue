<script setup lang="ts">
const logsOpen = ref(false)
</script>

<template>
  <div class="flex h-screen flex-col bg-default text-default relative">
    <MainNavbar />
    <div class="flex min-h-0 flex-1">
      <slot />
    </div>
    <LogsPanel v-model:logs-open="logsOpen" />
    <StatusBar v-model:logs-open="logsOpen" />
  </div>
</template>
