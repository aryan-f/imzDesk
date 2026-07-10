<script setup lang="ts">
import type { MSIDisplay } from '~/types/images'

const props = defineProps<{
  display: MSIDisplay
}>()

const emit = defineEmits<{
  apply: [display: MSIDisplay]
}>()

function cloneDisplay(display: MSIDisplay): MSIDisplay {
  return {
    preprocessing: { ...display.preprocessing },
    cubing: { ...display.cubing },
    reduction: { ...display.reduction },
  }
}

const draft = reactive<MSIDisplay>(cloneDisplay(props.display))

const normalizationOptions = [
  { label: 'None', value: 'none' },
  { label: 'TIC', value: 'tic' },
  { label: 'RMS', value: 'rms' },
  { label: 'Median', value: 'median' },
  { label: 'Max', value: 'max' },
]

const centroidingOptions = [
  { label: 'None', value: 'none' },
  { label: 'PeakPickerHiRes', value: 'peak_picker_hi_res' },
]

const cubingOptions = [
  { label: 'Binning', value: 'bin' },
  { label: 'Embeddings', value: 'embed' },
]

const embeddingModelOptions = [
  { label: 'DreaMS', value: 'roman-bushuiev/DreaMS' },
]

const defaultReduction = { label: 'PCA', value: 'pca' }

const reductionOptions = [
  { label: 'TIC', value: 'tic' },
  defaultReduction,
  { label: 'NMF', value: 'nmf' },
  { label: 't-SNE', value: 'tsne' },
]

const availableReductionOptions = computed(() => reductionOptions.map(option => ({
  ...option,
  disabled: option.value === 'tic' && draft.cubing.method !== 'bin',
})))

const selectedReduction = computed(() => (
  reductionOptions.find(option => option.value === props.display.reduction.method) ?? defaultReduction
))

const usesColormap = computed(() => draft.reduction.method === 'tic')

const scalingOptions = [
  { label: 'Robust', value: 'robust' },
  { label: 'Min-max', value: 'minmax' },
  { label: 'Z-score', value: 'zscore' },
]

const defaultColormap = {
  label: 'Viridis',
  value: 'viridis',
  gradient: 'linear-gradient(90deg, #440154, #31688e, #35b779, #fde725)',
}

const colormapOptions = [
  defaultColormap,
  { label: 'Magma', value: 'magma', gradient: 'linear-gradient(90deg, #000004, #51127c, #b73779, #fcfdbf)' },
  { label: 'Inferno', value: 'inferno', gradient: 'linear-gradient(90deg, #000004, #57106e, #bc3754, #fcffa4)' },
  { label: 'Plasma', value: 'plasma', gradient: 'linear-gradient(90deg, #0d0887, #7e03a8, #cc4778, #f0f921)' },
  { label: 'Cividis', value: 'cividis', gradient: 'linear-gradient(90deg, #00224e, #575d6d, #a59c74, #fee838)' },
]

const selectedColormap = computed(() => (
  colormapOptions.find(option => option.value === draft.reduction.colormap) ?? defaultColormap
))

watch(
  () => props.display,
  (value) => {
    const next = cloneDisplay(value)
    draft.preprocessing = next.preprocessing
    draft.cubing = next.cubing
    draft.reduction = next.reduction
  },
  { deep: true },
)

watch(
  () => [draft.cubing.method, draft.reduction.method],
  () => {
    if (draft.cubing.method !== 'bin' && draft.reduction.method === 'tic') {
      draft.reduction.method = 'pca'
    }
    if (draft.reduction.method === 'tic') {
      draft.reduction.components = 1
    } else if (draft.reduction.components < 3) {
      draft.reduction.components = 3
    }
  },
  { immediate: true },
)

function apply() {
  emit('apply', cloneDisplay(draft))
}
</script>

