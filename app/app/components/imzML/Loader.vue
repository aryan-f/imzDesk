<script setup lang="ts">
const props = defineProps<{
  path: string
}>()

const emit = defineEmits<{
  ready: [path: string]
  failed: [error: unknown]
}>()

const running = ref(false)
const ready = ref(false)
const failed = ref(false)
const phase = ref('checking')
const progress = ref<number | null>(null)

let activeController: AbortController | null = null

const icon = computed(() => {
  if (ready.value) return 'i-lucide-check'
  if (failed.value) return 'i-lucide-circle-alert'
  if (running.value) return 'i-line-md-loading-twotone-loop'
  return 'i-line-md-loading-loop'
})

const color = computed(() => {
  if (ready.value) return 'success'
  if (failed.value) return 'error'
  return 'neutral'
})

const phaseLabel = computed(() => {
  if (phase.value === 'checking') return 'Checking for cached data...'
  if (phase.value === 'reading') return 'Parsing the .imzML file...'
  if (phase.value === 'indexing') return 'Indexing the spectra...'
  if (phase.value === 'processing') return 'Writing viewer data...'
  if (phase.value === 'sorting') return 'Sorting the values and saving...'
  if (phase.value === 'done') return 'Data is ready for viewing.'
  if (phase.value === 'failed') return 'Data preparation onFailed.'
  return 'Preparing file...'
})

watch(
  () => props.path,
  async (newPath, oldPath, onCleanup) => {
    activeController?.abort()

    const controller = new AbortController()
    activeController = controller
    onCleanup(() => controller.abort())

    running.value = false
    ready.value = false
    failed.value = false
    phase.value = 'checking'
    progress.value = null

    try {
      const converted = await $fetch<boolean>('/api/imzML/converted', {
        query: { path: props.path },
        signal: controller.signal,
      })

      if (converted) {
        ready.value = true
        phase.value = 'done'
        progress.value = 1
        emit('ready', props.path)
        return
      }

      running.value = true

      const query = new URLSearchParams({ path: props.path })
      const response = await fetch(`/api/imzML/convert?${query}`, {
        method: 'POST',
        signal: controller.signal,
      })

      if (!response.ok || !response.body) {
        throw new Error('Conversion request onFailed.')
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()

        if (done) break

        buffer += decoder.decode(value, { stream: true })

        const chunks = buffer.split(/\r?\n\r?\n/)
        buffer = chunks.pop() ?? ''

        for (const chunk of chunks) {
          let eventName = 'message'
          let data = ''

          for (const line of chunk.split(/\r?\n/)) {
            if (line.startsWith('event:')) eventName = line.slice('event:'.length).trim()
            if (line.startsWith('data:')) data += line.slice('data:'.length).trim()
          }

          if (!data) continue

          const payload = JSON.parse(data)

          if (payload.phase) phase.value = payload.phase
          if (payload.progress !== undefined) progress.value = payload.progress

          if (eventName === 'done') {
            running.value = false
            ready.value = true
            failed.value = false
            phase.value = 'done'
            progress.value = 1
            emit('ready', props.path)
            return
          }

          if (eventName === 'error') {
            throw new Error(payload.message ?? 'Conversion onFailed.')
          }
        }
      }
    } catch (error) {
      if (controller.signal.aborted) return

      running.value = false
      ready.value = false
      failed.value = true
      phase.value = 'failed'
      emit('failed', error)
    }
  },
  { immediate: true },
)
</script>

<template>
  <UPopover>
    <UButton :icon="icon" :color="color" variant="ghost" size="xs" square />
    <template #content>
      <div class="w-52 p-2.5 text-xs">
        <div class="font-bold">Preprocessing</div>
        <div class="mt-0.5 text-muted">{{ phaseLabel }}</div>
        <UProgress v-if="progress !== null && !ready && !failed" :model-value="Math.round(progress * 100)" size="xs" class="mt-2" />
      </div>
    </template>
  </UPopover>
</template>
