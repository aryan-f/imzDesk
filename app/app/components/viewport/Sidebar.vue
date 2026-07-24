<script setup lang="ts">
import type { ComponentPublicInstance } from 'vue'
import type { TabsItem } from '@nuxt/ui'
import type { FileType } from '~/types/filesystem'
import type { Annotation, Label, MSIMetadata, WorkspaceSettings, WSIMetadata } from '~/types/images'

const { state, setActive } = useWorkspace()
const activity = useActivity()
type Metadata = WSIMetadata | MSIMetadata
type OptionalValue = Metadata['optional'][string]
type ListedAnnotation = Annotation & { owner: FileType, filepath: string }
type AnnotationSelectionEvent = CustomEvent<{ owner: FileType, id: string }>

const activeColor = computed(() => {
  switch (state.value.active) {
    case 'WSI': return 'primary'
    case 'MSI': return 'secondary'
    default: return 'neutral'
  }
})

function activeColorClass(prefix: string) {
  return `${prefix}-${activeColor.value}`
}

const tabs = ref<TabsItem[]>([
  { value: 'metadata', label: 'Metadata' },
  { value: 'tags', label: 'Tags' },
  { value: 'annotations', label: 'Annotations' },
])

const tab = ref('metadata')
const activeFilename = computed(() => {
  if (!state.value.active) return ''
  return state.value.opened[state.value.active]
})
const activeFilepath = computed(() => {
  if (!state.value.active || !activeFilename.value) return null
  return activeFilename.value
})
const metadata = ref<Metadata | null>(null)
const metadataLoading = ref(false)
const optionalDraft = ref<Record<string, string>>({})
const newOptionalKey = ref('')
const newOptionalValue = ref('')
const newOptionalKeyInput = ref<{ inputRef?: HTMLInputElement } | null>(null)
const metadataEndpoint = '/api/images/metadata'
const tags = ref<string[]>([])
const tagsLoading = ref(false)
const newTag = ref('')
const newTagInput = ref<{ inputRef?: HTMLInputElement } | null>(null)
const tagsEndpoint = '/api/images/tags'
const annotations = ref<ListedAnnotation[]>([])
const annotationsLoading = ref(false)
const annotationsEndpoint = '/api/images/annotations'
const workspaceSettingsEndpoint = '/api/workspace/settings'
const workspaceSettings = ref<WorkspaceSettings>({ labels: [] })
const focusedAnnotationId = ref<string | null>(null)
const pendingAnnotationFocus = ref<{ owner: FileType, id: string } | null>(null)
const annotationRows = new Map<string, HTMLElement>()
const { tagBadgeClass, tagColorStyle } = useTagColors()

const requiredRows = computed(() => {
  if (!metadata.value || !state.value.active) return []
  const rows = [
    { label: 'Width', value: formatPixels(metadata.value.width) },
    { label: 'Height', value: formatPixels(metadata.value.height) },
    { label: 'Spatial Resolution', value: formatMpp(metadata.value.mpp) },
  ]
  if (state.value.active === 'WSI') {
    const wsi = metadata.value as WSIMetadata
    rows.push(
      { label: 'Vendor', value: formatValue(wsi.vendor) },
      { label: 'Objective power', value: wsi.objective_power == null ? '—' : `${Number(wsi.objective_power.toFixed(2))}x` },
    )
  }
  return rows
})

const optionalEntries = computed(() => Object.entries(optionalDraft.value))
const metadataRowClass = 'grid grid-cols-[7.5rem_1fr] gap-2 border-b border-default/40 pr-5 text-sm leading-6'

function notifyAnnotationsChanged() {
  window.dispatchEvent(new CustomEvent('imzdesk:annotations-changed'))
}

function setAnnotationRowRef(id: string, element: Element | ComponentPublicInstance | null) {
  if (element instanceof HTMLElement) {
    annotationRows.set(id, element)
  } else {
    annotationRows.delete(id)
  }
}

