<script setup lang="ts">
const { state } = useWorkspace()
</script>

<template>
  <div class="flex h-full">
    State: {{ state }}
    <div class="flex-1 flex flex-col min-w-0">
      <!--Panels-->
    </div>
    <!--Sidebar-->
  </div>
</template>
