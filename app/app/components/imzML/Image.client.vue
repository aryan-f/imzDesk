<script setup lang="ts">
// @ts-ignore
import Plotly from 'plotly.js-dist'

const props = defineProps<{
  mode: string
  data: number[][] | null
  loading?: boolean
  display: {
    log1p: boolean
  }
}>()

const colorMode = useColorMode()

const container = ref<HTMLElement | null>(null)

const transformedData = computed(() => {
  if (!props.data) return null

  if (props.display.log1p)
    return props.data.map(row => row.map(value => Math.log10(value + 1)))

  return props.data
})

const trace = computed(() => {
  if (!props.data) return []

  switch (props.mode) {
    case 'tic':
      return {
        type: 'heatmap',
        z: transformedData.value,
      }
  }
})

const theme = computed(() => {
  const isDark = colorMode.value === 'dark'
  return {
    text: isDark ? '#e5e7eb' : '#111827',
    paper: 'rgba(0,0,0,0)',  // transparent
    plot: 'rgba(0,0,0,0)',  // transparent
  }
})

const layout = computed(() => {
  // noinspection SpellCheckingInspection
  return {
    autosize: true,
    margin: { t: 0, r: 0, b: 36, l: 40 },
    paper_bgcolor: theme.value.paper,
    plot_bgcolor: theme.value.plot,
    font: {
      color: theme.value.text,
    },
    xaxis: {
      showgrid: false,
      zeroline: false,
      showline: false,
      ticks: 'outside',
      showticklabels: true,
    },
    yaxis: {
      showgrid: false,
      zeroline: false,
      showline: false,
      ticks: 'outside',
      showticklabels: true,
      scaleanchor: 'x',
      scaleratio: 1,
    },
  }
})

const config = computed(() => {
  // noinspection SpellCheckingInspection
  return {
    displaylogo: false,
    responsive: true,
  }
})

async function renderPlot() {
  if (!container.value || props.loading || !props.data) return

  await Plotly.react(
    container.value,
    [trace.value],
    layout.value,
    config.value,
  )
}

function purgePlot() {
  if (container.value) {
    Plotly.purge(container.value)
  }
}

onMounted(async () => {
  await nextTick()
  await renderPlot()
})

onBeforeUnmount(() => {
  purgePlot()
})


watch(
  () => [props.mode, props.loading],
  async () => {
    await nextTick()
    if (!props.data) {
      purgePlot()
      return
    }
    await renderPlot()
  },
  { immediate: true }
)

watch(
  () => props.display,
  async () => {
    await renderPlot()
  },
  { deep: true }
)

watch(
  () => colorMode.value,
  async () => {
    await nextTick()
    await renderPlot()
  }
)
</script>

<template>
  <div class="h-full w-full">
    <USkeleton v-if="loading" class="h-full w-full" />
    <ClientOnly v-else>
      <div ref="container" class="h-full w-full" />
    </ClientOnly>
  </div>
</template>
