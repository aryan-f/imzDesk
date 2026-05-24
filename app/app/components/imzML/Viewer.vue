<script setup lang="ts">
import {type ImageResponse, type Selection} from '~/types/imzML'

const toast = useToast()

const props = defineProps<{
  path: string
}>()

const ready = ref<boolean>(false)

const modes = [
  {
    value: 'tic',
    label: 'Total Ion Current',
    parameters: ['colormap']
  },
  {
    value: 'ion',
    label: 'Ion Image',
    parameters: ['target_ion', 'tolerance', 'colormap'],
  },
  {
    value: 'pca',
    label: 'Bin → PCA',
    parameters: ['bin_width', 'n_components', 'normalization'],
  },
  {
    value: 'kmn',
    label: 'Bin → PCA → K-Means',
    parameters: ['bin_width', 'n_components', 'normalization', 'n_clusters', 'colormap'],
  },
]

const normalizationMethods = [
  { label: 'None', value: null },
  { label: 'Root Mean Square', value: 'rms' },
  { label: 'Total Ion Current', value: 'tic' },
]

const colormaps = [
  { label: 'Viridis', value: 'viridis', avatar: { src: '/images/colormaps/viridis.png' } },
  { label: 'Plasma', value: 'plasma', avatar: { src: '/images/colormaps/plasma.png' } },
  { label: 'Inferno', value: 'inferno', avatar: { src: '/images/colormaps/inferno.png' } },
  { label: 'Magma', value: 'magma', avatar: { src: '/images/colormaps/magma.png' } },
  { label: 'Cividis', value: 'cividis', avatar: { src: '/images/colormaps/cividis.png' } },
  { label: 'Grayscale', value: 'gray', avatar: { src: '/images/colormaps/gray.png' } },
  { label: 'Hot', value: 'hot', avatar: { src: '/images/colormaps/hot.png' } },
  { label: 'Cool', value: 'cool', avatar: { src: '/images/colormaps/cool.png' } },
  { label: 'Spring', value: 'spring', avatar: { src: '/images/colormaps/spring.png' } },
  { label: 'Summer', value: 'summer', avatar: { src: '/images/colormaps/summer.png' } },
  { label: 'Autumn', value: 'autumn', avatar: { src: '/images/colormaps/autumn.png' } },
  { label: 'Winter', value: 'winter', avatar: { src: '/images/colormaps/winter.png' } },
  { label: 'Jet', value: 'jet', avatar: { src: '/images/colormaps/jet.png' } },
  { label: 'Turbo', value: 'turbo', avatar: { src: '/images/colormaps/turbo.png' } },
  { label: 'Rainbow', value: 'rainbow', avatar: { src: '/images/colormaps/rainbow.png' } },
  { label: 'Blues', value: 'Blues', avatar: { src: '/images/colormaps/Blues.png' } },
  { label: 'Greens', value: 'Greens', avatar: { src: '/images/colormaps/Greens.png' } },
  { label: 'Reds', value: 'Reds', avatar: { src: '/images/colormaps/Reds.png' } },
  { label: 'Purples', value: 'Purples', avatar: { src: '/images/colormaps/Purples.png' } },
  { label: 'Oranges', value: 'Oranges', avatar: { src: '/images/colormaps/Oranges.png' } },
  { label: 'Set1', value: 'Set1', avatar: { src: '/images/colormaps/Set1.png' } },
  { label: 'Set2', value: 'Set2', avatar: { src: '/images/colormaps/Set2.png' } },
  { label: 'Set3', value: 'Set3', avatar: { src: '/images/colormaps/Set3.png' } },
  { label: 'Tab10', value: 'tab10', avatar: { src: '/images/colormaps/tab10.png' } },
  { label: 'Tab20', value: 'tab20', avatar: { src: '/images/colormaps/tab20.png' } },
]

const mode = ref<string>('tic')

const parameters = ref({
  target_ion: 554.6,
  tolerance: 1,
  bin_width: 1,
  n_components: 3,
  normalization: 'rms',
  n_clusters: 5,
  colormap: 'viridis',
})

const modeParameters = computed(() => {
  const activeMode = modes.find(item => item.value === mode.value)!
  return  Object.fromEntries(activeMode.parameters.map(
    key => [key, parameters.value[key as keyof typeof parameters.value]]
  ))
})

const loading = ref<boolean>(true)
const image = ref<ImageResponse | null>(null)

async function fetchImage() {
  loading.value = true

  try {
    image.value = await $fetch('/api/imzML/image', {
      method: 'POST',
      query: { path: props.path },
      body: { mode: mode.value, ...modeParameters.value }
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

const display = reactive({ })

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
                <UButton icon="solar-tuning-bold" color="neutral" variant="outline" :disabled="!modeParameters" />
              </UTooltip>
              <template #content>
                <div class="flex flex-col gap-2 p-4">
                  <template v-if="Object.keys(modeParameters).includes('target_ion')">
                    <UFormField orientation="horizontal" label="Target Ion:" size="sm">
                      <UInputNumber v-model="parameters.target_ion" color="neutral" :min="1" :max="2000" :step="0.1" orientation="vertical" />
                    </UFormField>
                  </template>
                  <template v-if="Object.keys(modeParameters).includes('tolerance')">
                    <UFormField v-if="mode === 'ion'" orientation="horizontal" label="Tolerance:" size="sm">
                      <UInputNumber v-model="parameters.tolerance" color="neutral" :min="0.001" :step="0.001" orientation="vertical" />
                    </UFormField>
                  </template>
                  <template v-if="Object.keys(modeParameters).includes('bin_width')">
                    <UFormField orientation="horizontal" label="Bin Width:" size="sm">
                      <UInputNumber v-model="parameters.bin_width" color="neutral" :min="0.001" :step="0.001" orientation="vertical"/>
                    </UFormField>
                  </template>
                  <template v-if="Object.keys(modeParameters).includes('n_components')">
                    <UFormField orientation="horizontal" label="Number of Components:" size="sm">
                      <UInputNumber v-model="parameters.n_components" color="neutral" :min="3" :step="1" orientation="vertical"/>
                    </UFormField>
                  </template>
                  <template v-if="Object.keys(modeParameters).includes('normalization')">
                    <UFormField orientation="horizontal" label="Normalization:" size="sm">
                      <USelect v-model="parameters.normalization" :items="normalizationMethods" orientation="vertical" class="w-45"/>
                    </UFormField>
                  </template>
                  <template v-if="Object.keys(modeParameters).includes('n_clusters')">
                    <UFormField orientation="horizontal" label="Number of Clusters:" size="sm">
                      <UInputNumber v-model="parameters.n_clusters" color="neutral" :min="2" :step="1" orientation="vertical"/>
                    </UFormField>
                  </template>
                  <template v-if="Object.keys(modeParameters).includes('colormap')">
                    <UFormField orientation="horizontal" label="Color Map:" size="sm">
                      <USelect v-model="parameters.colormap" :items="colormaps" class="w-45" />
                    </UFormField>
                  </template>
                </div>
              </template>
            </UPopover>
            <UButton color="neutral" :loading="loading && ready" :disabled="!ready" @click="onUpdate">Update</UButton>
          </div>
          <div class="shrink-0 flex items-center gap-2">
            <ImzMLLoader :path="path" @ready="onReady" @failed="onFailed" />
          </div>
        </div>
        <div class="flex-1 p-3 pt-0">
          <ImzMLImage
            :loading="!ready || image === null"
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
    <div class="w-72 shrink-0 border-l border-default flex flex-col">
      <ImzMLMetadata :path="path" />
    </div>
  </div>
</template>
