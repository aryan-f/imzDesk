<script setup lang="ts">
import type { DatasetPaneItem } from '~/components/datasets/Pane.vue'
import type { DatasetFile, DatasetKind, DatasetManifest, DatasetPair, DatasetSample } from '~/types/datasets'
import type { FileType } from '~/types/filesystem'
import type { WorkspaceSettings } from '~/types/images'

const route = useRoute()
const router = useRouter()
const activity = useActivity()
const { openDirectoryWithFiles } = useWorkspace()
const endpoint = '/api/datasets/manifest'
const filesEndpoint = '/api/datasets/files'
const workspaceSettingsEndpoint = '/api/workspace/settings'
const splitDragType = 'application/x-imzdesk-dataset-split'
const datasetId = computed(() => String(route.params.id))
const dataset = ref<DatasetManifest | null>(null)
const selectedPaths = ref(new Set<string>())
const selectedSampleKeys = ref(new Set<string>())
const newSplit = ref('')
const addingSplit = ref(false)
const deletingSplit = ref<string | null>(null)
const draggedSplit = ref<string | null>(null)
const splitOrderChanged = ref(false)
const saving = ref(false)
const reloading = ref(false)
const datasetUrl = computed(() => `${endpoint}/${datasetId.value}`)
const { data: loadedDataset, refresh: refreshDataset } = useFetch<DatasetManifest | null>(datasetUrl, { default: () => null, lazy: true })
const { data: files, status: filesStatus, refresh: refreshFiles } = useFetch<DatasetFile[]>(filesEndpoint, { default: () => [], lazy: true })
const { data: workspaceSettings, refresh: refreshWorkspaceSettings } = useFetch<WorkspaceSettings>(workspaceSettingsEndpoint, { default: () => ({ labels: [] }), lazy: true })

watch(loadedDataset, (value) => {
  dataset.value = value ? structuredClone(value) : null
}, { immediate: true })

