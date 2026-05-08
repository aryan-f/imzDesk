<script setup lang="ts">
// @ts-ignore
import Plotly from 'plotly.js-dist'

export type Selection = {
  id: string
  label: string
  type: 'rect'
  x0: number
  x1: number
  xref: 'x'
  y0: number
  y1: number
  yref: 'y'
  line?: {
    color?: string
    width?: number
    opacity?: number
  }
}

const props = defineProps<{
  mode: string
  loading: boolean
  data: number[][] | null
  height: number | null
  width: number | null
  display: {
    log1p: boolean
  }
  selections: Selection[]
}>()

const emit = defineEmits<{
  'update:selections': [regions: Selection[]]
}>()

const colorMode = useColorMode()

const container = ref<HTMLElement | null>(null)
const plot = ref<Plotly.PlotlyHTMLElement | null>(null)

const transformedData = computed(() => {
  if (!props.data) return null

  if (props.display.log1p)
    return props.data.map(row => row.map(value => Math.log10(value + 1)))

  return props.data
})

const annotations = computed(() => {
  return props.selections.map(selection => ({
    text: selection.label,
    x: Math.min(selection.x0, selection.x1),
    y: Math.max(selection.y0, selection.y1),
    xref: selection.xref,
    yref: selection.yref,
    showarrow: false,
    xanchor: 'left',
    yanchor: 'bottom',
    font: {
      color: 'white' // TODO: selection.line?.color
    }
  }))
})

const trace = computed(() => {
  if (!props.data) return []

  switch (props.mode) {
    case 'tic':
      return {
        type: 'heatmap',
        z: transformedData.value,
        hovertemplate: '(x:%{x}, y:%{y})<br>TIC=<b>%{z}</b>',
        showlegend: false,
        name: '',
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
  return {
    autosize: true,
    dragmode: 'zoom',
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
    selections: props.selections,
    annotations: annotations.value,
  }
})

const config = computed(() => {
  return {
    responsive: true,
    displaylogo: false,
    modeBarButtonsToRemove: ['lasso2d'],
  }
})

async function renderPlot() {
  if (!container.value || props.loading || !props.data) return

  const traces = [
    // We have to have an invisible plot that actually supports selection tools for them to show up.
    {
      type: 'scatter',
      x: [(props.width || 0) / 2],
      y: [(props.height || 0) / 2],
      marker: { size: 1 },
      hoverinfo: 'skip',
      opacity: 0
    },
    // We then layer the actual plot on top of it.
    trace.value,
  ]

  plot.value = await Plotly.react(container.value, traces, layout.value, config.value)

  plot.value.on('plotly_selected', () => emitSelections())
  plot.value.on('plotly_deselect', () => emitSelections())
}

function purgePlot() {
  if (container.value) {
    plot.value = null
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
    await nextTick()
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


function labelFromIndex(index: number) {
  let label = ''
  index += 1
  while (index > 0) {
    index--
    label = String.fromCharCode(65 + (index % 26)) + label
    index = Math.floor(index / 26)
  }
  return label
}

function emitSelections() {
  if (!plot.value) return

  const selections = plot.value.layout.selections ?? []

  const usedIds = selections
    .map((selection: Selection) => Number(selection.id))
    .filter((id: number) => Number.isInteger(id))

  let nextId = usedIds.length ? Math.max(...usedIds) + 1 : 0

  const update = selections.map((selection: any) => {
    const id = selection.id ?? nextId++
    return {
      ...selection,
      id: id,
      label: selection.label ?? labelFromIndex(id),
    }
  })

  emit('update:selections', update)
}

watch(
  () => props.selections,
  () => {
    if (!container.value) return
    Plotly.relayout(container.value, { selections: props.selections, annotations: annotations.value })
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
