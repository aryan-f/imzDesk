<script setup lang="ts">
const props = defineProps<{
  path: string
}>()

type MetadataValue = string | number | boolean | null

type MetadataItem = {
  key: string
  value: MetadataValue
}

type MetadataRow = MetadataItem & {
  id: number
}

const loading = ref<boolean>(false)
const saving = ref<boolean>(false)
const error = ref<boolean>(false)
const rows = ref<MetadataRow[]>([])
const dirty = ref<boolean>(false)

let nextId = 0

watch(
  () => props.path,
  async () => {
    try {
      loading.value = true
      error.value = false

      const response = await $fetch<MetadataItem[]>('/api/imzML/metadata', {
        query: { path: props.path },
      })

      rows.value = response.map(item => ({
        id: nextId++,
        key: item.key,
        value: item.value,
      }))
    } catch {
      error.value = true
      rows.value = []
    } finally {
      loading.value = false
      await nextTick()
      dirty.value = false
    }
  },
  { immediate: true },
)

async function save() {
  try {
    saving.value = true
    error.value = false

    const body = rows.value.map(row => ({ key: row.key.trim(), value: row.value })).filter(row => row.key.length > 0)

    const response = await $fetch<MetadataItem[]>('/api/imzML/metadata', {
      method: 'PUT',
      query: { path: props.path },
      body,
    })

    rows.value = response.map(item => ({
      id: nextId++,
      key: item.key,
      value: item.value,
    }))
  } catch {
    error.value = true
  } finally {
    saving.value = false
    await nextTick()
    dirty.value = false
  }
}

function addRow() {
  rows.value.push({
    id: nextId++,
    key: '',
    value: '',
  })
}

function deleteRow(id: number) {
  rows.value = rows.value.filter(row => row.id !== id)
}

watch(
  rows,
  () => {
    dirty.value = true
  },
  { deep: true },
)
</script>

<template>
  <UForm class="flex flex-col gap-2 p-4 w-full h-full">
    <div class="shrink-0 flex justify-between align-middle items-center mb-1.5">
      <div class="text-sm font-bold">Metadata</div>
      <UChip :show="dirty">
        <UButton size="sm" variant="outline" icon="material-symbols-save" color="neutral" type="submit" :loading="saving" @click="save">
          Save
        </UButton>
      </UChip>
    </div>
    <div class="flex-1 overflow-x-hidden overflow-y-auto scrollbar-thin">
      <table class="text-xs w-full border border-default">
        <tbody>
        <tr v-for="row in rows" :key="row.id" class="border-b border-default">
          <th class="w-47">
            <UInput v-model="row.key" size="xs" variant="ghost" placeholder="Name" :ui="{ base: 'rounded-none' }" />
          </th>
          <td class="w-47 border-l border-default">
            <UInput v-model="row.value" size="xs" variant="ghost" placeholder="Value" :ui="{ base: 'rounded-none' }" />
          </td>
          <td class="w-6 border-l border-default">
            <UButton color="neutral" variant="link" size="xs" icon="material-symbols-delete" @click="deleteRow(row.id)" />
          </td>
        </tr>
        <tr>
          <td colspan="3">
            <UButton color="neutral" variant="link" size="xs" trailing-icon="material-symbols-add" @click="addRow">
              Add
            </UButton>
          </td>
        </tr>
        </tbody>
      </table>
    </div>
  </UForm>
</template>
