<script setup lang="ts">
import prettyBytes from 'pretty-bytes'
import {type DirectoryEntry} from '~/types/entry'

const props = defineProps<{
  entry: DirectoryEntry,
  selected: boolean,
  viewing: boolean,
}>()

const router = useRouter()

const to = computed(() => {
  if (props.entry.directory) {
    return `/workspace/${props.entry.path}`
  }
})

const icon = computed(() => {
  if (props.entry.directory) return 'mdi-folder'
  if (props.entry.type) return 'iconamoon-file-duotone'
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
  if (!props.entry.size) return props.entry.label
  return `${props.entry.label} (${formattedSize.value})`
})

const badgeColor = computed(() => {
  switch (props.entry.type) {
    case 'WSI': return 'primary'
    case 'MSI': return 'secondary'
    default: return 'neutral'
  }
})

function clicked() {
  // Anything?
}

function doubleClicked() {
  if (to.value) {
    router.push({ path: to.value })
  }
  // TODO: Open files via `query`
}
</script>

<template>
  <UButton
    :to="to"
    class="w-full min-w-0 cursor-pointer py-1"
    variant="ghost"
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
          {{ entry.label }}
        </div>
      </UTooltip>
    </template>
    <template #trailing>
      <div class="ml-auto shrink-0 flex items-center gap-1">
        <UBadge v-if="props.entry.type" :label="props.entry.type" :color="badgeColor" variant="soft" class="px-1 py-px" />
        <div v-if="viewing">
          <UIcon name="iconoir-eye-solid" class="text-success" />
        </div>
      </div>
    </template>
  </UButton>
</template>
