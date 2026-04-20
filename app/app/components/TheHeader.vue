<script setup lang="ts">
import type { NavigationMenuItem } from '@nuxt/ui'

const items = ref<NavigationMenuItem[]>([
  {
    label: 'Images',
    to: '/',
  },
])
</script>


<template>
  <header class="bg-default border-b border-default h-(--ui-header-height) shrink-0 w-full flex items-center justify-between px-8">
    <div class="flex items-center gap-6">
      <div class="flex items-center gap-2 font-semibold text-lg cursor-default">
        <UIcon name="simple-icons-spectrum" class="text-primary" />
        <span class="font-bold">
          <span class="text-default">imz</span>
          <span class="text-primary">Desk</span>
        </span>
      </div>
      <nav class="flex items-center gap-4 text-sm">
        <UNavigationMenu :items="items"/>
      </nav>
    </div>
    <div class="flex items-center gap-3">
      <UTooltip text="Color Mode">
        <UColorModeButton />
      </UTooltip>
      <UTooltip text="Settings">
        <UButton icon="i-lucide-settings" color="neutral" variant="ghost" />
      </UTooltip>
      <UTooltip text="Shut Down">
        <UButton icon="i-lucide-power" color="neutral" variant="ghost" />
      </UTooltip>
    </div>
  </header>
</template>