<template>
  <UPopover>
    <div class="inline-flex items-center bg-default border border-default rounded-lg pl-2 pr-1.5 py-px cursor-pointer select-none">
      <span class="text-sm text-dimmed mr-1">mode</span>
      <span class="font-data text-base">{{ selectedReduction.label }}</span>
      <UIcon name="mdi-chevron-down" class="ml-1" />
    </div>
    <template #content>
      <div class="w-96 p-3">
        <div class="mb-3 flex items-center justify-between">
          <div>
            <div class="text-sm font-medium text-default">
              Mass Spectrometry Image
            </div>
            <div class="text-xs text-dimmed">
              Visualization Mode
            </div>
          </div>
          <UButton label="Apply" color="secondary" variant="soft" size="sm" @click="apply" />
        </div>
        <div class="space-y-3">
          <section class="space-y-2">
            <div class="flex items-center gap-2 text-xs font-medium uppercase text-muted">
              <UIcon name="i-lucide-sliders-horizontal" class="size-3.5" />
              Preprocessing
            </div>
            <div class="grid grid-cols-2 gap-2">
              <UFormField label="Normalization" size="sm">
                <USelect v-model="draft.preprocessing.normalization" :items="normalizationOptions" class="w-full" />
              </UFormField>
              <UFormField label="Centroiding" size="sm">
                <USelect v-model="draft.preprocessing.centroiding" :items="centroidingOptions" class="w-full" />
              </UFormField>
              <USwitch v-model="draft.preprocessing.baselineCorrection" label="Baseline correction" color="secondary" />
              <USwitch v-model="draft.preprocessing.smoothing" label="Spectral smoothing" color="secondary" />
            </div>
          </section>
          <section class="space-y-2">
            <div class="flex items-center gap-2 text-xs font-medium uppercase text-muted">
              <UIcon name="i-lucide-grid-3x3" class="size-3.5" />
              Grid Formation
            </div>
            <div class="grid grid-cols-2 gap-2">
              <UFormField label="Method" size="sm">
                <USelect v-model="draft.cubing.method" :items="cubingOptions" class="w-full" />
              </UFormField>
              <UFormField v-if="draft.cubing.method === 'embed'" label="Model" size="sm">
                <USelect v-model="draft.cubing.model" :items="embeddingModelOptions" class="w-full" />
              </UFormField>
              <UFormField v-else label="Bin width" size="sm">
                <UInput v-model.number="draft.cubing.binWidth" type="number" min="0.001" step="0.001" class="w-full font-data" />
              </UFormField>
            </div>
            <div class="grid grid-cols-2 gap-2">
              <UFormField label="m/z min" size="sm">
                <UInput v-model.number="draft.cubing.mzMin" type="number" min="0" class="w-full font-data" />
              </UFormField>
              <UFormField label="m/z max" size="sm">
                <UInput v-model.number="draft.cubing.mzMax" type="number" min="0" class="w-full font-data" />
              </UFormField>
            </div>
          </section>
          <section class="space-y-2">
            <div class="flex items-center gap-2 text-xs font-medium uppercase text-muted">
              <UIcon name="i-lucide-palette" class="size-3.5" />
              Reduction
            </div>
            <div class="grid grid-cols-3 gap-2">
              <UFormField label="Method" size="sm">
                <USelect v-model="draft.reduction.method" :items="availableReductionOptions" class="w-full" />
              </UFormField>
              <UFormField label="Scaling" size="sm">
                <USelect v-model="draft.reduction.scaling" :items="scalingOptions" class="w-full" />
              </UFormField>
              <UFormField v-if="usesColormap" label="Colormap" size="sm">
                <UPopover>
                  <UButton color="neutral" variant="outline" class="w-full justify-between">
                    <span class="flex min-w-0 items-center gap-2">
                      <span class="h-3 w-10 shrink-0 rounded-sm border border-default" :style="{ background: selectedColormap.gradient }" />
                      <span class="truncate">{{ selectedColormap.label }}</span>
                    </span>
                    <UIcon name="i-lucide-chevron-down" class="size-3.5 shrink-0 text-dimmed" />
                  </UButton>
                  <template #content>
                    <div class="w-44 p-1">
                      <UButton v-for="option in colormapOptions" :key="option.value" color="neutral" :variant="draft.reduction.colormap === option.value ? 'soft' : 'ghost'" class="w-full justify-start" @click="draft.reduction.colormap = option.value">
                        <span class="flex min-w-0 items-center gap-2">
                          <span class="h-3 w-12 shrink-0 rounded-sm border border-default" :style="{ background: option.gradient }" />
                          <span class="truncate">{{ option.label }}</span>
                        </span>
                      </UButton>
                    </div>
                  </template>
                </UPopover>
              </UFormField>
              <UFormField v-else label="Components" size="sm">
                <UInput v-model.number="draft.reduction.components" type="number" min="3" max="8" class="w-full font-data" />
              </UFormField>
            </div>
          </section>
        </div>
      </div>
    </template>
  </UPopover>
</template>
