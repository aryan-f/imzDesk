<script setup lang="ts">
import type { DatasetFile, DatasetKind, DatasetManifest, DatasetSample } from '~/types/datasets'
import type { FileType } from '~/types/filesystem'
import type { WorkspaceSettings } from '~/types/images'

type DatasetFilterField = 'filename' | 'dirpath' | 'tags' | 'annotations'
type TextFilterOperator = 'contains' | 'not_contains' | 'starts_with' | 'not_starts_with' | 'ends_with' | 'not_ends_with' | 'is_exactly' | 'is_not_exactly'
type PresenceFilterOperator = 'has' | 'has_not'
type DatasetFilterOperator = TextFilterOperator | PresenceFilterOperator

interface DatasetFilter {
  id: string
  enabled: boolean
  field: DatasetFilterField
  operator: DatasetFilterOperator
  value: string
}

const route = useRoute()
const activity = useActivity()
const { fileIcon, fileIconColorClass } = useFileIcon()
const { tagColorStyle } = useTagColors()
const endpoint = '/api/datasets/manifest'
const filesEndpoint = '/api/datasets/files'
const workspaceSettingsEndpoint = '/api/workspace/settings'
const fileDragType = 'application/x-imzdesk-dataset-files'
const splitDragType = 'application/x-imzdesk-dataset-split'
const datasetId = computed(() => String(route.params.id))
const dataset = ref<DatasetManifest | null>(null)
const selectedPaths = ref(new Set<string>())
const selectedSampleKeys = ref(new Set<string>())
const filters = ref<DatasetFilter[]>([])
const newSplit = ref('')
const addingSplit = ref(false)
const deletingSplit = ref<string | null>(null)
const draggedSplit = ref<string | null>(null)
const splitOrderChanged = ref(false)
const saving = ref(false)
const datasetUrl = computed(() => `${endpoint}/${datasetId.value}`)
const { data: loadedDataset } = useFetch<DatasetManifest | null>(datasetUrl, { default: () => null, lazy: true })
const { data: files, status: filesStatus } = useFetch<DatasetFile[]>(filesEndpoint, { default: () => [], lazy: true })
const { data: workspaceSettings } = useFetch<WorkspaceSettings>(workspaceSettingsEndpoint, { default: () => ({ labels: [] }), lazy: true })

watch(loadedDataset, (value) => {
  dataset.value = value ? structuredClone(value) : null
}, { immediate: true })

const fieldOptions: Array<{ label: string, value: DatasetFilterField }> = [
  { label: 'Filename', value: 'filename' },
  { label: 'Directory', value: 'dirpath' },
  { label: 'Tags', value: 'tags' },
  { label: 'Annotations', value: 'annotations' },
]
const textOperatorOptions: Array<{ label: string, value: TextFilterOperator }> = [
  { label: 'Contains', value: 'contains' },
  { label: 'Does not contain', value: 'not_contains' },
  { label: 'Starts with', value: 'starts_with' },
  { label: 'Does not start with', value: 'not_starts_with' },
  { label: 'Ends with', value: 'ends_with' },
  { label: 'Does not end with', value: 'not_ends_with' },
  { label: 'Is exactly', value: 'is_exactly' },
  { label: 'Is not exactly', value: 'is_not_exactly' },
]
const presenceOperatorOptions: Array<{ label: string, value: PresenceFilterOperator }> = [
  { label: 'Has', value: 'has' },
  { label: 'Has not', value: 'has_not' },
]