function annotationRowRef(id: string) {
  return (element: Element | ComponentPublicInstance | null) => setAnnotationRowRef(id, element)
}

function formatValue(value: unknown) {
  if (value === null || value === undefined || value === '') return '—'
  return String(value)
}

function formatPixels(value: number | null | undefined) {
  if (value === null || value === undefined) return '—'
  return `${value.toLocaleString()} px`
}

function formatMpp(value: Metadata['mpp']) {
  if (!value) return '—'
  const x = Number(value.x.toFixed(2))
  const y = Number(value.y.toFixed(2))
  if (x === y) return `${x.toFixed(2)} µm/pixel`
  return `(${x.toFixed(2)}, ${y.toFixed(2)}) µm per pixel`
}

function coerceOptionalValue(value: string): OptionalValue {
  const trimmed = value.trim()
  if (trimmed === '') return null
  if (trimmed === 'true') return true
  if (trimmed === 'false') return false
  const numeric = Number(trimmed)
  if (!Number.isNaN(numeric) && trimmed !== '') return numeric
  return value
}

function syncOptionalDraft(value: Metadata | null) {
  optionalDraft.value = Object.fromEntries(
    Object.entries(value?.optional ?? {}).map(([key, entry]) => [key, entry == null ? '' : String(entry)]),
  )
}

async function fetchMetadata() {
  if (!activeFilepath.value) {
    metadata.value = null
    syncOptionalDraft(null)
    return
  }
  metadataLoading.value = true
  try {
    metadata.value = await $fetch<Metadata>(`${metadataEndpoint}/all`, {
      query: { filepath: activeFilepath.value },
    })
    syncOptionalDraft(metadata.value)
  } finally {
    metadataLoading.value = false
  }
}

async function saveOptional(key: string, value: string) {
  if (!key || !activeFilepath.value) return
  const task = activity.startTask('Saving metadata')
  try {
    metadata.value = await $fetch<Metadata>(`${metadataEndpoint}/optional`, {
      method: 'POST',
      query: { filepath: activeFilepath.value },
      body: {
        key,
        value: coerceOptionalValue(value),
      },
    })
    syncOptionalDraft(metadata.value)
  } finally {
    activity.endTask(task)
  }
}

async function addOptional() {
  const key = newOptionalKey.value.trim()
  if (!key) return
  await saveOptional(key, newOptionalValue.value)
  newOptionalKey.value = ''
  newOptionalValue.value = ''
  await nextTick()
  newOptionalKeyInput.value?.inputRef?.focus()
}

async function deleteOptional(key: string) {
  if (!activeFilepath.value) return
  const task = activity.startTask('Deleting metadata')
  try {
    metadata.value = await $fetch<Metadata>(`${metadataEndpoint}/optional`, {
      method: 'DELETE',
      query: {
        filepath: activeFilepath.value,
        key,
      },
    })
    syncOptionalDraft(metadata.value)
  } finally {
    activity.endTask(task)
  }
}

async function fetchTags() {
  if (!activeFilepath.value) {
    tags.value = []
    return
  }
  tagsLoading.value = true
  try {
    tags.value = await $fetch<string[]>(`${tagsEndpoint}/all`, {
      query: { filepath: activeFilepath.value },
    })
  } finally {
    tagsLoading.value = false
  }
}

async function addTag() {
  const tag = newTag.value.trim()
  if (!tag || !activeFilepath.value) return
  const task = activity.startTask('Saving tag')
  try {
    tags.value = await $fetch<string[]>(tagsEndpoint, {
      method: 'POST',
      query: { filepath: activeFilepath.value },
      body: { tag },
    })
    newTag.value = ''
    await nextTick()
    newTagInput.value?.inputRef?.focus()
  } finally {
    activity.endTask(task)
  }
}

