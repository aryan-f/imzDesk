<script setup lang="ts">
const logsOpen = ref(false)
</script>

<template>
  <div class="flex h-screen flex-col bg-default text-default relative">
    <MainNavbar />
    <div class="flex min-h-0 flex-1">
      <aside class="w-64 shrink-0 border-e border-default bg-muted flex flex-col">
        <FileBrowser />
      </aside>
      <main class="min-w-0 flex-1">
        <slot />
      </main>
    </div>
    <LogsPanel v-model:logs-open="logsOpen" />
    <StatusBar v-model:logs-open="logsOpen" />
  </div>
</template>
