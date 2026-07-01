<script setup lang="ts">
import {type TabsItem} from '@nuxt/ui'

const { state } = useWorkspace()

const activeColor = computed(() => {
  switch (state.value.active) {
    case 'WSI': return 'primary'
    case 'MSI': return 'secondary'
  }
})

function activeColorClass(prefix: string) {
  return `${prefix}-${activeColor.value}`
}

const tabs = ref<TabsItem[]>([
  { value: 'metadata', label: 'Metadata' },
  { value: 'tags', label: 'Tags' },
  { value: 'annotations', label: 'Annotations' },
])

const tab = ref('metadata')
const activeFilename = computed(() => {
  if (!state.value.active) return ''
  return state.value.opened[state.value.active]
})
</script>

<template>
  <div class="flex w-76 shrink-0 flex-col border-s border-default bg-muted">
    <div class="h-12 border-b border-default">
      <div class="flex flex-col justify-center mx-3 my-2 px-2 border-l-3" :class="activeColorClass('border')">
        <div class="text-xs leading-4" :class="activeColorClass('text')">{{ state.active }}</div>
        <div class="truncate text-sm leading-4 font-data">{{ activeFilename }}</div>
      </div>
    </div>
    <UTabs
      :color="activeColor"
      :content="false"
      :items="tabs"
      :ui="{ trigger: 'flex-1' }"
      class="gap-4 w-full"
      variant="link"
      v-model="tab"
    />
    <div class="p-3 h-full">
      <USkeleton class="h-full overflow-hidden" />
    </div>
  </div>
</template>