async function deleteTag(tag: string) {
  if (!activeFilepath.value) return
  const task = activity.startTask('Deleting tag')
  try {
    tags.value = await $fetch<string[]>(tagsEndpoint, {
      method: 'DELETE',
      query: {
        filepath: activeFilepath.value,
        tag,
      },
    })
  } finally {
    activity.endTask(task)
  }
}

async function fetchAnnotations() {
  if (!activeFilepath.value || !state.value.active) {
    annotations.value = []
    return
  }
  annotationsLoading.value = true
  try {
    const values = await $fetch<Annotation[]>(`${annotationsEndpoint}/all`, {
      query: { filepath: activeFilepath.value },
    })
    annotations.value = values.map(annotation => ({
      ...annotation,
      owner: state.value.active!,
      filepath: activeFilepath.value!,
    }))
  } finally {
    annotationsLoading.value = false
  }
}

async function focusAnnotation(owner: FileType, id: string) {
  tab.value = 'annotations'
  if (state.value.active !== owner) setActive(owner)
  pendingAnnotationFocus.value = { owner, id }
  await nextTick()
  await fetchAnnotations()
  await nextTick()
  const row = annotationRows.get(id)
  if (!row) return
  row.scrollIntoView({ behavior: 'smooth', block: 'center' })
  focusedAnnotationId.value = id
  window.setTimeout(() => {
    if (focusedAnnotationId.value === id) focusedAnnotationId.value = null
  }, 900)
}

function handleAnnotationSelected(event: Event) {
  const { owner, id } = (event as AnnotationSelectionEvent).detail
  if (!owner || !id) return
  focusAnnotation(owner, id)
}

function annotationKindLabel(kind: Annotation['kind']) {
  if (kind === 'freehand') return 'Freehand'
  if (kind === 'polygon') return 'Polygon'
  return 'Box'
}

async function loadWorkspaceSettings() {
  workspaceSettings.value = await $fetch<WorkspaceSettings>(workspaceSettingsEndpoint)
}

const labelOptions = computed(() => workspaceSettings.value.labels.map(label => ({
  label: label.name,
  value: label.id,
  color: label.color,
})))

function labelForAnnotation(annotation: Annotation): Label {
  return workspaceSettings.value.labels.find(label => label.id === annotation.label) ?? {
    id: annotation.label,
    name: annotation.label,
    color: '#64748b',
  }
}

async function updateAnnotation(annotation: ListedAnnotation, patch: Partial<Pick<Annotation, 'label' | 'notes' | 'export' | 'project'>>) {
  const task = activity.startTask('Updating annotation')
  try {
    const updated = await $fetch<Annotation[]>(`${annotationsEndpoint}/${annotation.id}`, {
      method: 'PUT',
      query: { filepath: annotation.filepath },
      body: patch,
    })
    annotations.value = annotations.value
      .filter(value => value.filepath !== annotation.filepath)
      .concat(updated.map(value => ({ ...value, owner: annotation.owner, filepath: annotation.filepath })))
    notifyAnnotationsChanged()
  } finally {
    activity.endTask(task)
  }
}

function updateAnnotationLabel(annotation: ListedAnnotation, value: string | number | boolean | Record<string, unknown> | undefined) {
  if (typeof value === 'string') updateAnnotation(annotation, { label: value })
}

async function deleteAnnotation(annotation: ListedAnnotation) {
  const task = activity.startTask('Deleting annotation')
  try {
    const updated = await $fetch<Annotation[]>(`${annotationsEndpoint}/${annotation.id}`, {
      method: 'DELETE',
      query: { filepath: annotation.filepath },
    })
    annotations.value = annotations.value
      .filter(value => value.filepath !== annotation.filepath)
      .concat(updated.map(value => ({ ...value, owner: annotation.owner, filepath: annotation.filepath })))
    notifyAnnotationsChanged()
  } finally {
    activity.endTask(task)
  }
}

watch(
  () => [state.value.active, activeFilepath.value] as [FileType | null, string | null],
  fetchMetadata,
  { immediate: true },
)

