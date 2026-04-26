<script setup lang="ts">
import { getFileType } from '~/config/fileTypes'

const route = useRoute()

const path = computed(() => {
  const param = route.params.path
  const parts = Array.isArray(param) ? param : [param]
  const posixPath = parts.map(p => decodeURIComponent(p as string)).join('/')
  return posixPath || '/'
})

const viewer = computed(() => path.value ? getFileType(path.value)?.component : null)
</script>

<template>
  <aside class="w-80 shrink-0 overflow-y-auto border-r border-default">
    <FileBrowser :path="path" />
  </aside>
  <main class="min-w-0 min-h-0 flex-1 overflow-auto">
    <ClientOnly v-if="viewer">
      <component :is="viewer" :path="path"/>
    </ClientOnly>
  </main>
</template>
