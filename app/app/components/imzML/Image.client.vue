<script setup lang="ts">
// @ts-ignore
import Plotly from 'plotly.js-dist'
import {type ImageResponse, type Selection} from '~/types/imzML'

const props = defineProps<{
  loading: boolean
  image: ImageResponse | null
  display: { log1p: boolean }
  selections: Selection[]
}>()

const emit = defineEmits<{
  'update:selections': [regions: Selection[]]
}>()

const colorMode = useColorMode()

const container = ref<HTMLElement | null>(null)
const plot = ref<Plotly.PlotlyHTMLElement | null>(null)

const transformedValues = computed(() => {
  if (!props.image) return null

  if (props.display.log1p)
    return props.image.values.map(row => row.map(value => Math.log10(value + 1)))

  return props.image.values
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
      color: selection.line.color
    }
  }))
})

const trace = computed(() => {
  if (!props.image) return []

  switch (props.image.mode) {
    case 'tic':
      return {
        type: 'heatmap',
        x: props.image.coords.x,
        y: props.image.coords.y,
        z: transformedValues.value,
        hovertemplate: '(x:%{x}, y:%{y})<br>TIC=<b>%{z}</b>',
        colorscale: 'Viridis',
        showlegend: false,
        name: '',
      }

    case 'ion':
      return {
        type: 'heatmap',
        x: props.image.coords.x,
        y: props.image.coords.y,
        z: transformedValues.value,
        hovertemplate: '(x:%{x}, y:%{y})<br>Intensity=<b>%{z}</b>',
        colorscale: 'Viridis',
        showlegend: false,
        name: '',
      }

    case 'pca':
      return {
        type: 'image',
        x0: props.image.coords.x[0],
        y0: props.image.coords.y[0],
        dx: 1,
        dy: 1,
        z: props.image.values.map((row: any) =>
          row.map((pixel: any) =>
            pixel.map((channel: number) => Math.round(channel * 255))
          )
        ),
        hovertemplate: '(x:%{x}, y:%{y})',
        showlegend: false,
        name: '',
      }

    case 'kmn':
      return {
        type: 'heatmap',
        x: props.image.coords.x,
        y: props.image.coords.y,
        z: props.image.values,
        hovertemplate: '(x:%{x}, y:%{y})<br>Cluster=<b>%{z}</b>',
        colorscale: 'Jet',
        showlegend: false,
        name: '',
      }

    default:
      return []
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
    margin: { t: 36, r: 0, b: 0, l: 40 },
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

  const traces = [
    // We have to have an invisible plot that actually supports selection tools for them to show up.
    {
      type: 'scatter',
      x: [(props.image.width || 0) / 2],
      y: [(props.image.height || 0) / 2],
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
