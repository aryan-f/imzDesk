<script setup lang="ts">
const { anyOpened } = useWorkspace()
</script>

<template>
  <div class="flex min-h-0 flex-1">
    <div class="w-64 shrink-0 border-e border-default bg-muted">
      <FilesystemWidget />
    </div>
    <div class="min-w-0 flex-1">
      <template v-if="anyOpened">
        <ViewportWidget />
      </template>
    </div>
  </div>
</template>
