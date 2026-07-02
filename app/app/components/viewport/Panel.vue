<script setup lang="ts">
import type OpenSeadragon from 'openseadragon'
import { type TileSource } from 'openseadragon'
import { type WSIMetadata } from '~/types/images'

const { state, setActive, closeFile } = useWorkspace()

const props = withDefaults(defineProps<{
  wsi?: string | null
  msi?: string | null
  other?: boolean
}>(), {
  wsi: null,
  msi: null,
  other: false,
})

const overlaid = computed(() => props.wsi && props.msi)

const annotationTools = [
  { label: 'Select', icon: 'i-lucide-mouse-pointer-2' },
  { label: 'Box', icon: 'i-lucide-square-dashed-mouse-pointer' },
  { label: 'Polygon', icon: 'i-lucide-pentagon' },
  { label: 'Freehand', icon: 'i-lucide-pencil-line' },
]

const activeAnnotationTool = ref('Select')
const isFullscreen = ref(false)

const viewerEl = ref<HTMLElement | null>(null)
const viewportEl = ref<HTMLElement | null>(null)

const loading = ref(true)
const viewerReady = ref(false)

const cropRect = ref<{ x: number, y: number, width: number, height: number } | null>(null)
const hasCrop = computed(() => cropRect.value !== null)
const cropEnabled = ref(true)

let osd: typeof OpenSeadragon | null = null
let viewer: OpenSeadragon.Viewer | null = null

function makeGetTileUrl(filepath: string) {
  return (level: number, x: number, y: number) => {
    const params = new URLSearchParams({
      filepath,
      level: String(level),
      column: String(x),
      row: String(y),
    })
    return `/api/images/wsi/tile?${params.toString()}`
  }
}

const meta = ref<WSIMetadata | null>(null)

const metadataLabel = computed(() => {
  if (!meta.value) return null

  return [
    meta.value.vendor ?? 'Unknown vendor',
    formatObjectivePower(meta.value.objective_power),
    formatMpp(meta.value.mpp),
    formatSize(meta.value.size),
  ].filter(Boolean).join(' · ')
})

function formatObjectivePower(value: number | undefined) {
  if (value === undefined || value === null) return null
  return `${Number(value.toFixed(2))}x`
}

function formatMpp(value: WSIMetadata['mpp']) {
  const x = Number(value.x.toFixed(2))
  const y = Number(value.y.toFixed(2))

  if (x === y) return `${x.toFixed(2)} µm/px`
  return `(${x.toFixed(2)} × ${y.toFixed(2)}) µm/px`
}

function formatSize(value: WSIMetadata['size'] | undefined) {
  if (!value) return null
  return `${value.x.toFixed(2)} × ${value.y.toFixed(2)} cm`
}

async function buildTileSource(filepath: string) {
  meta.value = await $fetch<WSIMetadata>('/api/images/wsi/metadata', {
    query: { filepath },
  })

  cropRect.value = meta.value.crop

  // A bare custom tile source: OSD derives level count from width/height the
  // same way DeepZoomGenerator does, so addressing lines up.
  return {
    width: meta.value.width,
    height: meta.value.height,
    tileSize: meta.value.tile_size,
    tileOverlap: meta.value.tile_overlap,
    getTileUrl: makeGetTileUrl(filepath),
  }
}

function fitToCrop(immediately = false) {
  if (!viewer || !osd || !cropRect.value) return
  const item = viewer.world.getItemAt(0)
  if (!item) return

  const c = cropRect.value
  const size = item.getContentSize()
  // Relative [0,1] -> image pixels -> viewport coords for fitBounds.
  const pixelRect = new osd.Rect(c.x * size.x, c.y * size.y, c.width * size.x, c.height * size.y)
  viewer.viewport.fitBounds(item.imageToViewportRectangle(pixelRect), immediately)
}

function resetView() {
  if (!viewer) return
  if (cropRect.value) {
    fitToCrop()
    return
  }
  viewer.viewport.goHome()
}

async function init() {
  if (!viewerEl.value) return
  if (!props.wsi) {
    loading.value = false
    return
  }

  loading.value = true

  try {
    if (!osd) osd = (await import('openseadragon')).default

    const filepath = `${state.value.dirpath}/${props.wsi}`
    const tileSource = await buildTileSource(filepath)

    viewer = osd({
      element: viewerEl.value,
      tileSources: [tileSource as unknown as TileSource],
      showNavigationControl: false,
      springStiffness: 12,
      animationTime: 0.4,
    })

    viewer.addHandler('open', () => {
      loading.value = false
      viewerReady.value = true
      applyCrop()
      fitToCrop(true)
    })

    // MSI layer will go here later:
    // viewer.addTiledImage({ tileSource: msiTileSource, opacity: 0.5 })
  } catch {
    loading.value = false
  }
}

function applyCrop() {
  if (!viewer || !osd) return
  const item = viewer.world.getItemAt(0)
  if (!item) return

  if (cropEnabled.value && cropRect.value) {
    const c = cropRect.value
    // Crop is stored as relative [0,1] values. setClip wants image pixels,
    // so scale by the tiled image's pixel dimensions. Camera doesn't move.
    const size = item.getContentSize()
    item.setClip(new osd.Rect(c.x * size.x, c.y * size.y, c.width * size.x, c.height * size.y))
  } else {
    item.setClip(null)
  }
}

function toggleCrop() {
  cropEnabled.value = !cropEnabled.value
  applyCrop()
}

function zoomBy(factor: number) {
  if (!viewer) return
  viewer.viewport.zoomBy(factor)
  viewer.viewport.applyConstraints()
}

