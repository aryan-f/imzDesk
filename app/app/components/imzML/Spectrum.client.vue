<script setup lang="ts">
// @ts-ignore
import Plotly from 'plotly.js-dist'
import {type Selection} from '~/types/imzML'

const props = defineProps<{
  path: string
  ready: boolean
  selections: Selection[]
}>()

const loading = ref<boolean>(true)

const colorMode = useColorMode()
const isDark = computed(() => colorMode.value === 'dark')

const container = ref<HTMLElement | null>(null)

type SpectrumResponse = {
  mz: number[]
  intensity: number[]
}

type SpectrumRequest = {
  x_min?: number
  x_max?: number
  y_min?: number
  y_max?: number
}

type Spectrum = {
  id: string
  label: string
  color?: string
  opacity?: number
  requestKey?: string
  x: number[]
  y: number[]
}

const fullImageSpectrum = ref<Spectrum | null>(null)
const selectionSpectra = ref<Record<string, Spectrum>>({})

// Tracks the latest in-flight request per selection to avoid duplicate or stale updates.
const pendingSelectionRequests = new Map<string, string>()

// Guards against old full-values requests overwriting newer results after path/ready changes.
let fullImageFetchVersion = 0

function boundsFromSelection(selection: Selection): SpectrumRequest {
  return {
    x_min: Math.min(selection.x0, selection.x1),
    x_max: Math.max(selection.x0, selection.x1),
    y_min: Math.min(selection.y0, selection.y1),
    y_max: Math.max(selection.y0, selection.y1),
  }
}

// Cache key includes path and bounds so moved/resized selections refetch their spectra.
function requestKeyFromSelection(selection: Selection) {
  const bounds = boundsFromSelection(selection)
  return [
    props.path,
    bounds.x_min,
    bounds.x_max,
    bounds.y_min,
    bounds.y_max,
  ].join(':')
}

async function fetchSpectrum(body?: SpectrumRequest) {
  return await $fetch<SpectrumResponse>('/api/imzML/spectrum', {
    method: 'POST',
    query: { path: props.path },
    body,
  })
}

async function fetchFullImageSpectrum() {
  if (!props.ready) return

  const version = ++fullImageFetchVersion

  // Only the full-values spectrum controls the visible loading state.
  loading.value = true

  try {
    const spectrum = await fetchSpectrum()

    if (version !== fullImageFetchVersion) return

    fullImageSpectrum.value = {
      id: 'full-values',
      label: 'Image',
      x: spectrum.mz,
      y: spectrum.intensity,
    }
  } finally {
    if (version === fullImageFetchVersion) {
      loading.value = false

      await nextTick()
      await renderPlot()
    }
  }
}

async function fetchSelectionSpectrum(selection: Selection) {
  if (!props.ready) return

  // Capture path/request state so late responses can be ignored safely.
  const pathAtRequest = props.path
  const requestKey = requestKeyFromSelection(selection)
  const body = boundsFromSelection(selection)

  pendingSelectionRequests.set(selection.id, requestKey)

  try {
    const spectrum = await fetchSpectrum(body)

    if (props.path !== pathAtRequest) return
    if (pendingSelectionRequests.get(selection.id) !== requestKey) return

    // Selection may have been deleted or resized while the request was in flight.
    const currentSelection = props.selections.find(item => item.id === selection.id)

    if (!currentSelection) return
    if (requestKeyFromSelection(currentSelection) !== requestKey) return

    selectionSpectra.value = {
      ...selectionSpectra.value,
      [currentSelection.id]: {
        id: currentSelection.id,
        label: currentSelection.label,
        color: currentSelection.line.color,
        opacity: currentSelection.line.opacity,
        x: spectrum.mz,
        y: spectrum.intensity,
        requestKey,
      },
    }

    await nextTick()
    await renderPlot()
  } finally {
    if (pendingSelectionRequests.get(selection.id) === requestKey) {
      pendingSelectionRequests.delete(selection.id)
    }
  }
}

async function syncSelectionSpectra() {
  if (!props.ready) return

  // Keep only cached spectra that still match the current selections.
  const nextSelectionSpectra: Record<string, Spectrum> = {}

  for (const selection of props.selections) {
    const requestKey = requestKeyFromSelection(selection)
    const existingSpectrum = selectionSpectra.value[selection.id]

    if (existingSpectrum?.requestKey === requestKey) {
      // Metadata changes should update the trace without refetching spectrum values.
      nextSelectionSpectra[selection.id] = {
        ...existingSpectrum,
        label: selection.label,
        color: selection.line.color,
        opacity: selection.line.opacity,
      }
    }
  }

  selectionSpectra.value = nextSelectionSpectra

  await nextTick()
  await renderPlot()

  // Fetch spectra only for selections without a valid cached or pending request.
  for (const selection of props.selections) {
    const requestKey = requestKeyFromSelection(selection)
    const existingSpectrum = selectionSpectra.value[selection.id]

    if (existingSpectrum?.requestKey === requestKey) continue
    if (pendingSelectionRequests.get(selection.id) === requestKey) continue

    void fetchSelectionSpectrum(selection)
  }
}

