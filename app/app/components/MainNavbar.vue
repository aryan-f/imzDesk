<script setup lang="ts">
const menuItems = [
  { label: 'Images', to: '/' },
  { label: 'Datasets', to: '/datasets' },
]

const { data: infrastructure } = await useFetch('/api/system/infra')
</script>

<template>
  <header class="flex h-12 shrink-0 items-center gap-4 border-b border-default bg-muted px-4">
    <div class="flex items-center gap-2">
      <UIcon name="simple-icons-spectrum" class="text-secondary" />
      <span class="font-semibold tracking-tight">imz<span class="text-secondary">Desk</span></span>
    </div>
    <UNavigationMenu :items="menuItems" color="neutral" class="ms-1" />
    <div class="ms-auto flex items-center gap-3">
      <code class="rounded-md border border-default bg-default px-2 py-0.5 font-data text-sm text-muted">
        {{ infrastructure.workspace }}
      </code>
      <UModal title="System Settings">
        <UButton variant="ghost" color="neutral" icon="mdi-cog-outline" />
        <template #body>
          <USkeleton class="h-48 m-4" />
        </template>
      </UModal>
    </div>
  </header>
</template>
