<script setup lang="ts">
import {type ImageResponse, type Selection} from '~/types/imzML'

const toast = useToast()

const props = defineProps<{
  path: string
}>()

const ready = ref<boolean>(false)

const modes = [
  { label: 'Ion Slice', value: 'ion' },
  { label: 'Bin → PCA', value: 'pca' },
  { label: 'Bin → PCA → K-Means', value: 'kmn' },
  { label: 'Total Ion Current', value: 'tic' },
]

const normalizations = [
  { label: 'None', value: null },
  { label: 'Total Ion Current', value: 'tic' },
  { label: 'Root Mean Square', value: 'rms' },
]

const mode = ref<string>('tic')

const targetIon = ref<number>(554.6)
const tolerance = ref<number>(1)
const binWidth = ref<number>(1)
const numComponents = ref<number>(3)
const normalization = ref<string>('tic')
const numClusters = ref<number>(7)

const loading = ref<boolean>(true)
const image = ref<ImageResponse | null>(null)

async function fetchImage() {
  loading.value = true

  try {
    image.value = await $fetch('/api/imzML/image', {
      method: 'POST',
      query: { path: props.path },
      body: {
        mode: mode.value,
        targetIon: targetIon.value,
        tolerance: tolerance.value,
        binWidth: binWidth.value,
        numComponents: numComponents.value,
        normalization: normalization.value,
        numClusters: numClusters.value,
      }
    })
  } catch (error) {
    toast.add({
      title: 'Failed to load values.',
      description: 'Check the logs for more information.',
      icon: 'ic-round-error-outline',
      color: 'error'
    })
    image.value = null
  }

  loading.value = false
}

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

const display = reactive({
  log1p: false,
})

const selections = ref<Selection[]>([])

watch(
  () => props.path,
  () => {
    ready.value = false
    loading.value = true
    image.value = null
    selections.value = []
  }
)
</script>

<template>
  <div class="flex w-full h-full">
    <div class="flex flex-col h-full flex-1">
      <div class="min-h-0 min-w-0 flex-1 flex flex-col">
        <div class="flex justify-between p-3">
          <div class="shrink-0 flex items-center gap-2">
            <UFormField orientation="horizontal" label="Mode:">
              <USelect v-model="mode" :items="modes" class="w-49" />
            </UFormField>
            <UPopover>
              <UTooltip text="Settings">
                <UButton icon="solar-tuning-bold" color="neutral" variant="outline" :disabled="mode === 'tic'" />
              </UTooltip>
              <template #content>
                <div class="flex flex-col gap-2 p-4">
                  <UFormField v-if="mode === 'ion'" orientation="horizontal" label="Target Ion:" size="sm">
                    <UInputNumber v-model="targetIon" color="neutral" :min="1" max="2000" :step="0.1" orientation="vertical" />
                  </UFormField>
                  <UFormField v-if="mode === 'ion'" orientation="horizontal" label="Tolerance:" size="sm">
                    <UInputNumber v-model="tolerance" color="neutral" :min="0.001" :step="0.001" orientation="vertical" />
                  </UFormField>
                  <UFormField v-if="mode === 'pca' || mode == 'kmn'" orientation="horizontal" label="Bin Width:" size="sm">
                    <UInputNumber v-model="binWidth" color="neutral" :min="0.001" :step="0.001" orientation="vertical" />
                  </UFormField>
                  <UFormField v-if="mode === 'pca' || mode == 'kmn'" orientation="horizontal" label="Number of Components:" size="sm">
                    <UInputNumber v-model="numComponents" color="neutral" :min="3" :step="1" orientation="vertical" />
                  </UFormField>
                  <UFormField v-if="mode === 'pca' || mode == 'kmn'" orientation="horizontal" label="Normalization:" size="sm">
                    <USelect v-model="normalization" :items="normalizations" orientation="vertical" class="w-45" />
                  </UFormField>
                  <UFormField v-if="mode == 'kmn'" orientation="horizontal" label="Number of Clusters:" size="sm">
                    <UInputNumber v-model="numClusters" color="neutral" :min="2" :step="1" orientation="vertical" />
                  </UFormField>
                </div>
              </template>
            </UPopover>
            <UButton color="neutral" :disabled="!ready" @click="onUpdate">Update</UButton>
          </div>
          <div class="shrink-0 flex items-center gap-2">
            <UCheckbox label="Log" size="xs" v-model="display.log1p" />
            <USeparator orientation="vertical" class="ml-1.5" />
            <ImzMLLoader :path="path" @ready="onReady" @failed="onFailed" />
          </div>
        </div>
        <div class="flex-1 p-3 pt-0">
          <ImzMLImage
            :loading="loading"
            :display="display"
            :image="image"
            v-model:selections="selections"
          />
        </div>
      </div>
      <div class="h-72 shrink-0 border-t border-default flex flex-col">
        <div class="flex-1 p-3">
          <ImzMLSpectrum :path="props.path" :ready="ready" :selections="selections" />
        </div>
      </div>
    </div>
    <div class="w-64 shrink-0 border-l border-default">
      <div class="flex flex-col gap-2 p-4">
        <div class="text-sm font-bold mb-1.5">Meta Data</div>
        <div class="text-xs">To be implemented...</div>
      </div>
    </div>
  </div>
</template>
