<script setup lang="ts">
import type { TabsItem } from '@nuxt/ui'
import type { FileType } from '~/types/filesystem'
import type { MSIMetadata, WSIMetadata } from '~/types/images'

const { state } = useWorkspace()
type Metadata = WSIMetadata | MSIMetadata
type OptionalValue = Metadata['optional'][string]

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
  return `${state.value.dirpath}/${activeFilename.value}`
})
const metadata = ref<Metadata | null>(null)
const metadataLoading = ref(false)
const optionalDraft = ref<Record<string, string>>({})
const newOptionalKey = ref('')
const newOptionalValue = ref('')
const newOptionalKeyInput = ref<{ inputRef?: HTMLInputElement } | null>(null)
const metadataEndpoint = '/api/images/metadata'

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
  metadata.value = await $fetch<Metadata>(`${metadataEndpoint}/optional`, {
    method: 'POST',
    query: { filepath: activeFilepath.value },
    body: {
      key,
      value: coerceOptionalValue(value),
    },
  })
  syncOptionalDraft(metadata.value)
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
  metadata.value = await $fetch<Metadata>(`${metadataEndpoint}/optional`, {
    method: 'DELETE',
    query: {
      filepath: activeFilepath.value,
      key,
    },
  })
  syncOptionalDraft(metadata.value)
}

watch(
  () => [state.value.active, activeFilepath.value] as [FileType | null, string | null],
  fetchMetadata,
  { immediate: true },
)
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
      <USkeleton v-else class="h-full min-h-48 overflow-hidden" />
    </div>
  </div>
</template>