const splitNames = computed(() => Object.keys(dataset.value?.splits ?? {}))
const filesLoading = computed(() => filesStatus.value === 'pending')
const validDatasetName = computed(() => Boolean(dataset.value?.name.trim()))
const selectedFiles = computed(() => [...selectedPaths.value].map(path => fileByPath(path)).filter((file): file is DatasetFile => Boolean(file)))
const selectedWsiFiles = computed(() => selectedFiles.value.filter(file => file.type === 'WSI'))
const selectedMsiFiles = computed(() => selectedFiles.value.filter(file => file.type === 'MSI'))
const hasSelection = computed(() => selectedPaths.value.size > 0)
const canAddSelection = computed(() => {
  if (dataset.value?.kind === 'paired') return selectedWsiFiles.value.length === 1 && selectedMsiFiles.value.length === 1
  return selectedFiles.value.length > 0
})
const validSplitName = computed(() => {
  const name = splitName(newSplit.value)
  return Boolean(name && !dataset.value?.splits[name])
})
const usedPaths = computed(() => {
  const paths = new Set<string>()
  for (const samples of Object.values(dataset.value?.splits ?? {})) {
    for (const sample of samples) {
      if (sample.wsi) paths.add(sample.wsi)
      if (sample.msi) paths.add(sample.msi)
    }
  }
  return paths
})
const rawAvailableFiles = computed(() => {
  return (files.value ?? [])
    .filter(file => file.type && allowedFileTypes(dataset.value?.kind).includes(file.type))
    .filter(file => !usedPaths.value.has(file.path))
})
const activeFilters = computed(() => filters.value.filter(filter => filter.enabled && filter.value.trim()))
const availableFiles = computed(() => rawAvailableFiles.value.filter(file => activeFilters.value.every(filter => matchesDatasetFilter(file, filter))))
const tagFilterOptions = computed(() => [...new Set((files.value ?? []).flatMap(file => file.tags))].sort())
const labelFilterOptions = computed(() => workspaceSettings.value.labels.map(label => ({ label: label.name, value: label.id })))
const allAvailableSelected = computed(() => availableFiles.value.length > 0 && availableFiles.value.every(file => selectedPaths.value.has(file.path)))
const selectAllAvailableChecked = computed({
  get: () => allAvailableSelected.value,
  set: (checked: boolean | 'indeterminate') => {
    if (checked === true) selectAllAvailable()
    else deselectAllAvailable()
  },
})

function allowedFileTypes(kind?: DatasetKind) {
  if (kind === 'wsi') return ['WSI'] as FileType[]
  if (kind === 'msi') return ['MSI'] as FileType[]
  return ['WSI', 'MSI'] as FileType[]
}

function fileByPath(path?: string) {
  return (files.value ?? []).find(file => file.path === path)
}

function sampleFiles(sample: DatasetSample) {
  return [fileByPath(sample.wsi), fileByPath(sample.msi)].filter((file): file is DatasetFile => Boolean(file))
}

function splitSamples(split: string) {
  return dataset.value?.splits[split] ?? []
}

function sampleKey(split: string, sample: DatasetSample) {
  return `${split}:${sample.id}`
}

function parentPath(file: DatasetFile) {
  return file.parent === '.' ? '' : file.parent
}

function selectAvailable(file: DatasetFile) {
  const selected = new Set(selectedPaths.value)
  if (selected.has(file.path)) selected.delete(file.path)
  else selected.add(file.path)
  selectedPaths.value = selected
}

function isSelected(file: DatasetFile) {
  return selectedPaths.value.has(file.path)
}

function selectAllAvailable() {
  const selected = new Set(selectedPaths.value)
  for (const file of availableFiles.value) selected.add(file.path)
  selectedPaths.value = selected
}

function deselectAllAvailable() {
  const selected = new Set(selectedPaths.value)
  for (const file of availableFiles.value) selected.delete(file.path)
  selectedPaths.value = selected
}

function addFilter(field: DatasetFilterField = 'filename') {
  filters.value.push({
    id: crypto.randomUUID(),
    enabled: true,
    field,
    operator: defaultFilterOperator(field),
    value: '',
  })
}

function removeFilter(filter: DatasetFilter) {
  filters.value = filters.value.filter(value => value !== filter)
}

function setFilterField(filter: DatasetFilter, field: DatasetFilterField) {
  filter.field = field
  filter.operator = defaultFilterOperator(field)
  filter.value = ''
}

function defaultFilterOperator(field: DatasetFilterField): DatasetFilterOperator {
  return field === 'filename' || field === 'dirpath' ? 'contains' : 'has'
}

function operatorOptions(filter: DatasetFilter) {
  return filter.field === 'filename' || filter.field === 'dirpath' ? textOperatorOptions : presenceOperatorOptions
}

