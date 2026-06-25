<script setup lang="ts">
const route = useRoute()

const dirpath = computed<string>(() => {
  const value = route.params.dirpath
  if (!value) {
    return ''
  }
  if (Array.isArray(value)) {
    return value.join('/')
  }
  return value
})
</script>

<template>
  <aside class="w-64 shrink-0 border-e border-default bg-muted">
    <DirectoryPanel :dirpath="dirpath" />
  </aside>
  <main class="min-w-0 flex-1">
    <div>Images</div>
  </main>
</template>
