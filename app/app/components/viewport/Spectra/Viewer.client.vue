<script setup lang="ts">
import Plotly from 'plotly.js-dist-min'
import type { Config, Data, Layout, PlotlyHTMLElement, PlotRelayoutEvent } from 'plotly.js'
import type { SelectedMSISpectrum } from '~/types/images'

const props = withDefaults(defineProps<{
  spectra: SelectedMSISpectrum[]
  loading?: boolean
  error?: string
}>(), {
  loading: false,
  error: '',
})

const emit = defineEmits<{
  close: []
  clear: []
  remove: [id: string]
  visibility: [id: string, visible: boolean]
}>()

type SpectrumNormalization = 'none' | 'tic' | 'rms' | 'median' | 'max'

const xRangeStep = 10
const normalization = ref<SpectrumNormalization>('none')
const normalizationOptions: Array<{ label: string, value: SpectrumNormalization }> = [
  { label: 'None', value: 'none' },
  { label: 'TIC', value: 'tic' },
  { label: 'RMS', value: 'rms' },
  { label: 'Median', value: 'median' },
  { label: 'Max', value: 'max' },
]
const popoverUi = { content: 'z-[1000]' }
const selectUi = { content: 'z-[1100]' }

const plotEl = ref<PlotlyHTMLElement | null>(null)
let resizeObserver: ResizeObserver | null = null
let renderQueue = Promise.resolve()
let plottedSpectrumIds = new Set<string>()
let hasManualXRange = false
let updatingPlot = false
let relayoutListenerAttached = false

function cssColor(name: string, fallback: string) {
  if (!plotEl.value) return fallback
  return getComputedStyle(plotEl.value).getPropertyValue(name).trim() || fallback
}

function normalizeIntensities(values: number[]): number[] {
  if (normalization.value === 'none' || !values.length) return values

  let normalizer: number
  if (normalization.value === 'tic') {
    normalizer = values.reduce((sum, value) => sum + value, 0)
  } else if (normalization.value === 'rms') {
    const squaredSum = values.reduce((sum, value) => sum + value * value, 0)
    normalizer = Math.sqrt(squaredSum / values.length)
  } else if (normalization.value === 'median') {
    const sorted = [...values].sort((left, right) => left - right)
    const middle = Math.floor(sorted.length / 2)
    normalizer = sorted.length % 2
      ? sorted[middle]!
      : (sorted[middle - 1]! + sorted[middle]!) / 2
  } else {
    normalizer = values.reduce((maximum, value) => Math.max(maximum, value), Number.NEGATIVE_INFINITY)
  }

  return normalizer > 0 ? values.map(value => value / normalizer) : values
}

function plotData(): Data[] {
  return props.spectra.map((spectrum, index) => ({
    type: 'scattergl',
    mode: 'lines',
    name: `${index + 1} · (${spectrum.coordinate.x}, ${spectrum.coordinate.y})`,
    x: spectrum.mz,
    y: normalizeIntensities(spectrum.intensities),
    visible: spectrum.visible ? true : 'legendonly',
    showlegend: false,
    line: {
      color: spectrum.color,
      width: 1,
    },
    hovertemplate: [
      `Spectrum ${index + 1}`,
      `Pixel (${spectrum.coordinate.x}, ${spectrum.coordinate.y})`,
      'm/z %{x:.6g}',
      'Intensity %{y:.6g}',
      '<extra></extra>',
    ].join('<br>'),
  }))
}

function automaticXRange(): [number, number] | undefined {
  let lower = Number.POSITIVE_INFINITY
  let upper = Number.NEGATIVE_INFINITY

  for (const spectrum of props.spectra) {
    for (const mz of spectrum.mz) {
      if (!Number.isFinite(mz)) continue
      lower = Math.min(lower, mz)
      upper = Math.max(upper, mz)
    }
  }

  if (!Number.isFinite(lower) || !Number.isFinite(upper)) return undefined
  lower = Math.floor(lower / xRangeStep) * xRangeStep
  upper = Math.ceil(upper / xRangeStep) * xRangeStep
  return [lower, upper > lower ? upper : lower + xRangeStep]
}

function plotLayout(): Partial<Layout> {
  const textColor = cssColor('--ui-text-muted', '#94a3b8')
  const gridColor = cssColor('--ui-border', '#334155')
  const visible = props.spectra.some(spectrum => spectrum.visible)
  return {
    autosize: true,
    margin: { l: 52, r: 16, t: 16, b: 36 },
    paper_bgcolor: 'rgba(0, 0, 0, 0)',
    plot_bgcolor: 'rgba(0, 0, 0, 0)',
    font: {
      color: textColor,
      family: 'ui-monospace, SFMono-Regular, Menlo, Consolas, monospace',
      size: 10,
    },
    hovermode: 'closest',
    dragmode: 'zoom',
    showlegend: false,
    uirevision: 'pixel-spectra',
    xaxis: {
      title: { text: 'm/z', font: { size: 10 }, standoff: 4 },
      color: textColor,
      gridcolor: gridColor,
      linecolor: gridColor,
      linewidth: 1,
      mirror: true,
      showline: true,
      zeroline: false,
      automargin: true,
    },
    yaxis: {
      title: { text: 'Intensity', font: { size: 10 }, standoff: 4 },
      color: textColor,
      gridcolor: gridColor,
      linecolor: gridColor,
      linewidth: 1,
      mirror: true,
      showline: true,
      rangemode: 'tozero',
      zeroline: false,
      automargin: true,
    },
    annotations: visible || !props.spectra.length
      ? []
      : [{
          text: 'No spectra selected',
          x: 0.5,
          y: 0.5,
          xref: 'paper',
          yref: 'paper',
          showarrow: false,
          font: { color: textColor, size: 11 },
        }],
  }
}

