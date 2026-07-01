<script setup lang="ts">
import prettyBytes from 'pretty-bytes'
import type {FilesystemEntry} from '~/types/filesystem'

const props = defineProps<{
  entry: FilesystemEntry
  active?: boolean
}>()

const emit = defineEmits<{
  select: [entry: FilesystemEntry]
}>()

const { openDirectory, openFile } = useWorkspace()

const icon = computed(() => {
  if (props.entry.directory) {
    return 'mdi-folder'
  }
  if (props.entry.type) {
    switch (props.entry.type) {
      case 'MSI': return 'streamline-image-blur'
      case 'WSI': return 'healthicons-cell-nuclei-outline-24px'
    }
  }
  return 'iconamoon-file'
})

const iconColorClass = computed(() => {
  if (props.entry.directory) return 'text-primary'
  if (props.entry.type) return 'text-neutral'
  return 'text-dimmed' // Anything Else
})

const formattedSize = computed(() => {
  if (props.entry.size === undefined) return undefined
  return prettyBytes(props.entry.size)
})

const tooltip = computed(() => {
  if (!props.entry.size) return props.entry.name
  return `${props.entry.name} (${formattedSize.value})`
})

const badgeColor = computed(() => {
  switch (props.entry.type) {
    case 'WSI': return 'primary'
    case 'MSI': return 'secondary'
    default: return 'neutral'
  }
})

function clicked() {
  emit('select', props.entry)
}

function doubleClicked() {
  if (props.entry.directory) openDirectory(props.entry.path)
  else if (props.entry.type) openFile(props.entry.type, props.entry.name)
}
</script>

<template>
  <UButton
    class="w-full min-w-0 cursor-pointer py-1"
    variant="ghost"
    :active="active"
    active-variant="outline"
    color="neutral"
    @click.prevent="clicked"
    @dblclick="doubleClicked"
  >
    <template #leading>
      <UIcon :name="icon" :class="[iconColorClass, 'size-4 shrink-0']" />
    </template>
    <template #default>
      <UTooltip :text="tooltip" :delay-duration="250">
        <div class="min-w-0 truncate text-neutral select-none">
          {{ entry.name }}
        </div>
      </UTooltip>
    </template>
    <template #trailing>
      <div class="ml-auto shrink-0 flex items-center gap-1">
        <UBadge v-if="entry.type" :label="entry.type" :color="badgeColor" variant="soft" class="px-1 py-px" />
      </div>
    </template>
  </UButton>
</template>