watch(
  () => [state.value.active, activeFilepath.value, tab.value] as [FileType | null, string | null, string],
  () => {
    if (tab.value === 'tags') fetchTags()
  },
  { immediate: true },
)

watch(
  () => [state.value.active, activeFilepath.value, tab.value] as [FileType | null, string | null, string],
  () => {
    if (tab.value === 'annotations') fetchAnnotations()
  },
  { immediate: true },
)

function refreshAnnotations() {
  if (tab.value === 'annotations') fetchAnnotations()
}

onMounted(() => {
  loadWorkspaceSettings()
  window.addEventListener('imzdesk:annotations-changed', refreshAnnotations)
  window.addEventListener('imzdesk:annotation-selected', handleAnnotationSelected)
  window.addEventListener('imzdesk:workspace-settings-changed', loadWorkspaceSettings)
})

onBeforeUnmount(() => {
  window.removeEventListener('imzdesk:annotations-changed', refreshAnnotations)
  window.removeEventListener('imzdesk:annotation-selected', handleAnnotationSelected)
  window.removeEventListener('imzdesk:workspace-settings-changed', loadWorkspaceSettings)
})
</script>

<template>
  <div class="flex w-76 shrink-0 flex-col border-s border-default bg-muted">
    <div class="h-12 border-b border-default">
      <div class="flex flex-col justify-center mx-3 my-2 px-2 border-l-3" :class="activeColorClass('border')">
        <div class="text-xs leading-4" :class="activeColorClass('text')">
          {{ state.active }}
        </div>
        <div class="truncate text-sm leading-4 font-data">
          {{ activeFilename }}
        </div>
      </div>
    </div>
    <UTabs
      v-model="tab"
      :color="activeColor"
      :content="false"
      :items="tabs"
      :ui="{ trigger: 'flex-1' }"
      class="gap-4 w-full"
      variant="link"
    />
    <div class="min-h-0 flex-1 overflow-y-auto p-3">
      <template v-if="tab === 'metadata'">
        <div v-if="metadataLoading" class="flex items-center gap-2 py-1 text-sm text-muted">
          <UIcon name="i-lucide-loader-circle" class="size-4 animate-spin" />
          <span>Loading metadata</span>
        </div>
        <div v-else-if="metadata" class="space-y-5">
          <section class="space-y-2">
            <div class="mt-1 flex items-center gap-1.5 font-mono text-sm font-bold uppercase tracking-wide text-dimmed">
              <UIcon name="i-lucide-lock" class="size-3.5" />
              Required
            </div>
            <div class="space-y-1.5">
              <div v-for="row in requiredRows" :key="row.label" :class="metadataRowClass">
                <div class="text-muted">
                  {{ row.label }}
                </div>
                <div class="truncate font-data text-default">
                  {{ row.value }}
                </div>
              </div>
            </div>
          </section>
          <section class="space-y-2">
            <div class="flex items-center gap-1.5 font-mono text-sm font-bold uppercase tracking-wide text-dimmed">
              <UIcon name="i-lucide-pen-line" class="size-3.5" />
              Optional
            </div>
            <div class="space-y-1.5">
              <div v-for="[key, value] in optionalEntries" :key="key" :class="[metadataRowClass, 'relative']">
                <div class="truncate text-muted">
                  {{ key }}
                </div>
                <div class="truncate font-data text-default">
                  {{ value || '—' }}
                </div>
                <UButton icon="i-lucide-x" color="neutral" variant="ghost" size="xs" square class="absolute right-0 top-1/2 size-4 -translate-y-1/2 p-0" @click="deleteOptional(key)" />
              </div>
              <div class="grid grid-cols-[7.5rem_1fr_auto] items-center gap-1">
                <UInput ref="newOptionalKeyInput" v-model="newOptionalKey" size="sm" placeholder="Key" class="font-data" />
                <UInput v-model="newOptionalValue" size="sm" placeholder="Value" class="font-data" @keyup.enter="addOptional" />
                <UButton icon="i-lucide-plus" :color="activeColor" variant="soft" size="xs" square class="size-4 p-0" @click="addOptional" />
              </div>
            </div>
          </section>
        </div>
      </template>
      <template v-else-if="tab === 'tags'">
        <div v-if="tagsLoading" class="flex items-center gap-2 py-1 text-sm text-muted">
          <UIcon name="i-lucide-loader-circle" class="size-4 animate-spin" />
          <span>Loading tags</span>
        </div>
        <div v-else class="flex flex-wrap items-center gap-1.5">
          <div v-for="tag in tags" :key="tag" :class="tagBadgeClass" :style="tagColorStyle(tag)">
            <span class="min-w-0 max-w-40 truncate font-data">
              {{ tag }}
            </span>
            <UButton icon="i-lucide-x" color="neutral" variant="ghost" size="xs" square class="-mr-1 size-4 p-0 text-inherit hover:bg-black/10" @click="deleteTag(tag)" />
          </div>
          <div :class="[tagBadgeClass, 'w-14 border-default bg-default pr-1']">
            <UInput
              ref="newTagInput"
              v-model="newTag"
              variant="none"
              size="sm"
              placeholder="Add"
              :ui="{ base: 'h-5 w-8 px-0 py-0 font-data text-sm' }"
              @keyup.enter="addTag"
            />
            <UButton icon="i-lucide-plus" :color="activeColor" variant="ghost" size="xs" square class="size-4 p-0" @click="addTag" />
          </div>
        </div>
      </template>
      <template v-else-if="tab === 'annotations'">
        <div v-if="annotations.length" class="space-y-2">
          <div
            v-for="annotation in annotations"
            :key="`${annotation.owner}-${annotation.id}`"
            :ref="annotationRowRef(annotation.id)"
            class="space-y-1.5 rounded-md border p-2 transition-colors"
            :class="focusedAnnotationId === annotation.id ? 'border-default bg-white/70 dark:bg-white/10' : 'border-default/70 bg-default/60'"
          >
            <div class="flex items-center gap-2">
              <UBadge :label="annotationKindLabel(annotation.kind)" :color="activeColor" variant="soft" size="sm" />
              <div class="flex-1" />
              <UButton icon="i-lucide-trash-2" color="neutral" variant="ghost" size="xs" square class="size-3.5 p-0 [&_svg]:size-3" @click="deleteAnnotation(annotation)" />
            </div>
            <div class="grid grid-cols-[2.75rem_1fr] items-center gap-x-2 gap-y-1 text-sm leading-6">
              <div class="text-muted">
                Label
              </div>
              <USelect :model-value="annotation.label" :items="labelOptions" size="sm" class="font-data" @update:model-value="updateAnnotationLabel(annotation, $event)">
                <template #trailing>
                  <div class="relative size-4 overflow-hidden rounded border border-default">
                    <div class="absolute inset-0" :style="{ backgroundColor: labelForAnnotation(annotation).color }" />
                  </div>
                </template>
              </USelect>
              <div class="text-muted">
                Notes
              </div>
              <UInput :model-value="annotation.notes" size="sm" class="font-data" @change="updateAnnotation(annotation, { notes: ($event.target as HTMLInputElement).value })" />
              <div class="text-muted">
                Project
              </div>
              <USwitch :model-value="annotation.project" :color="annotation.owner === 'WSI' ? 'primary' : 'secondary'" @update:model-value="updateAnnotation(annotation, { project: $event })" />
              <div class="text-muted">
                Export
              </div>
              <USwitch :model-value="annotation.export" :color="annotation.owner === 'WSI' ? 'primary' : 'secondary'" @update:model-value="updateAnnotation(annotation, { export: $event })" />
            </div>
          </div>
        </div>
        <div v-else class="py-1 text-sm text-muted">
          No annotations
        </div>
      </template>
      <USkeleton v-else class="h-full min-h-48 overflow-hidden" />
    </div>
  </div>
</template>