const splitNames = computed(() => Object.keys(dataset.value?.splits ?? {}))
const filesLoading = computed(() => filesStatus.value === 'pending')
const validDatasetName = computed(() => Boolean(dataset.value?.name.trim()))
const paneItemHeight = computed(() => dataset.value?.kind === 'paired' ? 186 : 93)
const selectedFiles = computed(() => [...selectedPaths.value].map(path => fileByPath(path)).filter((file): file is DatasetFile => Boolean(file)))
const selectedPairs = computed(() => [...selectedPaths.value].map(id => pairById(id)).filter((pair): pair is DatasetPair => Boolean(pair)))
const hasSelection = computed(() => selectedPaths.value.size > 0)
const canAddSelection = computed(() => {
  if (dataset.value?.kind === 'paired') return selectedPairs.value.length === 1
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
const registeredPairs = computed<DatasetPair[]>(() => {
  const wsiByPath = new Map((files.value ?? []).filter(file => file.type === 'WSI').map(file => [file.path, file]))
  return (files.value ?? [])
    .filter(file => file.type === 'MSI')
    .flatMap((msi) => {
      return (msi.registered_references ?? []).flatMap((reference) => {
        const wsi = wsiByPath.get(reference)
        if (!wsi) return []
        return [{ id: pairId(wsi.path, msi.path), wsi, msi }]
      })
    })
})
const availablePairs = computed(() => registeredPairs.value.filter(pair => !usedPaths.value.has(pair.wsi.path) && !usedPaths.value.has(pair.msi.path)))
const availableItems = computed<DatasetPaneItem[]>(() => {
  if (dataset.value?.kind === 'paired') return availablePairs.value.map(pair => ({ id: pair.id, files: [pair.wsi, pair.msi] }))
  return rawAvailableFiles.value.map(file => ({ id: file.path, files: [file] }))
})
const tagFilterOptions = computed(() => [...new Set((files.value ?? []).flatMap(file => file.tags))].sort())
const labelFilterOptions = computed(() => workspaceSettings.value.labels.map(label => ({ label: label.name, value: label.id })))

function allowedFileTypes(kind?: DatasetKind) {
  if (kind === 'wsi') return ['WSI'] as FileType[]
  if (kind === 'msi') return ['MSI'] as FileType[]
  return ['WSI', 'MSI'] as FileType[]
}

function fileByPath(path?: string) {
  return (files.value ?? []).find(file => file.path === path)
}

function pairId(wsi: string, msi: string) {
  return `${wsi}\n${msi}`
}

function pairById(id: string) {
  return registeredPairs.value.find(pair => pair.id === id)
}

function sampleFiles(sample: DatasetSample) {
  return [fileByPath(sample.wsi), fileByPath(sample.msi)].filter((file): file is DatasetFile => Boolean(file))
}

function splitItems(split: string): DatasetPaneItem[] {
  return splitSamples(split).map(sample => ({ id: sample.id, files: sampleFiles(sample) }))
}

function splitSamples(split: string) {
  return dataset.value?.splits[split] ?? []
}

function sampleKey(split: string, sample: DatasetSample) {
  return `${split}:${sample.id}`
}

function toggleAvailable(path: string) {
  const selected = new Set(selectedPaths.value)
  if (selected.has(path)) selected.delete(path)
  else selected.add(path)
  selectedPaths.value = selected
}

function selectAvailable(ids: string[]) {
  const selected = new Set(selectedPaths.value)
  for (const id of ids) selected.add(id)
  selectedPaths.value = selected
}

function deselectAvailable(ids: string[]) {
  const selected = new Set(selectedPaths.value)
  for (const id of ids) selected.delete(id)
  selectedPaths.value = selected
}

function isSampleSelected(split: string, sample: DatasetSample) {
  return selectedSampleKeys.value.has(sampleKey(split, sample))
}

function selectedSplitIds(split: string) {
  return splitSamples(split).filter(sample => isSampleSelected(split, sample)).map(sample => sample.id)
}

function toggleSample(split: string, id: string) {
  const sample = splitSamples(split).find(sample => sample.id === id)
  if (!sample) return
  const selected = new Set(selectedSampleKeys.value)
  const key = sampleKey(split, sample)
  if (selected.has(key)) selected.delete(key)
  else selected.add(key)
  selectedSampleKeys.value = selected
}

function hasSplitSampleSelection(split: string) {
  return splitSamples(split).some(sample => selectedSampleKeys.value.has(sampleKey(split, sample)))
}

function selectSplitItems(split: string, ids: string[]) {
  const selected = new Set(selectedSampleKeys.value)
  for (const sample of splitSamples(split)) {
    if (!ids.includes(sample.id)) continue
    const key = sampleKey(split, sample)
    selected.add(key)
  }
  selectedSampleKeys.value = selected
}

function deselectSplitItems(split: string, ids: string[]) {
  const selected = new Set(selectedSampleKeys.value)
  for (const sample of splitSamples(split)) {
    if (!ids.includes(sample.id)) continue
    selected.delete(sampleKey(split, sample))
  }
  selectedSampleKeys.value = selected
}

function sampleId(sample: Partial<DatasetSample>) {
  const source = `${sample.wsi ?? ''}_${sample.msi ?? ''}`
  return source.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '').slice(0, 80) || crypto.randomUUID()
}

function selectedSampleFiles() {
  return selectedFiles.value
}

async function addToSplit(split: string) {
  if (!dataset.value) return
  const samples = dataset.value.splits[split]
  if (!samples) return
  const selected = selectedSampleFiles()
  if (dataset.value.kind === 'paired') {
    const pair = selectedPairs.value[0]
    if (!pair) return
    const sample = { id: sampleId({ wsi: pair.wsi.path, msi: pair.msi.path }), wsi: pair.wsi.path, msi: pair.msi.path }
    samples.push(sample)
    clearSelectedPaths([pair.id])
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

async function openItem(item: DatasetPaneItem) {
  const wsi = item.files.find(file => file.type === 'WSI')
  const msi = item.files.find(file => file.type === 'MSI')
  const dirpath = item.files[0]?.parent === '.' ? '' : item.files[0]?.parent ?? ''
  if (wsi && msi) {
    openDirectoryWithFiles(dirpath, { WSI: wsi.path, MSI: msi.path }, 'WSI')
  } else if (wsi) {
    openDirectoryWithFiles(dirpath, { WSI: wsi.path }, 'WSI')
  } else if (msi) {
    openDirectoryWithFiles(dirpath, { MSI: msi.path }, 'MSI')
  }
  await router.push('/workspace')
}

async function openAvailableItem(id: string) {
  const item = availableItems.value.find(item => item.id === id)
  if (item) await openItem(item)
}

async function openSplitItem(split: string, id: string) {
  const item = splitItems(split).find(item => item.id === id)
  if (item) await openItem(item)
}

function clearSelectedPaths(paths: string[]) {
  const selected = new Set(selectedPaths.value)
  for (const path of paths) selected.delete(path)
  selectedPaths.value = selected
}

async function dropSample(split: string, id: string) {
  if (!dataset.value) return
  const samples = dataset.value.splits[split]
  if (!samples) return
  const sample = samples.find(sample => sample.id === id)
  if (!sample) return
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

async function reloadFromDisk() {
  reloading.value = true
  const task = activity.startTask('Reloading dataset')
  try {
    selectedPaths.value = new Set()
    selectedSampleKeys.value = new Set()
    await Promise.all([
      refreshDataset(),
      refreshFiles(),
      refreshWorkspaceSettings(),
    ])
  } finally {
    activity.endTask(task)
    reloading.value = false
  }
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
        <div class="ms-auto" />
        <UButton label="Reload From Disk" icon="i-lucide-refresh-cw" color="neutral" variant="soft" size="sm" :loading="reloading" @click="reloadFromDisk" />
      </section>
      <section class="grid min-h-0 flex-1 gap-4 lg:grid-cols-[24rem_1fr]">
        <DatasetsPane
          title="Available"
          :items="availableItems"
          :selected-ids="[...selectedPaths]"
          :item-height="paneItemHeight"
          :loading="filesLoading"
          :item-drop-visible="false"
          :tag-options="tagFilterOptions"
          :label-options="labelFilterOptions"
          @toggle-item="toggleAvailable"
          @select-items="selectAvailable"
          @deselect-items="deselectAvailable"
          @open-item="openAvailableItem"
        />
        <div class="-mx-3 -my-3 min-w-0 overflow-x-auto overflow-y-visible px-3 py-3">
          <TransitionGroup name="split-pane" tag="div" class="flex h-full min-w-max gap-4">
            <DatasetsPane
              v-for="split in splitNames"
              :key="split"
              class="w-80 shrink-0"
              :title="split"
              :items="splitItems(split)"
              :selected-ids="selectedSplitIds(split)"
              :item-height="paneItemHeight"
              :draggable-title="true"
              :add-visible="hasSelection"
              :add-disabled="!canAddSelection"
              :drop-selected-visible="hasSplitSampleSelection(split)"
              :delete-visible="true"
              :drag-class="draggedSplit === split ? 'split-pane-dragging' : 'split-pane-idle'"
              :tag-options="tagFilterOptions"
              :label-options="labelFilterOptions"
              @toggle-item="toggleSample(split, $event)"
              @select-items="selectSplitItems(split, $event)"
              @deselect-items="deselectSplitItems(split, $event)"
              @add="addToSplit(split)"
              @drop-item="dropSample(split, $event)"
              @drop-selected="dropSelectedSamples(split)"
              @delete="deletingSplit = split"
              @open-item="openSplitItem(split, $event)"
              @title-dragstart="beginSplitDrag($event, split)"
              @title-dragend="endSplitDrag"
              @pane-dragover="dragOverSplit($event, split)"
            />
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
}

.split-pane-move {
  transition: transform 220ms cubic-bezier(0.2, 0.9, 0.25, 1.15);
}

.split-pane-dragging {
  box-shadow: 0 12px 28px rgb(0 0 0 / 0.22);
  opacity: 0.92;
  transform: scale(1.015);
  will-change: transform;
  z-index: 10;
}
</style>
