<script setup lang="ts">
import type { DatasetKind, DatasetManifest } from '~/types/datasets'

const activity = useActivity()
const endpoint = '/api/datasets/manifest'
const saving = ref(false)
const datasets = ref<DatasetManifest[]>([])
const deleteTarget = ref<DatasetManifest | null>(null)
const deleting = ref(false)
const { data: loadedDatasets, refresh } = await useFetch<DatasetManifest[]>(endpoint, { default: () => [] })

watch(loadedDatasets, (value) => {
  datasets.value = structuredClone(value ?? [])
}, { immediate: true })

const createOptions: Array<{ kind: DatasetKind, title: string, icon: string }> = [
  { kind: 'wsi', title: 'WSI', icon: 'healthicons-cell-nuclei-outline-24px' },
  { kind: 'msi', title: 'MSI', icon: 'streamline-image-blur' },
  { kind: 'paired', title: 'WSI-MSI', icon: 'i-lucide-link' },
]

function newId() {
  return crypto.randomUUID().replaceAll('-', '').slice(0, 10)
}

function titleFor(kind: DatasetKind) {
  if (kind === 'paired') return 'WSI-MSI Dataset'
  return `${kind.toUpperCase()} Dataset`
}

function kindLabel(kind: DatasetKind) {
  return kind === 'paired' ? 'WSI-MSI' : kind.toUpperCase()
}

async function createDataset(kind: DatasetKind) {
  saving.value = true
  const task = activity.startTask('Creating dataset')
  const dataset: DatasetManifest = {
    id: newId(),
    name: titleFor(kind),
    kind,
    splits: {
      train: [],
      validation: [],
      test: [],
    },
  }
  try {
    await $fetch<DatasetManifest>(endpoint, {
      method: 'POST',
      body: dataset,
    })
    await refresh()
    await navigateTo(`/datasets/${dataset.id}`)
  } finally {
    activity.endTask(task)
    saving.value = false
  }
}

function openDataset(dataset: DatasetManifest) {
  navigateTo(`/datasets/${dataset.id}`)
}

async function deleteDataset() {
  if (!deleteTarget.value) return
  deleting.value = true
  const task = activity.startTask('Deleting dataset')
  try {
    await $fetch<boolean>(`${endpoint}/${deleteTarget.value.id}`, {
      method: 'DELETE',
    })
    deleteTarget.value = null
    await refresh()
  } finally {
    activity.endTask(task)
    deleting.value = false
  }
}
</script>

<template>
  <div class="min-h-0 flex-1 overflow-y-auto bg-default">
    <main class="mx-auto flex min-h-full w-full max-w-5xl flex-col justify-center px-6 py-10">
      <section class="mb-7">
        <h1 class="text-4xl font-semibold tracking-normal text-default">
          Datasets
        </h1>
      </section>
      <section class="space-y-3">
        <div class="text-sm font-semibold text-muted">
          Create a New Dataset
        </div>
        <div class="grid gap-3 md:grid-cols-3">
          <UButton
            v-for="option in createOptions"
            :key="option.kind"
            color="neutral"
            variant="soft"
            class="h-16 justify-start rounded-lg px-4"
            :disabled="saving"
            @click="createDataset(option.kind)"
          >
            <template #leading>
              <span class="flex size-8 items-center justify-center rounded-md bg-elevated text-info">
                <UIcon :name="option.icon" class="size-5" />
              </span>
            </template>
            <span class="text-base font-semibold text-default">
              {{ option.title }}
            </span>
          </UButton>
        </div>
      </section>
      <section class="mt-8 flex h-[360px] min-h-0 flex-col rounded-lg border border-default bg-muted">
        <div class="flex h-12 items-center border-b border-default px-4">
          <h2 class="text-sm font-semibold text-muted">
            Existing Datasets
          </h2>
          <UBadge :label="String(datasets.length)" color="neutral" variant="soft" size="sm" class="ms-auto" />
        </div>
        <div class="min-h-0 flex-1 overflow-y-auto p-2">
          <div
            v-for="dataset in datasets"
            :key="dataset.id"
            class="flex w-full items-center gap-3 rounded-md px-3 py-2 text-left hover:bg-elevated"
            role="button"
            tabindex="0"
            @dblclick="openDataset(dataset)"
            @keydown.enter="openDataset(dataset)"
          >
            <UIcon :name="dataset.kind === 'paired' ? 'i-lucide-link' : dataset.kind === 'wsi' ? 'healthicons-cell-nuclei-outline-24px' : 'streamline-image-blur'" class="size-5 text-info" />
            <span class="min-w-0 flex-1">
              <span class="block truncate text-sm font-semibold text-default">{{ dataset.name }}</span>
              <span class="block truncate font-data text-xs text-dimmed">{{ dataset.id }}</span>
            </span>
            <UBadge :label="kindLabel(dataset.kind)" color="neutral" variant="soft" size="sm" />
            <UButton
              icon="i-lucide-trash-2"
              color="neutral"
              variant="ghost"
              size="xs"
              square
              class="size-6 p-0"
              @click.stop="deleteTarget = dataset"
            />
          </div>
          <div v-if="!datasets.length" class="px-3 py-2 text-sm text-muted">
            No datasets yet.
          </div>
        </div>
      </section>
    </main>
    <UModal :open="Boolean(deleteTarget)" @update:open="value => { if (!value) deleteTarget = null }">
      <template #content>
        <div class="space-y-4 p-4">
          <div>
            <h2 class="text-base font-semibold text-default">
              Delete Dataset
            </h2>
            <p class="mt-1 text-sm text-muted">
              Are you sure you want to delete "{{ deleteTarget?.name }}"? This action cannot be undone.
            </p>
          </div>
          <div class="flex justify-end gap-2">
            <UButton label="Cancel" color="neutral" variant="ghost" :disabled="deleting" @click="deleteTarget = null" />
            <UButton label="Yes, I'm sure" icon="i-lucide-trash-2" color="error" :loading="deleting" :disabled="deleting" @click="deleteDataset" />
          </div>
        </div>
      </template>
    </UModal>
  </div>
</template>
