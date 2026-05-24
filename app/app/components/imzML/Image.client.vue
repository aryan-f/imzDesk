<script setup lang="ts">
// @ts-ignore
import Plotly from 'plotly.js-dist'
import {type ImageResponse, type Selection} from '~/types/imzML'

const props = defineProps<{
  loading: boolean
  image: ImageResponse | null
  display: { }
  selections: Selection[]
}>()

const emit = defineEmits<{
  'update:selections': [regions: Selection[]]
}>()

const colorMode = useColorMode()

const container = ref<HTMLElement | null>(null)
const plot = ref<Plotly.PlotlyHTMLElement | null>(null)

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
      color: selection.line.color
    }
  }))
})

const imageTrace = computed(() => {
  if (!props.image) return null

  return {
    type: 'image',
    x0: props.image.origin[0],
    y0: props.image.origin[1],
    dx: props.image.delta[0],
    dy: props.image.delta[1],
    source: props.image.image,
    hovertemplate: '(x:%{x}, y:%{y})',
    showlegend: false,
    name: '',
  }
})

const colorbarTrace = computed(() => {
  if (!props.image?.colorbar) return null

  // Image traces don't support colorbars. We'll need a dummy trace to add that.
  return {
    type: 'heatmap',
    z: [[props.image.colorbar.cmin, props.image.colorbar.cmax]],
    x: [0, 1],
    y: [0],
    zmin: props.image.colorbar.cmin,
    zmax: props.image.colorbar.cmax,
    colorscale: props.image.colorbar.colorscale,
    showscale: true,
    hoverinfo: 'skip',
    opacity: 0,
    showlegend: false,
    colorbar: {
      title: '',
      tickmode: props.image.colorbar.tickmode,
      tickvals: props.image.colorbar.tickvals,
      ticktext: props.image.colorbar.ticktext,
      ticks: 'outside',
      thickness: 14,
      len: 0.85,
    },
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
    uirevision: true,
    margin: { t: 36, r: 90, b: 0, l: 45 },
    paper_bgcolor: theme.value.paper,
    plot_bgcolor: theme.value.plot,
    font: { color: theme.value.text },
    xaxis: {
      showgrid: false,
      zeroline: false,
      showline: false,
      ticks: 'outside',
      showticklabels: true,
      constrain: 'range',
      side: 'top',
    },
    yaxis: {
      showgrid: false,
      zeroline: false,
      showline: false,
      ticks: 'outside',
      showticklabels: true,
      scaleanchor: 'x',
      scaleratio: 1,
      constrain: 'range',
      autorange: 'reversed',
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
  if (!container.value || props.loading || !props.image) return

  const traces: any[] = [
    // We'll need another dummy trace for the selection tools to show up!
    {
      type: 'scatter',
      x: [(props.image.width || 0) / 2],
      y: [(props.image.height || 0) / 2],
      marker: { size: 1 },
      hoverinfo: 'skip',
      opacity: 0
    },
  ]

  if (imageTrace.value) {
    traces.push(imageTrace.value)
  }

  if (colorbarTrace.value) {
    traces.push(colorbarTrace.value)
  }

  plot.value = await Plotly.react(container.value, traces, layout.value, config.value)

  plot.value.on('plotly_selected', () => emitSelections())
  plot.value.on('plotly_deselect', () => emitSelections())
  // TODO: Generate pixel-size selections on plotly_click
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
  () => [props.image, props.loading],
  async () => {
    await nextTick()
    if (!props.image) {
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


let selectionColorHue = Math.random()

function randomSelectionColor(saturation = 75, lightness = 75) {
  selectionColorHue += 0.618033988749895  // golden ratio
  selectionColorHue %= 1
  return `hsl(${selectionColorHue * 360}, ${saturation}%, ${lightness}%)`
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
    const color = selection.line?.color ?? randomSelectionColor()
    return {
      ...selection,
      id: id,
      line: { dash: 'solid', color, width: 3 },
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
