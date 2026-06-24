<script setup lang="ts">
const props = defineProps<{
  logsOpen?: boolean
}>()

interface LogRecord {
  name: string
  level: string
  created: number
  module: string
  msg: string
  thread: string
}

const MAX_LOGS = 500

const logs = ref<LogRecord[]>([])
const logContainer = ref<HTMLElement | null>(null)
let logStream: EventSource | null = null

function formatLogTime(created: number) {
  return new Date(created * 1000).toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  })
}

function levelClass(level: string) {
  switch (level) {
    case 'CRITICAL':
    case 'ERROR':
      return 'text-error'
    case 'WARNING':
      return 'text-warning'
    case 'INFO':
      return 'text-primary'
    case 'DEBUG':
      return 'text-muted'
    default:
      return 'text-dimmed'
  }
}

function appendLog(log: LogRecord) {
  logs.value.push(log)

  if (logs.value.length > MAX_LOGS) {
    logs.value.splice(0, logs.value.length - MAX_LOGS)
  }

  nextTick(() => {
    if (logContainer.value) {
      logContainer.value.scrollTop = logContainer.value.scrollHeight
    }
  })
}

onMounted(() => {
  logStream = new EventSource('/api/system/logs')

  logStream.onmessage = (event) => {
    try {
      appendLog(JSON.parse(event.data) as LogRecord)
    } catch (error) {
      console.error('Failed to parse log event', error)
    }
  }

  logStream.onerror = (error) => {
    console.error('Log stream error', error)
  }
})

onUnmounted(() => {
  logStream?.close()
  logStream = null
})
</script>

<template>
  <UCollapsible id="logs-panel" :open="props.logsOpen" :unmount-on-hide="false">
    <template #content>
      <div ref="logContainer" class="h-48 overflow-y-auto border-t border-default bg-black/60 px-3 py-2 font-data text-[11.5px] leading-relaxed">
        <div v-if="logs.length === 0" class="text-dimmed">
          Logs will appear here once <span class="italic">something happens</span>.
        </div>
        <div v-for="(log, index) in logs" :key="index" class="flex gap-2">
          <span class="shrink-0 text-dimmed">{{ formatLogTime(log.created) }}</span>
          <span class="shrink-0" :class="levelClass(log.level)">[{{ log.name }}]</span>
          <span class="min-w-0 flex-1 text-default">{{ log.msg }}</span>
          <span class="shrink-0 text-dimmed">{{ log.thread }}</span>
        </div>
      </div>
    </template>
  </UCollapsible>
</template>

<style>
#logs-panel {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 30px; /* matching h-48 */
}
</style>
