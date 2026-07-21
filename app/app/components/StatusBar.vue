<script setup lang="ts">
const props = defineProps<{
  logsOpen?: boolean
}>()

const emit = defineEmits<{
  'update:logsOpen': [value: boolean]
}>()

const activity = useActivity()

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

const cpuUsage = ref(0)
const ramUsage = ref(0)
const filledRAM = ref(0)
const totalRAM = ref(0)
let metricsStream: EventSource | null = null

function applyMetrics(metrics: SystemMetrics) {
  cpuUsage.value = Math.round(metrics.cpu.usage_percent)
  ramUsage.value = metrics.memory.usage_percent
  filledRAM.value = metrics.memory.used
  totalRAM.value = metrics.memory.total
}

onMounted(() => {
  metricsStream = new EventSource('/api/system/metrics')
  metricsStream.onmessage = (event) => {
    applyMetrics(JSON.parse(event.data).data as SystemMetrics)
  }
})

onUnmounted(() => {
  metricsStream?.close()
  metricsStream = null
})
</script>

<template>
  <footer class="flex h-7.5 shrink-0 items-center gap-4 border-t border-default bg-muted px-3 text-[11.5px] text-muted">
    <span class="flex items-center gap-1.5">
      <UIcon name="material-symbols-circle" class="animate-pulse size-2" :class="activity.active.value ? 'text-warning' : 'text-success'" />
      <span>{{ activity.message }}<span v-if="activity.active.value" class="status-ellipsis">...</span></span>
    </span>
    <div class="ms-auto flex items-center gap-2">
      <span class="font-data text-xs text-dimmed">CPU</span>
      <UProgress :model-value="cpuUsage" size="sm" class="w-14" />
      <span class="font-data text-xs">{{ cpuUsage }}%</span>
    </div>
    <div class="flex items-center gap-2">
      <span class="font-data text-xs text-dimmed">RAM</span>
      <UProgress :model-value="ramUsage" color="secondary" size="sm" class="w-14" />
      <span class="font-data text-xs">{{ filledRAM.toFixed(1) }}/{{ totalRAM.toFixed(1) }}G</span>
    </div>
    <UButton
      color="neutral" variant="ghost" size="xs" icon="mdi-text"
      :trailing-icon="props.logsOpen ? 'i-lucide-chevron-down' : 'i-lucide-chevron-up'"
      @click="emit('update:logsOpen', !props.logsOpen)"
    >
      Logs
    </UButton>
  </footer>
</template>

<style scoped>
.status-ellipsis {
  display: inline-block;
  overflow: hidden;
  vertical-align: bottom;
  width: 0;
  animation: status-ellipsis 1.1s steps(5, end) infinite;
}

@keyframes status-ellipsis {
  to {
    width: 1.5em;
  }
}
</style>
