<script setup lang="ts">
import type {BreadcrumbItem} from '@nuxt/ui'
import type {DirectoryEntry} from '~/types/entry'

const props = defineProps<{
  dirpath: string
}>()

const breadcrumbs = computed<BreadcrumbItem[]>(() => {
  const root: BreadcrumbItem = {
    icon: 'mdi-folder',
    class: 'text-sm',
    to: '/workspace',
    ui: { linkLeadingIcon: 'size-4' },
  }

  const segments = props.dirpath.split('/').map(segment => segment.trim()).filter(Boolean)

  if (!segments) {
    return [root]
  }

  const directories: BreadcrumbItem[] = segments.map((segment, index) => ({
    label: segment,
    to: `/workspace/${segments.slice(0, index + 1).map(encodeURIComponent).join('/')}`,
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

const { data: entries, error } = await useFetch<DirectoryEntry[]>('/api/filesystem/listdir', {
  query: { dirpath: props.dirpath },
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
  return items.filter(entry => entry.label.toLowerCase().includes(query))
})
</script>

<template>
  <div class="flex h-full flex-col">
    <div class="flex justify-start items-center h-12 px-3 border-default border-b">
      <UBreadcrumb
        :items="breadcrumbs"
        color="neutral"
        :ui="{ separatorIcon: 'mx-[-0.5em]' }"
        separator-icon="heroicons-slash"
      />
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
        <DirectoryEntry :entry="entry" :selected="false" :viewing="false" />
      </template>
    </div>
  </div>
</template>
