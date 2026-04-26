<script setup lang="ts">
import prettyBytes from 'pretty-bytes'
import { getFileType } from '~/config/fileTypes'

const router = useRouter()

type ListItem = {
  name: string
  is_dir: boolean
  size: number
}

type Stat = {
  name: string
  size: number
  is_dir: boolean
  is_file: boolean
  modified_at: number
  path: string
}

const props = withDefaults(defineProps<{
  path: string
  maxLen?: number
}>(), {
  maxLen: 10,
})

const { data: stat, error } = await useFetch<Stat>('/api/fs/stat', {
  query: computed(() => ({
    path: props.path,
  })),
  watch: [() => props.path],
})

watchEffect(() => {
  if (!error.value) return
  if (error.value.statusCode === 404) {
    throw createError({
      statusCode: 404,
      statusMessage: 'File not found',
      statusText: 'How did you end up here?',
    })
  }
})

const selected = ref<string | null>(null)

const dirpath = computed(() => {
  selected.value = null // Deselect file/directory on change to route
  const parts = props.path.split('/').filter(Boolean)
  if (!stat.value || stat.value.path !== props.path) {
    return parts  // May not have been updated yet
  }
  if (!stat.value.is_dir) {
    return parts.slice(0, -1)
  }
  return parts
})

const breadcrumbs = computed(() => {
  const root = { 'icon': 'material-symbols-folder', to: '/' }
  const parts = dirpath.value.map((part, index) => ({
    to: '/' + dirpath.value.slice(0, index + 1).join('/'),
    label: part.length > props.maxLen ? part.slice(0, props.maxLen) + '…' : part,
  }))
  if (parts.length <= 2)
    return [root, ...parts]
  return [root, { label: '...' }, ...parts.slice(-2)]
})

const { data: list } = await useLazyFetch<ListItem[]>('/api/fs/list', {
  query: computed(() => ({
    path: dirpath.value.join('/'),
  })),
  default: () => [],
  watch: [dirpath],
  transform: (items) => {
    return [...items].sort((a, b) => {
      if (a.is_dir !== b.is_dir) return a.is_dir ? -1 : 1  // folders first
      return a.name.localeCompare(b.name, undefined, { sensitivity: 'base' })  // alphabetical
    })
  },
})

function getLink(item: ListItem) {
  return ['', ...dirpath.value, item.name].join('/')
}

function isDisabled(item: ListItem) {
  return (!item.is_dir) && (!getFileType(item.name))
}

function getIcon(item: ListItem) {
  if (item.is_dir) return 'material-symbols-folder'
  const fileType = getFileType(item.name)
  return fileType?.icon || 'mdi-file'
}

function getColor(item: ListItem) {
  return getFileType(item.name) ? 'primary' : 'neutral'
}

function getTooltip(item: ListItem) {
  return item.is_dir ? item.name : `${item.name} (${prettyBytes(item.size)})`
}

function setSelected(item: ListItem) {
  selected.value = item.name
}

function goTo(item: ListItem) {
  const path = getLink(item)
  if (path) router.push(path)
}
</script>

<style>
.scrollbar-thin {
  scrollbar-width: thin;
}
</style>

<template>
  <div class="flex flex-col h-full">
    <div class="shrink-0 border-b border-default">
      <div class="flex items-center gap-1 px-1.5 h-9">
        <template v-for="(crumb, index) in breadcrumbs" :key="index">
          <UButton
            :icon="crumb.icon"
            :to="crumb.to"
            variant="ghost"
            color="neutral"
            size="sm"
            class="px-1 py-0.5"
          >
            {{ crumb.label }}
          </UButton>
          <span>/</span>
        </template>
      </div>
    </div>
    <div class="flex-1 overflow-x-hidden overflow-y-auto scrollbar-thin flex flex-col">
      <template v-for="(item, index) in list" :key="index">
        <UTooltip :text="getTooltip(item)">
          <UButton
            :icon="getIcon(item)"
            :to="getLink(item)"
            :color="getColor(item)"
            :disabled="isDisabled(item)"
            :variant="selected === item.name ? 'subtle' : 'ghost'"
            class="px-2 py-1.25 text-left rounded-none whitespace-nowrap"
            @click.prevent="setSelected(item)"
            @dblclick="goTo(item)"
          >
            {{ item.name }}
          </UButton>
        </UTooltip>
      </template>
    </div>
  </div>
</template>
