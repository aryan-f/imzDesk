<script setup lang="ts">
import type {BreadcrumbItem} from '@nuxt/ui'
import {type FilesystemEntry} from '~/types/filesystem'

const { state, openDirectory } = useWorkspace()

const dirpath = computed(() => state.value.dirpath)
const displayedDirpath = ref(dirpath.value)

const breadcrumbs = computed<BreadcrumbItem[]>(() => {
  const root: BreadcrumbItem = {
    icon: 'mdi-folder',
    class: 'cursor-pointer text-sm',
    onClick: () => openDirectory(''),
    ui: { linkLeadingIcon: 'size-4' },
  }

  const segments = displayedDirpath.value.split('/').map(segment => segment.trim()).filter(Boolean)

  if (segments.length === 0) return [root]

  const directories: BreadcrumbItem[] = segments.map((segment, index) => ({
    label: segment,
    class: 'cursor-pointer',
    onClick: () => openDirectory(segments.slice(0, index + 1).join('/')),
  }))

  // Show everything if path is shallow
  if (directories.length <= 2) {
    return [root, ...directories]
  }

  // For deeper paths, compact the breadcrumbs
  return [
    root,
    { label: '...', class: 'text-sm' },
    ...directories.slice(-2),
  ]
})

const { data: entries, error, status, refresh } = await useFetch<FilesystemEntry[]>('/api/filesystem/listdir', {
  query: { dirpath },
  watch: false,
})
const loading = computed(() => status.value === 'pending')

const activePath = ref<string | null>(null)

watch(dirpath, async () => {
  const nextDirpath = dirpath.value
  await refresh()
  if (!error.value && dirpath.value === nextDirpath) {
    displayedDirpath.value = nextDirpath
    activePath.value = null
  }
})

if (error.value) {
  const data = error.value.data as { detail?: string } | undefined
  throw createError({
    statusCode: error.value.statusCode,
    statusMessage: error.value.statusMessage,
    data: error.value.data,
    message: data?.detail,
    fatal: true,
  })
}

const search = ref('')

const filteredEntries = computed(() => {
  const query = search.value.trim().toLowerCase()
  const items = entries.value ?? []
  if (!query) return items
  return items.filter(entry => entry.name.toLowerCase().includes(query))
})
</script>

<template>
  <div class="flex h-full flex-col">
    <div class="flex justify-start items-center h-12 px-3 border-default border-b gap-2">
      <UBreadcrumb
        :items="breadcrumbs"
        color="neutral"
        :ui="{ separatorIcon: 'mx-[-0.5em]' }"
        separator-icon="heroicons-slash"
      />
      <UIcon v-if="loading" name="i-lucide-loader-circle" class="ms-auto size-4 animate-spin text-primary" />
    </div>
    <div class="flex flex-col justify-center h-12 px-3">
      <UInput
        v-model="search"
        icon="i-lucide-search"
        placeholder="Search..."
        size="md"
      />
    </div>
    <div class="min-h-0 flex-1 overflow-y-auto px-3 pb-3">
      <template v-for="entry in filteredEntries" :key="entry.path">
        <FilesystemEntry
          :entry="entry"
          :active="entry.path === activePath"
          @select="activePath = $event.path"
        />
      </template>
    </div>
  </div>
</template>
