<script setup lang="ts">
const { state } = useWorkspace()

const wsi = computed(() => state.value.opened.WSI)
const msi = computed(() => state.value.opened.MSI)
const bothOpened = computed(() => wsi.value && msi.value)

const overlaid = ref(false)
</script>

<template>
  <div class="flex h-full">
    <div class="flex-1 flex flex-col min-w-0">
      <div class="flex min-h-0 flex-1">
        <template v-if="overlaid && bothOpened">
          <ViewportPanel :wsi="wsi" :msi="msi" />
        </template>
        <template v-else>
          <ViewportPanel v-if="wsi" :wsi="wsi" :other="!!msi" />
          <ViewportPanel v-if="msi" :msi="msi" :other="!!wsi" />
        </template>
      </div>
    </div>
    <ViewportSidebar />
  </div>
</template>
