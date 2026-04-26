<script setup lang="ts">
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
    </div>
    <div class="flex items-center gap-3">
      <UTooltip text="Color Mode">
        <UColorModeButton />
      </UTooltip>
      <UModal title="Settings">
        <UTooltip text="Settings">
          <UButton icon="i-lucide-settings" color="neutral" variant="ghost" />
        </UTooltip>
        <template #body>
          <USkeleton class="h-48 m-4" />
        </template>
        <template #footer>
          <div class="flex justify-end w-full gap-2">
            <UButton color="neutral">Discard</UButton>
            <UButton color="success">Save Changes</UButton>
          </div>
        </template>
      </UModal>
      <UTooltip text="Shut Down">
        <UButton icon="i-lucide-power" color="neutral" variant="ghost" />
      </UTooltip>
    </div>
  </header>
</template>

