<script setup lang="ts">
import type { WorkspaceSettings } from '~/types/images'
import type { SystemInfrastructure } from '~/types/system'

const menuItems = [
  { label: 'Workspace', to: '/workspace' },
  { label: 'Datasets', to: '/datasets' },
]

const { data: infrastructure } = await useFetch<SystemInfrastructure>('/api/system/infra', {
  default: () => ({ workspace: '' }),
})

const settingsEndpoint = '/api/workspace/settings'
const { data: workspaceSettings } = await useFetch<WorkspaceSettings>(settingsEndpoint, {
  default: () => ({ labels: [] }),
})
const settingsDraft = ref<WorkspaceSettings>({ labels: [] })
const settingsSaving = ref(false)
const deletingLabelId = ref<string | null>(null)

const deletingLabel = computed(() => settingsDraft.value.labels.find(label => label.id === deletingLabelId.value) ?? null)
const deletingLabelDescription = computed(() => {
  if (!deletingLabel.value) return ''
  return `Are you sure you want to delete "${deletingLabel.value.name}"? This action will invalidate that label in all files that reference it. Annotation YAML files will not be rewritten, but downstream elements will no longer recognize this label id.`
})

watch(workspaceSettings, (settings) => {
  settingsDraft.value = structuredClone(settings ?? { labels: [] })
}, { immediate: true })

function addLabel() {
  const id = `label_${Date.now().toString(36)}`
  settingsDraft.value.labels.push({
    id,
    name: 'Label',
    color: '#2563eb',
  })
}

function requestDeleteLabel(id: string) {
  deletingLabelId.value = id
}

function cancelDeleteLabel() {
  deletingLabelId.value = null
}

function deleteLabel(id: string) {
  settingsDraft.value.labels = settingsDraft.value.labels.filter(label => label.id !== id)
  deletingLabelId.value = null
}

async function saveWorkspaceSettings() {
  settingsSaving.value = true
  try {
    workspaceSettings.value = await $fetch<WorkspaceSettings>(settingsEndpoint, {
      method: 'POST',
      body: settingsDraft.value,
    })
    window.dispatchEvent(new CustomEvent('imzdesk:workspace-settings-changed'))
  } finally {
    settingsSaving.value = false
  }
}
</script>

<template>
  <header class="flex h-12 shrink-0 items-center gap-4 border-b border-default bg-muted px-4">
    <NuxtLink to="/" class="flex items-center gap-2">
      <UIcon name="simple-icons-spectrum" class="text-secondary" />
      <span class="font-semibold tracking-tight">imz<span class="text-secondary">Desk</span></span>
    </NuxtLink>
    <UNavigationMenu :items="menuItems" color="neutral" class="ms-1" />
    <div class="ms-auto flex items-center gap-3">
      <code class="rounded-md border border-default bg-default px-2 py-0.5 font-data text-sm text-muted">
        {{ infrastructure.workspace }}
      </code>
      <UModal title="Workspace Settings">
        <UButton variant="ghost" color="neutral" icon="mdi-cog-outline" />
        <template #body>
          <div class="space-y-3 p-1">
            <div class="flex items-center justify-between">
              <div class="font-mono text-sm font-bold uppercase text-dimmed">
                Labels
              </div>
              <UButton icon="i-lucide-plus" color="primary" variant="soft" size="xs" square @click="addLabel" />
            </div>
            <div class="space-y-2">
              <div v-for="label in settingsDraft.labels" :key="label.id" class="grid grid-cols-[1fr_5rem_auto] items-center gap-2">
                <UInput v-model="label.name" size="sm" class="font-data" />
                <UInput v-model="label.color" type="color" size="sm" />
                <UButton icon="i-lucide-trash-2" color="neutral" variant="ghost" size="xs" square class="size-4 p-0" @click="requestDeleteLabel(label.id)" />
              </div>
            </div>
            <UAlert
              v-if="deletingLabel"
              color="warning"
              variant="soft"
              icon="i-lucide-triangle-alert"
              title="Delete label?"
              :description="deletingLabelDescription"
            >
              <template #actions>
                <UButton label="Cancel" color="neutral" variant="ghost" size="sm" @click="cancelDeleteLabel" />
                <UButton label="Yes, I'm sure" icon="i-lucide-trash-2" color="warning" size="sm" @click="deleteLabel(deletingLabel.id)" />
              </template>
            </UAlert>
            <div class="flex justify-end pt-6">
              <UButton label="Save" icon="i-lucide-check" color="primary" :loading="settingsSaving" :disabled="settingsSaving" @click="saveWorkspaceSettings" />
            </div>
          </div>
        </template>
      </UModal>
    </div>
  </header>
</template>