function matchesDatasetFilter(file: DatasetFile, filter: DatasetFilter) {
  const value = filter.value.trim().toLowerCase()
  if (!value) return true
  if (filter.field === 'filename') return matchesTextFilter(file.name.toLowerCase(), filter.operator as TextFilterOperator, value)
  if (filter.field === 'dirpath') return matchesTextFilter(parentPath(file).toLowerCase(), filter.operator as TextFilterOperator, value)
  if (filter.field === 'tags') {
    const hasTag = file.tags.some(tag => tag.toLowerCase() === value)
    return filter.operator === 'has' ? hasTag : !hasTag
  }
  const hasAnnotation = file.annotation_labels.some(label => label.id === filter.value)
  return filter.operator === 'has' ? hasAnnotation : !hasAnnotation
}

function matchesTextFilter(source: string, operator: TextFilterOperator, value: string) {
  if (operator === 'contains') return source.includes(value)
  if (operator === 'not_contains') return !source.includes(value)
  if (operator === 'starts_with') return source.startsWith(value)
  if (operator === 'not_starts_with') return !source.startsWith(value)
  if (operator === 'ends_with') return source.endsWith(value)
  if (operator === 'not_ends_with') return !source.endsWith(value)
  if (operator === 'is_exactly') return source === value
  return source !== value
}

function isSampleSelected(split: string, sample: DatasetSample) {
  return selectedSampleKeys.value.has(sampleKey(split, sample))
}

function selectSample(split: string, sample: DatasetSample) {
  const selected = new Set(selectedSampleKeys.value)
  const key = sampleKey(split, sample)
  if (selected.has(key)) selected.delete(key)
  else selected.add(key)
  selectedSampleKeys.value = selected
}

function allSplitSamplesSelected(split: string) {
  const samples = splitSamples(split)
  return samples.length > 0 && samples.every(sample => selectedSampleKeys.value.has(sampleKey(split, sample)))
}

function hasSplitSampleSelection(split: string) {
  return splitSamples(split).some(sample => selectedSampleKeys.value.has(sampleKey(split, sample)))
}

function toggleSelectAllSplit(split: string, checked: boolean | 'indeterminate') {
  const selected = new Set(selectedSampleKeys.value)
  for (const sample of splitSamples(split)) {
    const key = sampleKey(split, sample)
    if (checked === true) selected.add(key)
    else selected.delete(key)
  }
  selectedSampleKeys.value = selected
}

function sampleId(sample: Partial<DatasetSample>) {
  const source = `${sample.wsi ?? ''}_${sample.msi ?? ''}`
  return source.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '').slice(0, 80) || crypto.randomUUID()
}

function dragAvailable(event: DragEvent, file: DatasetFile) {
  const paths = selectedPaths.value.has(file.path) ? [...selectedPaths.value] : [file.path]
  event.dataTransfer?.setData(fileDragType, JSON.stringify(paths))
}

function selectedSampleFiles(paths?: string[]) {
  if (paths) return paths.map(path => fileByPath(path)).filter((file): file is DatasetFile => Boolean(file))
  return selectedFiles.value
}

async function addToSplit(split: string, paths?: string[]) {
  if (!dataset.value) return
  const samples = dataset.value.splits[split]
  if (!samples) return
  const selected = selectedSampleFiles(paths)
  if (dataset.value.kind === 'paired') {
    const wsi = selected.filter(file => file.type === 'WSI')
    const msi = selected.filter(file => file.type === 'MSI')
    if (wsi.length !== 1 || msi.length !== 1) return
    const sample = { id: sampleId({ wsi: wsi[0]!.path, msi: msi[0]!.path }), wsi: wsi[0]!.path, msi: msi[0]!.path }
    samples.push(sample)
    clearSelectedPaths(selected.map(file => file.path))
    await persistDataset()
    return
  }
  for (const file of selected) {
    const sample = dataset.value.kind === 'wsi'
      ? { id: sampleId({ wsi: file.path }), wsi: file.path }
      : { id: sampleId({ msi: file.path }), msi: file.path }
    samples.push(sample)
  }
  clearSelectedPaths(selected.map(file => file.path))
  await persistDataset()
}