const traces = computed(() => {
  const orderedSpectra = [
    ...(fullImageSpectrum.value ? [fullImageSpectrum.value] : []),
    ...props.selections
      .map(selection => selectionSpectra.value[selection.id])
      .filter((spectrum): spectrum is Spectrum => Boolean(spectrum)),
  ]

  return orderedSpectra.map((spectrum) => {
    const isFullImage = spectrum.id === 'full-values'

    return {
      x: spectrum.x,
      y: spectrum.y,
      type: 'bar',
      name: spectrum.label,
      marker: {
        color: isFullImage
          ? isDark.value
            ? 'rgba(229, 231, 235, 0.45)'
            : 'rgba(17, 24, 39, 0.35)'
          : spectrum.color,
      },
      opacity: isFullImage ? 0.55 : spectrum.opacity ?? 1,
      hovertemplate: [
        'm/z: %{x}',
        'Intensity: %{y:.2f}%',
        '<extra>%{fullData.name}</extra>',
      ].join('<br>'),
    }
  })
})

const theme = computed(() => {
  return {
    text: isDark.value ? '#e5e7eb' : '#111827',
    paper: 'rgba(0,0,0,0)',
    plot: 'rgba(0,0,0,0)',
    grid: isDark.value ? 'rgba(255,255,255,0.10)' : 'rgba(0,0,0,0.10)',
    axis: isDark.value ? 'rgba(255,255,255,0.18)' : 'rgba(0,0,0,0.18)',
    spike: isDark.value ? 'rgba(255,255,255,0.75)' : 'rgba(0,0,0,0.75)',
  }
})

const layout = computed(() => {
  return {
    autosize: true,
    dragmode: 'zoom',
    uirevision: 'keep-zoom',
    barmode: 'overlay',
    margin: { t: 16, r: 16, b: 36, l: 54 },
    paper_bgcolor: theme.value.paper,
    plot_bgcolor: theme.value.plot,
    font: {
      color: theme.value.text,
    },
    xaxis: {
      title: { text: 'm/z' },
      mirror: true,
      fixedrange: false,
      gridcolor: theme.value.grid,
      linecolor: theme.value.axis,
      zerolinecolor: theme.value.axis,
      spikemode: 'across',
      spikecolor: theme.value.spike,
    },
    yaxis: {
      title: { text: 'Relative Intensity' },
      mirror: true,
      fixedrange: true,
      gridcolor: theme.value.grid,
      linecolor: theme.value.axis,
      zerolinecolor: theme.value.axis,
    },
  }
})

const config = computed(() => {
  return {
    responsive: true,
    displaylogo: false,
    scrollZoom: true,
    modeBarButtonsToRemove: [
      'select2d',
      'lasso2d',
    ],
  }
})

async function renderPlot() {
  if (!container.value) return

  await Plotly.react(
    container.value,
    traces.value,
    layout.value,
    config.value
  )
}

function purgePlot() {
  if (container.value) {
    Plotly.purge(container.value)
  }
}

onMounted(async () => {
  await nextTick()

  if (!props.ready) return

  void fetchFullImageSpectrum()
  void syncSelectionSpectra()
})

onBeforeUnmount(() => {
  purgePlot()
})

watch(
  () => props.ready,
  async () => {
    if (!props.ready) {
      loading.value = true
      return
    }

    void fetchFullImageSpectrum()
    void syncSelectionSpectra()
  }
)

watch(
  () => props.path,
  async () => {
    // A new file invalidates all spectra and pending selection requests.
    fullImageFetchVersion++

    fullImageSpectrum.value = null
    selectionSpectra.value = {}
    pendingSelectionRequests.clear()

    loading.value = props.ready

    await nextTick()
    await renderPlot()

    if (!props.ready) return

    void fetchFullImageSpectrum()
    void syncSelectionSpectra()
  }
)

watch(
  () => props.selections,
  async () => {
    await syncSelectionSpectra()
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
  <div class="relative h-full w-full">
    <ClientOnly v-if="traces.length">
      <div ref="container" class="h-full w-full" />
    </ClientOnly>
    <USkeleton v-if="loading" class="absolute inset-0 h-full w-full" />
  </div>
</template>
