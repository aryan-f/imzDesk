<script setup lang="ts">

const toast = useToast()

const props = defineProps<{
  path: string
}>()

const ready = ref<boolean>(false)

const loading = ref<boolean>(true)
const image = ref<number[][] | null>(null)

async function fetchImage() {
  loading.value = true

  try {
    const data: any = await $fetch('/api/imzML/image', {
      method: 'POST',
      query: { path: props.path }
    })
    image.value = data.values
  } catch (error) {
    toast.add({
      title: 'Failed to load image.',
      description: 'Check the logs for more information.',
      icon: 'ic-round-error-outline',
      color: 'error'
    })
    image.value = null
  }

  loading.value = false
}

const modes = [
  { label: 'TIC', value: 'tic' },
]

const mode = ref<string>('tic')

async function onReady() {
  ready.value = true
  await fetchImage()
}

async function onUpdate() {
  if (!ready.value) {
    return
  }
  await fetchImage()
}

function onFailed() {
  toast.add({
    title: '.imz5 conversion onFailed.',
    description: 'Check the logs for more information.',
    icon: 'ic-round-error-outline',
    color: 'error'
  })
}
</script>

<template>
  <div class="flex w-full h-full">
    <div class="flex flex-col h-full flex-1">
      <div class="min-h-0 min-w-0 flex-1 flex flex-col">
        <div class="flex justify-between p-3">
          <div class="shrink-0 flex items-center gap-2">
            <UFormField orientation="horizontal" label="Mode:">
              <USelect v-model="mode" :items="modes" />
            </UFormField>
<!--            <template v-if="mode === 'peak'">-->
<!--              <span class="text-xs">Peak:</span>-->
<!--              <UInput v-model.number="settings.peak.peak" type="number" size="xs" class="w-24" min="0" max="2000" step="0.001"/>-->
<!--              <span class="text-xs">Width:</span>-->
<!--              <UInput v-model.number="settings.peak.width" type="number" size="xs" class="w-16" min="0.1" step="0.1"/>-->
<!--            </template>-->
            <UButton color="neutral" size="xs" :disabled="!ready" @click="onUpdate">Update</UButton>
          </div>
          <div class="shrink-0 flex items-center gap-2">
            <ImzMLLoader :path="path" @ready="onReady" @failed="onFailed" />
          </div>
        </div>
        <div class="flex-1 p-3 pt-0">
          <ImzMLImage :mode="mode" :data="image" :loading="loading" />
        </div>
      </div>
      <div class="h-90 shrink-0 border-t border-default flex flex-col">
        <div class="flex gap-2 p-3">
          <div class="flex items-center gap-4">
            <span class="font-medium text-default text-sm">Displaying:</span>
            <UCheckbox label="Global" />
            <UCheckbox label="A" />
            <UCheckbox label="B" />
            <UCheckbox label="C" />
            <UCheckbox label="D" />
            <UCheckbox label="E" />
            <UCheckbox label="F" />
          </div>
        </div>
        <div class="flex-1 p-3 pt-0">
          <!--DisplaySpectrum-->
        </div>
      </div>
    </div>
    <div class="w-64 shrink-0 border-l border-default">
      <div class="flex flex-col gap-2 p-4">
        <div class="text-sm font-bold mb-1.5">Meta Data</div>
      </div>
    </div>
  </div>
</template>
