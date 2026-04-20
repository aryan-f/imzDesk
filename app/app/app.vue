<script setup>
useHead({
  meta: [{ name: 'viewport', content: 'width=device-width, initial-scale=1' }],
  link: [{ rel: 'icon', href: '/favicon.ico' }],
  htmlAttrs: { lang: 'en' }
})

useSeoMeta({
  title: 'imzDesk',
})
</script>

<template>
  <UApp>
    <div class="h-screen w-screen overflow-hidden flex flex-col">
      <TheHeader />
      <div class="flex min-h-0 flex-1">
        <NuxtPage />
      </div>
    </div>
  </UApp>
</template>