function clearSelectedPaths(paths: string[]) {
  const selected = new Set(selectedPaths.value)
  for (const path of paths) selected.delete(path)
  selectedPaths.value = selected
}

function dropOnSplit(event: DragEvent, split: string) {
  const splitPayload = event.dataTransfer?.getData(splitDragType)
  if (splitPayload) {
    draggedSplit.value = null
    return
  }
  const payload = event.dataTransfer?.getData(fileDragType)
  if (!payload) return
  const paths = JSON.parse(payload)
  if (Array.isArray(paths)) addToSplit(split, paths)
}

async function dropSample(split: string, sample: DatasetSample) {
  if (!dataset.value) return
  const samples = dataset.value.splits[split]
  if (!samples) return
  dataset.value.splits[split] = samples.filter(value => value !== sample)
  const selected = new Set(selectedSampleKeys.value)
  selected.delete(sampleKey(split, sample))
  selectedSampleKeys.value = selected
  await persistDataset()
}

async function dropSelectedSamples(split: string) {
  if (!dataset.value) return
  const samples = dataset.value.splits[split]
  if (!samples) return
  dataset.value.splits[split] = samples.filter(sample => !selectedSampleKeys.value.has(sampleKey(split, sample)))
  const selected = new Set(selectedSampleKeys.value)
  for (const sample of samples) selected.delete(sampleKey(split, sample))
  selectedSampleKeys.value = selected
  await persistDataset()
}

function beginSplitDrag(event: DragEvent, split: string) {
  draggedSplit.value = split
  event.dataTransfer?.setData(splitDragType, split)
  if (event.dataTransfer) event.dataTransfer.effectAllowed = 'move'
}

function dragOverSplit(event: DragEvent, split: string) {
  if (!draggedSplit.value || draggedSplit.value === split) return
  const rect = (event.currentTarget as HTMLElement).getBoundingClientRect()
  moveSplitPane(split, event.clientX > rect.left + rect.width / 2)
}

function moveSplitPane(split: string, after: boolean) {
  if (!dataset.value || !draggedSplit.value || draggedSplit.value === split) return
  const entries = Object.entries(dataset.value.splits)
  const from = entries.findIndex(([name]) => name === draggedSplit.value)
  const to = entries.findIndex(([name]) => name === split)
  if (from < 0 || to < 0) return
  const [entry] = entries.splice(from, 1)
  if (!entry) return
  const target = entries.findIndex(([name]) => name === split)
  entries.splice(target + (after ? 1 : 0), 0, entry)
  dataset.value.splits = Object.fromEntries(entries)
  splitOrderChanged.value = true
}

async function addSplit() {
  if (!dataset.value) return
  const name = splitName(newSplit.value)
  if (!name || dataset.value.splits[name]) return
  dataset.value.splits[name] = []
  newSplit.value = ''
  addingSplit.value = false
  await persistDataset()
}

function splitName(value: string) {
  return value.trim().toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '')
}

async function deleteSplit() {
  if (!dataset.value || !deletingSplit.value) return
  const split = deletingSplit.value
  dataset.value.splits = Object.fromEntries(
    Object.entries(dataset.value.splits).filter(([name]) => name !== split),
  )
  const selected = new Set(selectedSampleKeys.value)
  for (const key of selected) {
    if (key.startsWith(`${split}:`)) selected.delete(key)
  }
  selectedSampleKeys.value = selected
  deletingSplit.value = null
  await persistDataset()
}

async function endSplitDrag() {
  draggedSplit.value = null
  if (!splitOrderChanged.value) return
  splitOrderChanged.value = false
  await persistDataset()
}

async function persistDataset() {
  if (!dataset.value) return
  saving.value = true
  const task = activity.startTask('Saving dataset')
  try {
    loadedDataset.value = await $fetch<DatasetManifest>(endpoint, {
      method: 'POST',
      body: dataset.value,
    })
  } finally {
    activity.endTask(task)
    saving.value = false
  }
}

async function saveDataset() {
  if (!dataset.value) return
  const name = dataset.value.name.trim()
  if (!name) return
  dataset.value.name = name
  await persistDataset()
}
</script>

