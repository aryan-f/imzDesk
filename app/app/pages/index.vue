<script setup lang="ts">
const repositoryUrl = 'https://github.com/aryan-f/imzDesk'

const primaryLinks = [
  {
    label: 'Workspace',
    description: 'View, register, and annotate.',
    icon: 'i-lucide-panels-top-left',
    to: '/workspace',
  },
  {
    label: 'Datasets',
    description: 'Select, organize, and curate.',
    icon: 'i-lucide-database',
    to: '/datasets',
  },
]

const secondaryLinks = [
  {
    label: 'GitHub',
    icon: 'simple-icons-github',
    to: repositoryUrl,
  },
  {
    label: 'Submit an Issue',
    icon: 'i-lucide-circle-alert',
    to: `${repositoryUrl}/issues/new`,
  },
  {
    label: 'Documentation',
    icon: 'i-lucide-book-open',
    to: 'https://med-i-lab.gitbook.io/imzdesk',
  },
]
</script>

<template>
  <main class="flex min-h-0 flex-1 items-center justify-center px-6 py-10">
    <div class="flex w-full max-w-2xl flex-col gap-8">
      <div class="space-y-2">
        <div class="flex items-center gap-3">
          <UIcon name="simple-icons-spectrum" class="size-7 text-secondary" />
          <h1 class="text-3xl font-semibold tracking-tight">
            imz<span class="text-secondary">Desk</span>
          </h1>
        </div>
        <p class="max-w-2xl text-base leading-6 text-muted">
          WSI-MSI Workbench
        </p>
      </div>
      <div class="grid gap-3 sm:grid-cols-2">
        <NuxtLink v-for="link in primaryLinks" :key="link.to" :to="link.to" class="group rounded-lg border border-default bg-muted p-5 transition-colors hover:bg-elevated">
          <div class="flex items-start gap-4">
            <div class="flex size-12 items-center justify-center rounded-md bg-default ring-1 ring-default transition-colors group-hover:bg-accented">
              <UIcon :name="link.icon" class="size-6 text-info" />
            </div>
            <div class="min-w-0 space-y-1">
              <div class="text-xl font-semibold text-default">
                {{ link.label }}
              </div>
              <div class="text-sm leading-5 text-muted">
                {{ link.description }}
              </div>
            </div>
          </div>
        </NuxtLink>
      </div>
      <div class="flex flex-wrap gap-2">
        <UButton
          v-for="link in secondaryLinks"
          :key="link.to"
          :to="link.to"
          :icon="link.icon"
          :label="link.label"
          color="neutral"
          variant="soft"
          target="_blank"
        />
      </div>
    </div>
  </main>
</template>
