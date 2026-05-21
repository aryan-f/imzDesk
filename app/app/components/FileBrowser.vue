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

const search = ref('')

const listViewport = ref<HTMLElement | null>(null)
const viewportHeight = ref(0)
const scrollTop = ref(0)

const rowHeight = 30  // Determines how many items fit in the viewport
const overscan = 50  // How many rows to render besides the ones currently visible

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

watch(dirpath, () => {
  selected.value = null
  search.value = ''
  scrollTop.value = 0
  listViewport.value?.scrollTo({ top: 0 })
})

const breadcrumbs = computed(() => {
  const root = { icon: 'material-symbols-folder', to: '/' }
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

const filteredList = computed(() => {
  const query = search.value.trim().toLowerCase()
  if (!query) return list.value
  return list.value.filter(item => item.name.toLowerCase().includes(query))
})

const totalHeight = computed(() => filteredList.value.length * rowHeight)

const visibleStart = computed(() => {
  return Math.max(0, Math.floor(scrollTop.value / rowHeight) - overscan)
})

const visibleEnd = computed(() => {
  return Math.min(
    filteredList.value.length,
    Math.ceil((scrollTop.value + viewportHeight.value) / rowHeight) + overscan,
  )
})

const virtualList = computed(() => {
  return filteredList.value.slice(visibleStart.value, visibleEnd.value)
})

const offsetTop = computed(() => visibleStart.value * rowHeight)

watch(search, () => {
  selected.value = null
  scrollTop.value = 0
  listViewport.value?.scrollTo({ top: 0 })
})

function updateViewportHeight() {
  viewportHeight.value = listViewport.value?.clientHeight ?? 0
}

function onScroll() {
  scrollTop.value = listViewport.value?.scrollTop ?? 0
}

let resizeObserver: ResizeObserver | null = null

onMounted(() => {
  updateViewportHeight()
  if (!listViewport.value) return
  resizeObserver = new ResizeObserver(updateViewportHeight)
  resizeObserver.observe(listViewport.value)
})

onBeforeUnmount(() => {
  resizeObserver?.disconnect()
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
          <UButton :icon="crumb.icon" :to="crumb.to" variant="ghost" color="neutral" size="sm" class="px-1 py-0.5">
            {{ crumb.label }}
          </UButton>
          <span>/</span>
        </template>
      </div>
      <div class="flex items-center gap-1.5 px-1.5 pb-1.5">
        <UInput v-model="search" icon="i-lucide-search" placeholder="Search by name..." size="sm" class="flex-1" />
        <UPopover>
          <UButton icon="i-lucide-sliders-horizontal" color="neutral" variant="soft" size="sm">
            Filters
          </UButton>
          <template #content>
            <div class="p-3 text-sm text-muted">
              Not yet implemented.
            </div>
          </template>
        </UPopover>
      </div>
    </div>
    <div ref="listViewport" class="flex-1 overflow-x-hidden overflow-y-auto scrollbar-thin" @scroll="onScroll">
      <div v-if="filteredList.length" class="relative" :style="{ height: `${totalHeight}px` }">
        <div class="absolute inset-x-0 top-0" :style="{ transform: `translateY(${offsetTop}px)` }">
          <template v-for="item in virtualList" :key="item.name">
            <UTooltip :text="getTooltip(item)">
              <UButton
                :icon="getIcon(item)"
                :to="getLink(item)"
                :color="getColor(item)"
                :disabled="isDisabled(item)"
                :variant="selected === item.name ? 'subtle' : 'ghost'"
                class="w-full h-8 px-2 py-0 text-left justify-start rounded-none whitespace-nowrap"
                @click.prevent="setSelected(item)"
                @dblclick="goTo(item)"
              >
                {{ item.name }}
              </UButton>
            </UTooltip>
          </template>
        </div>
      </div>
      <div v-else class="px-3 py-4 text-sm text-muted">
        <template v-if="search">
          No items found.
        </template>
      </div>
    </div>
  </div>
</template>
