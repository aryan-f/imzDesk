<script setup lang="ts">
const { state } = useWorkspace()

const wsi = computed(() => state.value.opened.WSI)
const msi = computed(() => state.value.opened.MSI)
const bothOpened = computed(() => Boolean(wsi.value && msi.value))
const overlaid = ref(false)
const registered = ref(false)
const split = computed(() => !overlaid.value || !bothOpened.value)

watch([wsi, msi], () => {
  registered.value = false
  overlaid.value = false
})
</script>

<template>
  <div class="flex h-full">
    <div class="flex-1 flex flex-col min-w-0">
      <div class="flex min-h-0 flex-1">
        <ViewportPanel
          v-if="wsi"
          v-show="split"
          :wsi="wsi"
          :msi="msi"
          :display-wsi="split"
          :other="!!msi && split"
          :registered="registered"
          :overlay="overlaid"
          @update:registered="registered = $event"
          @update:overlay="overlaid = $event"
        />
        <ViewportPanel
          v-if="msi"
          :wsi="wsi"
          :msi="msi"
          :display-wsi="overlaid && bothOpened"
          display-msi
          :other="!!wsi && split"
          :registered="registered"
          :overlay="overlaid"
          @update:registered="registered = $event"
          @update:overlay="overlaid = $event"
        />
      </div>
    </div>
    <ViewportSidebar />
  </div>
</template>
