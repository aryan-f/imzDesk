<script setup lang="ts">
type HealthResponse = {
  status: string
}

const {
  data,
  error,
  pending,
  refresh,
} = await useFetch<HealthResponse>(`/api/health`, {
  default: () => ({ status: '' }),
})

const manualData = ref<HealthResponse | null>(null)
const manualError = ref<unknown>(null)
const manualPending = ref(false)

const manualFetch = async () => {
  manualPending.value = true
  manualError.value = null

  try {
    manualData.value = await $fetch<HealthResponse>(`/api/health`)
  } catch (err) {
    manualError.value = err
    manualData.value = null
  } finally {
    manualPending.value = false
  }
}

const useFetchMessage = computed(() => {
  if (pending.value) return 'Checking API health with useFetch...'
  if (error.value) return 'The API health check failed.'
  if (data.value?.status === 'ok') return 'The API is healthy.'
  return 'The API returned an unexpected response.'
})

const manualMessage = computed(() => {
  if (manualPending.value) return 'Checking API health with $fetch...'
  if (manualError.value) return 'The manual API health check failed.'
  if (!manualData.value) return 'No manual request has been made yet.'
  if (manualData.value.status === 'ok') return 'The manual API check succeeded.'
  return 'The manual request returned an unexpected response.'
})

const formatJson = (value: unknown) => JSON.stringify(value, null, 2)
</script>

<template>
  <UContainer class="py-12">
    <div class="mx-auto max-w-3xl">
      <div class="mb-8 text-center">
        <h1 class="text-3xl font-bold tracking-tight">API Health Check</h1>
        <p class="mt-2 text-sm text-muted">
          This page tests both <code>useFetch</code> and <code>$fetch</code> against
          <code>/api/health</code>.
        </p>
      </div>

      <div class="grid gap-6 md:grid-cols-2">
        <UCard>
          <template #header>
            <div class="flex items-center justify-between gap-3">
              <div>
                <h2 class="text-lg font-semibold">useFetch</h2>
                <p class="text-sm text-muted">Loaded automatically on page render</p>
              </div>

              <UButton
                :loading="pending"
                icon="i-lucide-refresh-cw"
                @click="refresh()"
              >
                Request again
              </UButton>
            </div>
          </template>

          <UAlert
            :color="error ? 'error' : data?.status === 'ok' ? 'success' : 'neutral'"
            :title="useFetchMessage"
            variant="soft"
          />

          <div class="mt-4">
            <p class="mb-2 text-sm font-medium">Raw JSON</p>
            <pre class="overflow-x-auto rounded-lg bg-muted p-4 text-sm">{{ formatJson(data) }}</pre>
          </div>

          <div v-if="error" class="mt-4">
            <p class="mb-2 text-sm font-medium">Error</p>
            <pre class="overflow-x-auto rounded-lg bg-muted p-4 text-sm">{{ formatJson(error) }}</pre>
          </div>
        </UCard>

        <UCard>
          <template #header>
            <div class="flex items-center justify-between gap-3">
              <div>
                <h2 class="text-lg font-semibold">$fetch</h2>
                <p class="text-sm text-muted">Triggered manually without page refresh</p>
              </div>

              <UButton
                :loading="manualPending"
                icon="i-lucide-play"
                @click="manualFetch"
              >
                Request now
              </UButton>
            </div>
          </template>

          <UAlert
            :color="manualError ? 'error' : manualData?.status === 'ok' ? 'success' : 'neutral'"
            :title="manualMessage"
            variant="soft"
          />

          <div class="mt-4">
            <p class="mb-2 text-sm font-medium">Raw JSON</p>
            <pre class="overflow-x-auto rounded-lg bg-muted p-4 text-sm">{{ formatJson(manualData) }}</pre>
          </div>

          <div v-if="manualError" class="mt-4">
            <p class="mb-2 text-sm font-medium">Error</p>
            <pre class="overflow-x-auto rounded-lg bg-muted p-4 text-sm">{{ formatJson(manualError) }}</pre>
          </div>
        </UCard>
      </div>
    </div>
  </UContainer>
</template>
