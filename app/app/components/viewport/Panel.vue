<script setup lang="ts">
const { state, setActive, closeFile } = useWorkspace()

const props = withDefaults(defineProps<{
  wsi: string | null
  msi: string | null
  other: boolean
}>(), {
  wsi: null,
  msi: null,
  other: false,
})

const overlaid = computed(() => props.wsi && props.msi)

function closeAll() {
  if (props.wsi) closeFile('WSI')
  if (props.msi) closeFile('MSI')
}
</script>

<template>
  <div :class="{ 'max-w-1/2': other, 'last:border-l': other }" class="relative flex flex-col flex-1 border-default">
    <div class="flex items-center bg-elevated px-3 py-1 text-base border-b border-default">
      <div v-if="wsi" class="flex truncate gap-2 cursor-pointer" @click="setActive('WSI')">
        <UBadge label="WSI" color="primary" variant="soft" class="px-1 py-px" />
        <div class="font-data text-sm truncate">{{ wsi }}</div>
      </div>
      <div v-if="overlaid">and</div>
      <div v-if="msi" class="flex truncate gap-2 cursor-pointer" @click="setActive('MSI')">
        <UBadge label="MSI" color="secondary" variant="soft" class="px-1 py-px" />
        <div class="font-data text-sm truncate">{{ msi }}</div>
      </div>
      <div class="flex-1"></div>
      <UButton
        icon="mdi-close"
        variant="ghost"
        color="error"
        size="xs"
        @click="closeAll"
      />
    </div>
    <div class="flex-1 p-2">
      <USkeleton class="h-full" />
    </div>
  </div>
</template>

