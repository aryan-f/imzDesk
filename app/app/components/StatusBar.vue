<script setup lang="ts">
const props = defineProps<{
  logsOpen?: boolean
}>()

const emit = defineEmits<{
  'update:logsOpen': [value: boolean]
}>()

interface SystemMetrics {
  cpu: {
    usage_percent: number
  }
  memory: {
    usage_percent: number
    used: number
    total: number
  }
}

const REFRESH_INTERVAL = 2000

const cpuUsage = ref(0)
const ramUsage = ref(0)
const filledRAM = ref(0)
const totalRAM = ref(0)
const metricsTimer = ref<ReturnType<typeof setInterval> | null>(null)

async function fetchMetrics() {
  try {
    const metrics = await $fetch<SystemMetrics>('/api/system/metrics')
    cpuUsage.value = Math.round(metrics.cpu.usage_percent)
    ramUsage.value = metrics.memory.usage_percent
    filledRAM.value = metrics.memory.used
    totalRAM.value = metrics.memory.total
  } catch (error) {
    console.error('Failed to fetch system metrics', error)
  }
}

onMounted(() => {
  fetchMetrics()
  metricsTimer.value = setInterval(fetchMetrics, REFRESH_INTERVAL)
})

onUnmounted(() => {
  if (metricsTimer.value) {
    clearInterval(metricsTimer.value)
  }
})
</script>

<template>
  <footer class="flex h-7.5 shrink-0 items-center gap-4 border-t border-default bg-muted px-3 text-[11.5px] text-muted">
    <span class="flex items-center gap-1.5">
      <UIcon name="material-symbols-circle" class="animate-pulse text-success size-2"/>
      Ready
    </span>
    <div class="ms-auto flex items-center gap-2">
      <span class="font-data text-xs text-dimmed">CPU</span>
      <UProgress :model-value="cpuUsage" size="sm" class="w-14"/>
      <span class="font-data text-xs">{{ cpuUsage }}%</span>
    </div>
    <div class="flex items-center gap-2">
      <span class="font-data text-xs text-dimmed">RAM</span>
      <UProgress :model-value="ramUsage" color="secondary" size="sm" class="w-14"/>
      <span class="font-data text-xs">{{ filledRAM.toFixed(1) }}/{{ totalRAM.toFixed(1) }}G</span>
    </div>
    <UButton
      color="neutral" variant="ghost" size="xs" icon="i-lucide-terminal"
      :trailing-icon="props.logsOpen ? 'i-lucide-chevron-down' : 'i-lucide-chevron-up'"
      @click="emit('update:logsOpen', !props.logsOpen)"
    >
      Logs
    </UButton>
  </footer>
</template>