<template>
  <div class="min-h-0 flex-1 overflow-hidden bg-default">
    <main v-if="dataset" class="flex h-full min-h-0 flex-col gap-4 p-4">
      <section class="flex items-center gap-3">
        <UButton icon="i-lucide-arrow-left" color="neutral" variant="ghost" size="sm" square to="/datasets" />
        <UBadge :label="dataset.kind === 'paired' ? 'WSI-MSI' : dataset.kind.toUpperCase()" color="neutral" variant="soft" size="sm" />
        <label class="text-sm font-semibold text-muted" for="dataset-name">
          Dataset Name:
        </label>
        <UInput id="dataset-name" v-model="dataset.name" size="sm" class="w-80" :color="validDatasetName ? 'neutral' : 'error'" @keyup.enter="saveDataset" />
        <UButton label="Save" icon="i-lucide-check" color="primary" size="sm" :loading="saving" :disabled="saving || !validDatasetName" @click="saveDataset" />
      </section>
      <section class="grid min-h-0 flex-1 gap-4 lg:grid-cols-[24rem_1fr]">
        <aside class="flex min-h-0 flex-col rounded-lg border border-default bg-muted">
          <div class="flex h-12 items-center gap-2 border-b border-default px-3">
            <h2 class="text-sm font-semibold text-muted">
              Available
            </h2>
            <UBadge :label="String(availableFiles.length)" color="neutral" variant="soft" size="sm" />
            <UIcon v-if="filesLoading" name="i-lucide-loader-circle" class="size-4 animate-spin text-muted" />
            <div class="ms-auto" />
            <UCheckbox
              v-model="selectAllAvailableChecked"
              label="Select All"
              size="sm"
              :disabled="!availableFiles.length"
              :ui="{ root: 'items-center', wrapper: 'w-auto ms-1.5', label: 'leading-4' }"
            />
            <UPopover>
              <UButton icon="i-lucide-filter" color="neutral" variant="ghost" size="sm" square />
              <template #content>
                <div class="w-[42rem] space-y-3 p-3">
                  <div class="flex items-center justify-between">
                    <div class="text-sm font-semibold text-default">
                      Filters
                    </div>
                    <UButton label="Add Filter" icon="i-lucide-plus" color="neutral" variant="soft" size="sm" @click="addFilter()" />
                  </div>
                  <div v-if="filters.length" class="space-y-2">
                    <div v-for="filter in filters" :key="filter.id" class="grid grid-cols-[auto_8rem_10rem_1fr_auto] items-center gap-2">
                      <UCheckbox v-model="filter.enabled" size="sm" :ui="{ root: 'items-center' }" />
                      <USelect
                        :model-value="filter.field"
                        :items="fieldOptions"
                        size="sm"
                        @update:model-value="setFilterField(filter, $event as DatasetFilterField)"
                      />
                      <USelect v-model="filter.operator" :items="operatorOptions(filter)" size="sm" />
                      <UInput v-if="filter.field === 'filename' || filter.field === 'dirpath'" v-model="filter.value" size="sm" placeholder="Value" />
                      <UInputMenu v-else-if="filter.field === 'tags'" v-model="filter.value" :items="tagFilterOptions" mode="autocomplete" create-item="always" size="sm" placeholder="Tag" />
                      <USelectMenu v-else v-model="filter.value" :items="labelFilterOptions" value-key="value" size="sm" placeholder="Annotation label" />
                      <UButton icon="i-lucide-trash-2" color="neutral" variant="ghost" size="sm" square @click="removeFilter(filter)" />
                    </div>
                  </div>
                  <div v-else class="py-2 text-sm text-muted">
                    No filters.
                  </div>
                </div>
              </template>
            </UPopover>
          </div>
          <div class="min-h-0 flex-1 overflow-y-auto p-2">
            <button
              v-for="file in availableFiles"
              :key="file.path"
              draggable="true"
              class="mb-1 flex w-full items-start gap-2 rounded-md px-2 py-2 text-left hover:bg-elevated"
              :class="isSelected(file) ? 'bg-elevated' : ''"
              @click="selectAvailable(file)"
              @dragstart="dragAvailable($event, file)"
            >
              <span class="mt-0.5 flex size-4 shrink-0 items-center justify-center rounded border border-default" :class="isSelected(file) ? 'bg-info text-inverted border-info' : 'bg-default text-transparent'">
                <UIcon name="i-lucide-check" class="size-3" />
              </span>
              <UIcon :name="fileIcon(file)" :class="[fileIconColorClass(file), 'mt-0.5 size-4 shrink-0']" />
              <span class="min-w-0 flex-1">
                <span class="block truncate font-data text-xs text-dimmed">{{ parentPath(file) }}</span>
                <span class="block truncate font-data text-sm text-default">{{ file.name }}</span>
                <span class="mt-1 flex min-h-5 min-w-0 items-center gap-1 overflow-hidden whitespace-nowrap">
                  <template v-if="file.tags.length">
                    <UBadge v-for="tag in file.tags" :key="tag" :label="tag" color="neutral" variant="soft" size="sm" class="max-w-24 shrink-0 px-1.5 py-0.75" :style="tagColorStyle(tag)" />
                  </template>
                  <span v-else class="text-xs leading-5 text-dimmed">
                    No tags.
                  </span>
                </span>
                <span class="mt-0.5 flex min-h-5 min-w-0 items-center gap-1 overflow-hidden whitespace-nowrap">
                  <template v-if="file.annotation_labels.length">
                    <UBadge v-for="label in file.annotation_labels" :key="label.id" :label="`${label.name} (${label.count})`" color="neutral" variant="soft" size="sm" class="max-w-24 shrink-0 px-1.5 py-0.75" :style="{ backgroundColor: `${label.color}22`, borderColor: `${label.color}66`, color: label.color }" />
                  </template>
                  <span v-else class="text-xs leading-5 text-dimmed">
                    No annotations.
                  </span>
                </span>
              </span>
            </button>
          </div>
        </aside>
        <div class="-mx-3 -my-3 min-w-0 overflow-x-auto overflow-y-visible px-3 py-3">
          <TransitionGroup name="split-pane" tag="div" class="flex h-full min-w-max gap-4">
            <section
              v-for="split in splitNames"
              :key="split"
              class="flex w-80 shrink-0 flex-col rounded-lg border border-default bg-muted"
              :class="draggedSplit === split ? 'split-pane-dragging' : 'split-pane-idle'"
              @dragover.prevent="dragOverSplit($event, split)"
              @drop.prevent="dropOnSplit($event, split)"
            >
              <div class="flex min-h-12 flex-wrap items-center gap-2 border-b border-default px-3 py-2">
                <div
                  class="flex min-w-0  cursor-grab items-center gap-1.5 active:cursor-grabbing"
                  draggable="true"
                  @dragstart="beginSplitDrag($event, split)"
                  @dragend="endSplitDrag"
                >
                  <UIcon name="i-lucide-grip-vertical" class="size-4 shrink-0 text-dimmed" />
                  <h2 class="min-w-0 truncate font-data text-sm font-semibold text-muted">
                    {{ split }}
                  </h2>
                </div>
                <div class="flex-1 flex items-center">
                  <UBadge :label="String(splitSamples(split).length)" color="neutral" variant="soft" size="sm" />
                </div>
                <UCheckbox
                  :model-value="allSplitSamplesSelected(split)"
                  label="Select All"
                  size="sm"
                  :disabled="!splitSamples(split).length"
                  :ui="{ root: 'items-center', wrapper: 'w-auto ms-1.5' }"
                  @update:model-value="toggleSelectAllSplit(split, $event)"
                />
                <UButton v-if="hasSelection" icon="i-lucide-plus" color="neutral" variant="soft" size="sm" square :disabled="!canAddSelection" @click="addToSplit(split)" />
                <UTooltip v-if="hasSplitSampleSelection(split)" text="Drop selected samples">
                  <UButton icon="i-lucide-circle-minus" color="neutral" variant="soft" size="sm" square @click="dropSelectedSamples(split)" />
                </UTooltip>
                <UButton icon="i-lucide-trash-2" color="neutral" variant="ghost" size="sm" square @click="deletingSplit = split" />
              </div>
              <div class="min-h-0 flex-1 overflow-y-auto p-2">
                <div v-for="sample in splitSamples(split)" :key="sample.id" class="mb-2 rounded-md border border-default bg-default p-2">
                  <div class="flex items-start gap-2">
                    <UButton color="neutral" variant="ghost" size="xs" square class="mt-0.5 size-4 shrink-0 rounded border border-default p-0" :class="isSampleSelected(split, sample) ? 'bg-info text-inverted border-info hover:bg-info' : 'bg-default text-transparent'" @click="selectSample(split, sample)">
                      <UIcon name="i-lucide-check" class="size-3" />
                    </UButton>
                    <div class="min-w-0 flex-1">
                      <template v-for="file in sampleFiles(sample)" :key="file.path">
                        <div class="mb-1 flex min-w-0 gap-2">
                          <UIcon :name="fileIcon(file)" :class="[fileIconColorClass(file), 'mt-0.5 size-4 shrink-0']" />
                          <span class="min-w-0">
                            <span class="block truncate font-data text-sm text-default">{{ file.name }}</span>
                            <span class="block truncate font-data text-xs text-dimmed">{{ parentPath(file) }}</span>
                          </span>
                        </div>
                      </template>
                    </div>
                    <UTooltip text="Drop sample">
                      <UButton icon="i-lucide-circle-minus" color="neutral" variant="ghost" size="xs" square @click="dropSample(split, sample)" />
                    </UTooltip>
                  </div>
                </div>
              </div>
            </section>
            <UButton
              key="add-split"
              color="neutral"
              variant="soft"
              class="flex w-48 shrink-0 items-center justify-center rounded-lg border border-dashed border-default"
              @click="addingSplit = true"
            >
              <template #leading>
                <UIcon name="i-lucide-plus" class="size-4" />
              </template>
              <span class="text-sm font-semibold">
                Add Split
              </span>
            </UButton>
          </TransitionGroup>
        </div>
      </section>
    </main>
    <div v-else class="p-6 text-sm text-muted">
      Dataset not found.
    </div>
    <UModal :open="addingSplit" @update:open="value => { addingSplit = value }">
      <template #content>
        <div class="space-y-4 p-4">
          <div>
            <h2 class="text-base font-semibold text-default">
              Add Split
            </h2>
            <p class="mt-1 text-sm text-muted">
              Choose a name for the new split.
            </p>
          </div>
          <UInput v-model="newSplit" autofocus placeholder="Split name" :color="validSplitName || !newSplit ? 'neutral' : 'error'" @keyup.enter="addSplit" />
          <div class="flex justify-end gap-2">
            <UButton label="Cancel" color="neutral" variant="ghost" @click="addingSplit = false; newSplit = ''" />
            <UButton label="Add Split" icon="i-lucide-plus" color="primary" :disabled="!validSplitName" @click="addSplit" />
          </div>
        </div>
      </template>
    </UModal>
    <UModal :open="Boolean(deletingSplit)" @update:open="value => { if (!value) deletingSplit = null }">
      <template #content>
        <div class="space-y-4 p-4">
          <div>
            <h2 class="text-base font-semibold text-default">
              Delete Split
            </h2>
            <p class="mt-1 text-sm text-muted">
              Are you sure you want to delete "{{ deletingSplit }}"? Assigned files will return to Available. This action cannot be undone.
            </p>
          </div>
          <div class="flex justify-end gap-2">
            <UButton label="Cancel" color="neutral" variant="ghost" @click="deletingSplit = null" />
            <UButton label="Yes, I'm sure" icon="i-lucide-trash-2" color="error" @click="deleteSplit" />
          </div>
        </div>
      </template>
    </UModal>
  </div>
</template>

<style scoped>
.split-pane-idle,
.split-pane-dragging {
  transition:
    transform 220ms cubic-bezier(0.2, 0.9, 0.25, 1.15),
    box-shadow 160ms ease,
    opacity 160ms ease;
  will-change: transform;
}

.split-pane-move {
  transition: transform 220ms cubic-bezier(0.2, 0.9, 0.25, 1.15);
}

.split-pane-dragging {
  box-shadow: 0 12px 28px rgb(0 0 0 / 0.22);
  opacity: 0.92;
  transform: scale(1.015);
  z-index: 10;
}
</style>
