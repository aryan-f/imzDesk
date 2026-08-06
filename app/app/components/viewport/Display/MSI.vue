<script setup lang="ts">
import type { MSIDisplay } from '~/types/images'

const props = defineProps<{
  display: MSIDisplay
  loading?: boolean
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
const { presets, savePreset, deletePreset } = useMsiDisplayPresets()
const namingPreset = ref(false)
const presetName = ref('')
const presetError = ref('')
const validPresetName = computed(() => Boolean(presetName.value.trim()))

const normalizationOptions = [
  { label: 'None', value: 'none' },
  { label: 'TIC', value: 'tic' },
  { label: 'RMS', value: 'rms' },
  { label: 'Median', value: 'median' },
  { label: 'Max', value: 'max' },
]

const availableNormalizationOptions = computed(() => normalizationOptions.map(option => ({
  ...option,
  disabled: draft.cubing.method === 'embed' && option.value === 'none',
})))

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
  disabled: draft.cubing.method !== 'bin' && ['tic', 'nmf'].includes(option.value),
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

const availableScalingOptions = computed(() => scalingOptions.map(option => ({
  ...option,
  disabled: draft.reduction.method === 'nmf' && option.value !== 'minmax',
})))

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

const popoverUi = {
  content: 'z-[1000]',
}

const selectUi = {
  content: 'z-[1100]',
}

const colormapPopoverUi = {
  content: 'z-[1100]',
}

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
  () => [draft.cubing.method, draft.preprocessing.normalization, draft.reduction.method],
  () => {
    if (draft.cubing.method === 'embed' && draft.preprocessing.normalization === 'none') {
      draft.preprocessing.normalization = 'tic'
    }
    if (draft.cubing.method !== 'bin' && ['tic', 'nmf'].includes(draft.reduction.method)) {
      draft.reduction.method = 'pca'
    }
    if (draft.reduction.method === 'tic') {
      draft.reduction.components = 1
    } else if (draft.reduction.components < 3) {
      draft.reduction.components = 3
    }
    if (draft.reduction.method === 'nmf') {
      draft.reduction.scaling = 'minmax'
    }
  },
  { immediate: true },
)

function apply() {
  emit('apply', cloneDisplay(draft))
}

function setDraft(display: MSIDisplay) {
  const next = cloneDisplay(display)
  draft.preprocessing = next.preprocessing
  draft.cubing = next.cubing
  draft.reduction = next.reduction
}

function beginPreset() {
  presetName.value = ''
  presetError.value = ''
  namingPreset.value = true
}

function cancelPreset() {
  presetName.value = ''
  presetError.value = ''
  namingPreset.value = false
}

function saveCurrentPreset() {
  if (!validPresetName.value) return
  if (!savePreset(presetName.value, cloneDisplay(draft))) {
    presetError.value = 'Unable to save presets in this browser.'
    return
  }
  cancelPreset()
}

function applyPreset(display: MSIDisplay) {
  setDraft(display)
  apply()
}

function removePreset(id: string) {
  if (!deletePreset(id)) {
    presetError.value = 'Unable to update presets in this browser.'
  }
}
</script>

<template>
  <UPopover :ui="popoverUi">
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
          <UButton label="Apply" color="secondary" variant="soft" size="sm" :loading="loading" :disabled="loading" @click="apply" />
        </div>
        <div class="space-y-3">
          <section class="space-y-2">
            <div class="flex items-center justify-between gap-2 text-xs font-medium uppercase text-muted">
              <span class="flex items-center gap-2">
                <UIcon name="i-lucide-bookmark" class="size-3.5" />
                Presets
              </span>
              <UButton label="Save" icon="i-lucide-bookmark-plus" color="neutral" variant="ghost" size="xs" :disabled="namingPreset" @click="beginPreset" />
            </div>
            <div v-if="namingPreset" class="flex items-start gap-1.5">
              <UFormField :error="presetError || undefined" class="min-w-0 flex-1">
                <UInput v-model="presetName" autofocus maxlength="64" placeholder="Preset name" size="sm" class="w-full" @keyup.enter="saveCurrentPreset" @keyup.esc="cancelPreset" />
              </UFormField>
              <UTooltip text="Save preset">
                <UButton aria-label="Save preset" icon="i-lucide-save" color="secondary" variant="soft" size="sm" square :disabled="!validPresetName" @click="saveCurrentPreset" />
              </UTooltip>
              <UTooltip text="Cancel">
                <UButton aria-label="Cancel preset" icon="i-lucide-x" color="neutral" variant="ghost" size="sm" square @click="cancelPreset" />
              </UTooltip>
            </div>
            <div v-if="presets.length" class="flex max-h-32 flex-wrap gap-1 overflow-y-auto pr-1">
              <div v-for="preset in presets" :key="preset.id" class="inline-flex min-w-0 max-w-full overflow-hidden rounded-md bg-elevated">
                <UButton :label="preset.name" icon="i-lucide-bookmark" color="neutral" variant="ghost" size="xs" class="min-w-0 max-w-48 justify-start rounded-none hover:bg-primary/15 hover:text-primary" :disabled="loading" @click="applyPreset(preset.display)" />
                <UTooltip :text="`Delete ${preset.name}`">
                  <UButton :aria-label="`Delete ${preset.name}`" icon="i-lucide-x" color="neutral" variant="ghost" size="xs" square class="rounded-none" @click="removePreset(preset.id)" />
                </UTooltip>
              </div>
            </div>
            <p v-if="presetError && !namingPreset" class="text-xs text-error">
              {{ presetError }}
            </p>
          </section>
          <section class="space-y-2">
            <div class="flex items-center gap-2 text-xs font-medium uppercase text-muted">
              <UIcon name="i-lucide-sliders-horizontal" class="size-3.5" />
              Preprocessing
            </div>
            <div class="grid grid-cols-1 gap-2">
              <UFormField label="Normalization" size="sm">
                <USelect v-model="draft.preprocessing.normalization" :items="availableNormalizationOptions" :ui="selectUi" class="w-full" />
              </UFormField>
            </div>
          </section>
          <section class="space-y-2">
            <div class="flex items-center gap-2 text-xs font-medium uppercase text-muted">
              <UIcon name="i-lucide-grid-3x3" class="size-3.5" />
              Grid Formation
            </div>
            <div class="grid grid-cols-2 gap-2">
              <UFormField label="Method" size="sm">
                <USelect v-model="draft.cubing.method" :items="cubingOptions" :ui="selectUi" class="w-full" />
              </UFormField>
              <UFormField v-if="draft.cubing.method === 'embed'" label="Model" size="sm">
                <USelect v-model="draft.cubing.model" :items="embeddingModelOptions" :ui="selectUi" class="w-full" />
              </UFormField>
              <UFormField v-else label="Bin width" size="sm">
                <UInput v-model.number="draft.cubing.binWidth" type="number" min="0.001" step="0.1" class="w-full font-data" />
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
                <USelect v-model="draft.reduction.method" :items="availableReductionOptions" :ui="selectUi" class="w-full" />
              </UFormField>
              <UFormField label="Scaling" size="sm">
                <USelect v-model="draft.reduction.scaling" :items="availableScalingOptions" :ui="selectUi" class="w-full" :disabled="draft.reduction.method === 'tic'" />
              </UFormField>
              <UFormField v-if="usesColormap" label="Colormap" size="sm">
                <UPopover :ui="colormapPopoverUi">
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