async function toggleFullscreen() {
  const target = viewportEl.value
  if (!target) return

  if (document.fullscreenElement) {
    await document.exitFullscreen()
  } else {
    await target.requestFullscreen()
  }
}

function syncFullscreenState() {
  isFullscreen.value = document.fullscreenElement === viewportEl.value
}

function destroy() {
  if (viewer) {
    viewer.destroy()
    viewer = null
  }
  viewerReady.value = false
}

onMounted(() => {
  init()
  document.addEventListener('fullscreenchange', syncFullscreenState)
})

onBeforeUnmount(() => {
  destroy()
  document.removeEventListener('fullscreenchange', syncFullscreenState)
})

// Rebuild when the WSI file changes.
watch(() => props.wsi, () => {
  destroy()
  cropEnabled.value = false
  init()
})

function closeAll() {
  if (props.wsi) closeFile('WSI')
  if (props.msi) closeFile('MSI')
}
</script>

<template>
  <div :class="{ 'max-w-1/2': other, 'last:border-l': other }" class="relative flex flex-col flex-1 border-default">
    <div class="flex items-center bg-elevated px-3 py-1 text-base border-b border-default">
      <div v-if="wsi" class="flex truncate gap-2 cursor-pointer" @click="setActive('WSI')">
        <UBadge label="WSI" color="primary" variant="soft" class="px-1 py-px" />
        <div class="font-data text-sm truncate">
          {{ wsi }}
        </div>
      </div>
      <div v-if="overlaid">
        and
      </div>
      <div v-if="msi" class="flex truncate gap-2 cursor-pointer" @click="setActive('MSI')">
        <UBadge label="MSI" color="secondary" variant="soft" class="px-1 py-px" />
        <div class="font-data text-sm truncate">
          {{ msi }}
        </div>
      </div>
      <div class="flex-1" />
      <UButton
        icon="mdi-close"
        variant="ghost"
        color="error"
        size="xs"
        @click="closeAll"
      />
    </div>
    <div ref="viewportEl" class="relative flex-1 bg-default">
      <div ref="viewerEl" class="absolute inset-0" />
      <div v-if="wsi" class="pointer-events-none absolute inset-0 z-10">
        <div class="pointer-events-auto absolute inset-s-3 top-3 flex flex-col gap-1 rounded-md border border-default/80 bg-default/70 p-1 shadow-lg backdrop-blur-md">
          <UTooltip v-for="tool in annotationTools" :key="tool.label" :text="tool.label" :delay-duration="250">
            <UButton
              :icon="tool.icon"
              :color="activeAnnotationTool === tool.label ? 'primary' : 'neutral'"
              :variant="activeAnnotationTool === tool.label ? 'soft' : 'ghost'"
              size="sm"
              square
              @click="activeAnnotationTool = tool.label"
            />
          </UTooltip>
        </div>
        <template v-if="metadataLabel">
          <div class="absolute inset-s-1/2 top-3 max-w-[calc(100%-7rem)] -translate-x-1/2 truncate rounded-md border border-default/80 bg-default/70 px-3 py-1.5 font-data text-xs text-muted shadow-lg backdrop-blur-md">
            {{ metadataLabel }}
          </div>
        </template>
        <div class="pointer-events-auto absolute bottom-3 inset-s-3 flex flex-col gap-1 rounded-md border border-default/80 bg-default/70 p-1 shadow-lg backdrop-blur-md">
          <UTooltip text="Zoom in" :delay-duration="250">
            <UButton
              icon="i-lucide-plus"
              color="neutral"
              :disabled="!viewerReady"
              variant="ghost"
              size="sm"
              square
              @click="zoomBy(1.25)"
            />
          </UTooltip>
          <UTooltip text="Zoom out" :delay-duration="250">
            <UButton
              icon="i-lucide-minus"
              color="neutral"
              :disabled="!viewerReady"
              variant="ghost"
              size="sm"
              square
              @click="zoomBy(0.8)"
            />
          </UTooltip>
          <UTooltip text="Reset" :delay-duration="250">
            <UButton
              icon="i-lucide-house"
              color="neutral"
              :disabled="!viewerReady"
              variant="ghost"
              size="sm"
              square
              @click="resetView"
            />
          </UTooltip>
          <UTooltip :text="isFullscreen ? 'Exit full screen' : 'Full screen'" :delay-duration="250">
            <UButton
              :icon="isFullscreen ? 'i-lucide-minimize' : 'i-lucide-maximize'"
              color="neutral"
              variant="ghost"
              size="sm"
              square
              @click="toggleFullscreen"
            />
          </UTooltip>
        </div>
        <div class="pointer-events-auto absolute bottom-3 inset-s-1/2 flex -translate-x-1/2 rounded-md border border-default/80 bg-default/70 p-1 shadow-lg backdrop-blur-md">
          <UTooltip :text="cropEnabled ? 'Show full slide' : 'Show crop only'" :delay-duration="250">
            <UButton
              :icon="cropEnabled ? 'mdi-crop' : 'mdi-crop-free'"
              :color="cropEnabled ? 'primary' : 'neutral'"
              :disabled="!hasCrop"
              variant="ghost"
              size="sm"
              square
              @click="toggleCrop"
            />
          </UTooltip>
        </div>
      </div>
      <UIcon
        v-if="loading"
        name="i-lucide-loader-circle"
        class="absolute top-4 inset-e-4 size-4 animate-spin text-primary"
      />
      <div v-else-if="!wsi" class="absolute inset-0 flex items-center justify-center text-sm text-dimmed">
        No slide loaded
      </div>
    </div>
  </div>
</template>