const plotConfig: Partial<Config> = {
  responsive: true,
  scrollZoom: true,
  displaylogo: false,
  modeBarButtonsToRemove: ['lasso2d', 'select2d'],
}

async function renderPlot() {
  await nextTick()
  if (!plotEl.value) return
  const spectrumIds = new Set(props.spectra.map(spectrum => spectrum.id))
  const spectrumAdded = [...spectrumIds].some(id => !plottedSpectrumIds.has(id))

  updatingPlot = true
  try {
    await Plotly.react(plotEl.value, plotData(), plotLayout(), plotConfig)
    if (!relayoutListenerAttached) {
      plotEl.value.on('plotly_relayout', recordManualXRange)
      relayoutListenerAttached = true
    }
    if (spectrumAdded && !hasManualXRange) {
      const range = automaticXRange()
      if (range) await Plotly.relayout(plotEl.value, { 'xaxis.range': range })
    }
  } finally {
    updatingPlot = false
    plottedSpectrumIds = spectrumIds
    if (!spectrumIds.size) hasManualXRange = false
  }
}

function queueRender() {
  renderQueue = renderQueue.then(renderPlot, renderPlot)
}

function setVisibility(id: string, value: boolean | 'indeterminate') {
  emit('visibility', id, value === true)
}

function recordManualXRange(event: PlotRelayoutEvent) {
  if (updatingPlot) return
  if (
    event['xaxis.range[0]'] !== undefined
    || event['xaxis.range[1]'] !== undefined
    || event['xaxis.autorange'] !== undefined
  ) {
    hasManualXRange = true
  }
}

watch(() => props.spectra, queueRender, { deep: true })
watch(normalization, queueRender)

onMounted(() => {
  resizeObserver = new ResizeObserver(() => {
    if (plotEl.value) Plotly.Plots.resize(plotEl.value)
  })
  if (plotEl.value) {
    resizeObserver.observe(plotEl.value)
  }
  queueRender()
})

onBeforeUnmount(() => {
  resizeObserver?.disconnect()
  if (plotEl.value) Plotly.purge(plotEl.value)
})
</script>

<template>
  <section class="flex h-56 shrink-0 flex-col border-t border-default bg-muted">
    <header class="flex h-9 shrink-0 items-center gap-2 border-b border-default px-3">
      <UIcon name="i-lucide-chart-no-axes-combined" class="size-4 text-secondary" />
      <span class="text-sm font-medium text-default">Spectra</span>
      <span class="font-data text-xs text-dimmed">{{ spectra.length }}</span>
      <UIcon v-if="loading" name="i-lucide-loader-circle" class="size-3.5 animate-spin text-secondary" />
      <span v-if="error" class="min-w-0 truncate text-xs text-error" :title="error">{{ error }}</span>
      <div class="flex-1" />
      <UPopover :ui="popoverUi">
        <UButton aria-label="Spectrum settings" icon="i-lucide-settings-2" color="neutral" variant="ghost" size="xs" square />
        <template #content>
          <div class="w-52 p-3">
            <UFormField label="Normalization" size="sm">
              <USelect v-model="normalization" :items="normalizationOptions" :ui="selectUi" class="w-full" />
            </UFormField>
          </div>
        </template>
      </UPopover>
      <UTooltip text="Clear spectra" :delay-duration="250">
        <UButton aria-label="Clear spectra" icon="i-lucide-trash-2" color="neutral" variant="ghost" size="xs" square :disabled="!spectra.length && !loading" @click="emit('clear')" />
      </UTooltip>
      <UTooltip text="Close spectrum viewer" :delay-duration="250">
        <UButton aria-label="Close spectrum viewer" icon="i-lucide-x" color="neutral" variant="ghost" size="xs" square @click="emit('close')" />
      </UTooltip>
    </header>
    <div class="grid min-h-0 flex-1 grid-cols-[minmax(0,1fr)_7rem]">
      <div class="relative min-w-0 overflow-hidden">
        <div ref="plotEl" class="absolute inset-0" />
      </div>
      <div class="overflow-y-auto border-l border-default py-1">
        <div v-for="(spectrum, index) in spectra" :key="spectrum.id" class="flex h-8 min-w-0 items-center gap-1.5 px-2 hover:bg-elevated" :title="`Native pixel (${spectrum.coordinate.x}, ${spectrum.coordinate.y})`">
          <UCheckbox :model-value="spectrum.visible" :ui="{ base: 'cursor-pointer' }" @update:model-value="setVisibility(spectrum.id, $event)" />
          <span class="size-2.5 shrink-0 rounded-sm" :style="{ backgroundColor: spectrum.color }" />
          <div class="min-w-0 flex-1 truncate font-data text-xs text-muted">
            {{ index + 1 }}
          </div>
          <UTooltip :text="`Remove spectrum ${index + 1}`" :delay-duration="250">
            <UButton :aria-label="`Remove spectrum ${index + 1}`" icon="i-lucide-x" color="neutral" variant="ghost" size="xs" square @click="emit('remove', spectrum.id)" />
          </UTooltip>
        </div>
      </div>
    </div>
  </section>
</template>
