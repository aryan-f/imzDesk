<script setup lang="ts">
import type OpenSeadragon from 'openseadragon'
import type { TileSource } from 'openseadragon'
import type { MSIDisplay, MSIMetadata, WSIMetadata } from '~/types/images'

const { state, setActive, closeFile } = useWorkspace()

const props = withDefaults(defineProps<{
  wsi?: string | null
  msi?: string | null
  displayWsi?: boolean
  displayMsi?: boolean
  registered?: boolean
  other?: boolean
  overlay?: boolean
}>(), {
  wsi: null,
  msi: null,
  displayWsi: false,
  displayMsi: false,
  registered: false,
  other: false,
  overlay: false,
})

const emit = defineEmits<{
  'update:registered': [value: boolean]
  'update:overlay': [value: boolean]
}>()

const showWsi = computed(() => Boolean(props.wsi && props.displayWsi))
const showMsi = computed(() => Boolean(props.msi && props.displayMsi))
const overlaid = computed(() => showWsi.value && showMsi.value)
const canRegister = computed(() => Boolean(msiFilepath.value && fixedWsiFilepath.value))
const canOverlay = computed(() => Boolean(props.msi && props.wsi && props.registered))

const annotationTools = [
  { label: 'Select', icon: 'i-lucide-mouse-pointer-2' },
  { label: 'Box', icon: 'i-lucide-square-dashed-mouse-pointer' },
  { label: 'Polygon', icon: 'i-lucide-pentagon' },
  { label: 'Freehand', icon: 'i-lucide-pencil-line' },
]

const activeAnnotationTool = ref('Select')
const isFullscreen = ref(false)
const msiImageUrl = ref<string | null>(null)
const msiRendering = ref(false)
const msiOpacity = ref(0.65)
const registrationMatrix = ref<number[][] | null>(null)
const registering = ref(false)

const viewerEl = ref<HTMLElement | null>(null)
const viewportEl = ref<HTMLElement | null>(null)

const wsiLoading = ref(showWsi.value)
const viewerReady = ref(false)

const cropRect = ref<{ x: number, y: number, width: number, height: number } | null>(null)
const hasCrop = computed(() => cropRect.value !== null)
const cropEnabled = ref(true)

const msiDisplay = ref<MSIDisplay>({
  preprocessing: {
    normalization: 'none',
    centroiding: 'none',
    baselineCorrection: false,
    smoothing: false,
  },
  cubing: {
    method: 'bin',
    mzMin: 50,
    mzMax: 1000,
    binWidth: 0.1,
    model: 'roman-bushuiev/DreaMS',
  },
  reduction: {
    method: 'tic',
    components: 1,
    scaling: 'robust',
    colormap: 'viridis',
  },
})

let osd: typeof OpenSeadragon | null = null
let viewer: OpenSeadragon.Viewer | null = null
let wsiImageLayer: OpenSeadragon.TiledImage | null = null
let msiImageLayer: OpenSeadragon.TiledImage | null = null
let msiRenderTimer: ReturnType<typeof setTimeout> | null = null

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

const msiFilepath = computed(() => {
  if (!props.msi || !props.displayMsi) return null
  return `${state.value.dirpath}/${props.msi}`
})

const wsiFilepath = computed(() => {
  if (!props.wsi || !props.displayWsi) return null
  return `${state.value.dirpath}/${props.wsi}`
})

const fixedWsiFilepath = computed(() => {
  if (props.wsi) return `${state.value.dirpath}/${props.wsi}`
  return null
})

const wsiMeta = ref<WSIMetadata | null>(null)
const msiMeta = ref<MSIMetadata | null>(null)

const metadataLabel = computed(() => {
  if (wsiMeta.value) {
    return [
      wsiMeta.value.vendor ?? 'Unknown vendor',
      formatObjectivePower(wsiMeta.value.objective_power),
      formatMpp(wsiMeta.value.mpp),
      formatSize(wsiMeta.value.size),
    ].filter(Boolean).join(' · ')
  }

  const msiLabel = [
    formatMpp(msiMeta.value?.mpp),
    formatSize(msiMeta.value?.size),
  ].filter(Boolean).join(' · ')

  return msiLabel || null
})

function formatObjectivePower(value: number | undefined) {
  if (value === undefined || value === null) return null
  return `${Number(value.toFixed(2))}x`
}

function formatMpp(value: WSIMetadata['mpp'] | MSIMetadata['mpp'] | undefined) {
  if (!value) return null
  const x = Number(value.x.toFixed(2))
  const y = Number(value.y.toFixed(2))

  if (x === y) return `${x.toFixed(2)} µm/px`
  return `(${x.toFixed(2)} × ${y.toFixed(2)}) µm/px`
}

function formatSize(value: WSIMetadata['size'] | MSIMetadata['size'] | undefined) {
  if (!value) return null
  return `${value.x.toFixed(2)} × ${value.y.toFixed(2)} cm`
}

async function buildTileSource(filepath: string) {
  wsiMeta.value = await $fetch<WSIMetadata>('/api/images/wsi/metadata', {
    query: { filepath },
  })

  cropRect.value = wsiMeta.value.crop

  // A bare custom tile source: OSD derives level count from width/height the
  // same way DeepZoomGenerator does, so addressing lines up.
  return {
    width: wsiMeta.value.width,
    height: wsiMeta.value.height,
    tileSize: wsiMeta.value.tile_size,
    tileOverlap: wsiMeta.value.tile_overlap,
    getTileUrl: makeGetTileUrl(filepath),
  }
}

async function loadMsiMetadata() {
  if (!msiFilepath.value) {
    msiMeta.value = null
    return
  }
  msiMeta.value = await $fetch<MSIMetadata>('/api/images/msi/metadata', {
    query: { filepath: msiFilepath.value },
  })
}

function registrationRequestParams() {
  if (!msiFilepath.value || !fixedWsiFilepath.value) return null
  return {
    filepath: msiFilepath.value,
    reference: fixedWsiFilepath.value,
  }
}

async function checkRegistration() {
  const query = registrationRequestParams()
  if (!query) {
    emit('update:registered', false)
    registrationMatrix.value = null
    return
  }
  const registered = await $fetch<boolean>('/api/images/msi/registered', {
    query,
  })
  emit('update:registered', registered)
  if (!registered) registrationMatrix.value = null
}

async function loadRegistrationMatrix() {
  const query = registrationRequestParams()
  if (!query || !props.registered) {
    registrationMatrix.value = null
    return null
  }
  registrationMatrix.value = await $fetch<number[][] | null>('/api/images/msi/registered/transform', {
    query,
  })
  return registrationMatrix.value
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

async function initWsiLayer() {
  if (!viewer || !wsiFilepath.value) {
    wsiLoading.value = false
    return
  }
  wsiLoading.value = true
  const tileSource = await buildTileSource(wsiFilepath.value)
  viewer.addTiledImage({
    tileSource: tileSource as unknown as TileSource,
    index: 0,
    success: (event) => {
      wsiImageLayer = (event as unknown as { item: OpenSeadragon.TiledImage }).item
      wsiLoading.value = false
      viewerReady.value = true
      applyCrop()
      fitToCrop(true)
    },
  })
}

function destroyWsiLayer() {
  if (viewer && wsiImageLayer) {
    viewer.world.removeItem(wsiImageLayer)
  }
  wsiImageLayer = null
  wsiMeta.value = null
  cropRect.value = null
  wsiLoading.value = false
}

function releaseMsiImage() {
  if (viewer && msiImageLayer) {
    viewer.world.removeItem(msiImageLayer)
    msiImageLayer = null
  }
  if (!msiImageUrl.value) return
  URL.revokeObjectURL(msiImageUrl.value)
  msiImageUrl.value = null
}

function displayMsiImage(url: string) {
  if (!viewer) return
  const currentViewer = viewer
  if (msiImageLayer) {
    currentViewer.world.removeItem(msiImageLayer)
    msiImageLayer = null
  }
  currentViewer.addTiledImage({
    tileSource: {
      type: 'image',
      url,
    } as unknown as TileSource,
    index: showWsi.value ? 1 : currentViewer.world.getItemCount(),
    success: (event) => {
      msiImageLayer = (event as unknown as { item: OpenSeadragon.TiledImage }).item
      applyMsiLayerTransform()
      if (!showWsi.value) {
        viewerReady.value = true
        currentViewer.viewport.goHome(true)
      }
    },
  })
}

function applyMsiLayerTransform() {
  if (!viewer || !osd || !msiImageLayer) return
  msiImageLayer.setOpacity(overlaid.value ? msiOpacity.value : 1)
  if (!overlaid.value || !registrationMatrix.value || !wsiImageLayer || !wsiMeta.value || !msiMeta.value?.mpp) return

  const matrix = registrationMatrix.value
  const row0 = matrix[0]
  const row1 = matrix[1]
  if (!row0 || !row1) return
  const xScale = msiMeta.value.mpp.x / wsiMeta.value.mpp.x
  const yScale = msiMeta.value.mpp.y / wsiMeta.value.mpp.y
  const a = (row0[0] ?? 1) * xScale
  const b = (row0[1] ?? 0) * xScale
  const c = (row0[2] ?? 0) * xScale
  const d = (row1[0] ?? 0) * yScale
  const e = (row1[1] ?? 1) * yScale
  const f = (row1[2] ?? 0) * yScale
  const origin = wsiImageLayer.imageToViewportCoordinates(new osd.Point(c, f))
  const xAxis = wsiImageLayer.imageToViewportCoordinates(new osd.Point(c + a, f + d))
  const yAxis = wsiImageLayer.imageToViewportCoordinates(new osd.Point(c + b, f + e))
  const width = Math.hypot(xAxis.x - origin.x, xAxis.y - origin.y) * msiImageLayer.getContentSize().x
  const height = Math.hypot(yAxis.x - origin.x, yAxis.y - origin.y) * msiImageLayer.getContentSize().y
  const angle = Math.atan2(d, a) * 180 / Math.PI
  const angleRadians = angle * Math.PI / 180
  const halfWidth = width / 2
  const halfHeight = height / 2
  const rotatedHalf = new osd.Point(
    halfWidth * Math.cos(angleRadians) - halfHeight * Math.sin(angleRadians),
    halfWidth * Math.sin(angleRadians) + halfHeight * Math.cos(angleRadians),
  )
  const position = new osd.Point(
    origin.x - halfWidth + rotatedHalf.x,
    origin.y - halfHeight + rotatedHalf.y,
  )

  msiImageLayer.setPosition(position, true)
  msiImageLayer.setWidth(width, true)
  msiImageLayer.setRotation(angle, true)
}

async function renderMsiImage() {
  if (!msiFilepath.value) return

  msiRendering.value = true
  if (overlaid.value) await loadRegistrationMatrix()
  const response = await $fetch<Blob>('/api/images/msi/image', {
    method: 'POST',
    body: {
      filepath: msiFilepath.value,
      registered: props.registered,
      preprocessing: msiDisplay.value.preprocessing,
      cubing: msiDisplay.value.cubing,
      reduction: msiDisplay.value.reduction,
    },
    responseType: 'blob',
  })

  const imageUrl = URL.createObjectURL(response)
  releaseMsiImage()
  msiImageUrl.value = imageUrl
  displayMsiImage(imageUrl)
  msiRendering.value = false
}

function queueMsiImageRender() {
  if (msiRenderTimer) clearTimeout(msiRenderTimer)
  if (!msiFilepath.value) {
    releaseMsiImage()
    msiRendering.value = false
    return
  }
  msiRendering.value = true
  msiRenderTimer = setTimeout(() => {
    msiRenderTimer = null
    renderMsiImage().finally(() => {
      if (!msiRenderTimer) msiRendering.value = false
    })
  }, 250)
}

function cancelMsiImageRender() {
  if (msiRenderTimer) {
    clearTimeout(msiRenderTimer)
    msiRenderTimer = null
    msiRendering.value = false
  }
}

async function initMsiLayer() {
  if (!msiFilepath.value) {
    destroyMsiLayer()
    return
  }
  await loadMsiMetadata()
  await checkRegistration()
  queueMsiImageRender()
}

function destroyMsiLayer() {
  cancelMsiImageRender()
  releaseMsiImage()
  msiMeta.value = null
  registrationMatrix.value = null
}

function applyMsiDisplay(display: MSIDisplay) {
  msiDisplay.value = display
  queueMsiImageRender()
}

async function init() {
  if (!viewerEl.value) return

  try {
    if (!osd) osd = (await import('openseadragon')).default

    viewer = osd({
      element: viewerEl.value,
      tileSources: [],
      showNavigationControl: false,
      springStiffness: 12,
      animationTime: 0.4,
    })

    await initWsiLayer()
    await initMsiLayer()
  } catch {
    wsiLoading.value = false
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

function toggleOverlay() {
  if (!canOverlay.value) return
  emit('update:overlay', !props.overlay)
}

async function registerMsi() {
  if (!msiFilepath.value || !fixedWsiFilepath.value) return
  registering.value = true
  try {
    const registered = await $fetch<boolean>('/api/images/msi/register', {
      method: 'POST',
      body: {
        filepath: msiFilepath.value,
        reference: fixedWsiFilepath.value,
      },
    })
    emit('update:registered', registered)
  } finally {
    registering.value = false
  }
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
  destroyWsiLayer()
  destroyMsiLayer()
  if (viewer) {
    viewer.destroy()
    viewer = null
  }
  wsiImageLayer = null
  msiImageLayer = null
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

watch(() => [props.wsi, props.msi, props.displayWsi, props.displayMsi], () => {
  destroy()
  cropEnabled.value = false
  init()
})

watch(msiOpacity, () => {
  applyMsiLayerTransform()
})

function closeAll() {
  if (showWsi.value) closeFile('WSI')
  if (showMsi.value) closeFile('MSI')
}
</script>

<template>
  <div :class="{ 'max-w-1/2': other, 'last:border-l': other }" class="relative flex flex-col flex-1 border-default">
    <div class="flex items-center bg-elevated px-3 py-1 text-base border-b border-default">
      <div v-if="showWsi" class="flex truncate gap-2 cursor-pointer" @click="setActive('WSI')">
        <UBadge label="WSI" color="primary" variant="soft" class="px-1 py-px" />
        <div class="font-data text-sm truncate">
          {{ wsi }}
        </div>
      </div>
      <div v-if="overlaid">
        and
      </div>
      <div v-if="showMsi" class="flex truncate gap-2 cursor-pointer" @click="setActive('MSI')">
        <UBadge label="MSI" color="secondary" variant="soft" class="px-1 py-px" />
        <div class="font-data text-sm truncate">
          {{ msi }}
        </div>
      </div>
      <div class="flex-1" />
      <ViewportDisplayMSI v-if="showMsi" :display="msiDisplay" :loading="msiRendering" @apply="applyMsiDisplay" />
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
      <div v-if="showWsi || showMsi" class="pointer-events-none absolute inset-0 z-10">
        <div class="pointer-events-auto absolute top-3 flex flex-col gap-1 rounded-md border border-default/80 bg-default/70 p-1 shadow-lg backdrop-blur-md" :class="showWsi ? 'inset-s-3' : 'inset-e-3'">
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
        <div class="pointer-events-auto absolute bottom-3 flex flex-col gap-1 rounded-md border border-default/80 bg-default/70 p-1 shadow-lg backdrop-blur-md" :class="showWsi ? 'inset-s-3' : 'inset-e-3'">
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
        <div v-if="showWsi || showMsi" class="pointer-events-auto absolute bottom-3 inset-s-1/2 flex -translate-x-1/2 gap-1 rounded-md border border-default/80 bg-default/70 p-1 shadow-lg backdrop-blur-md">
          <UTooltip v-if="showWsi" :text="cropEnabled ? 'Show full slide' : 'Show crop only'" :delay-duration="250">
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
          <UTooltip v-if="showMsi" text="Register" :delay-duration="250">
            <UButton
              icon="mdi-resize"
              :color="registered ? 'secondary' : 'neutral'"
              :disabled="!canRegister || registering"
              :loading="registering"
              :variant="registered ? 'soft' : 'ghost'"
              size="sm"
              square
              @click="registerMsi"
            />
          </UTooltip>
          <UTooltip v-if="showMsi" :text="overlay ? 'Show separately' : 'Overlay'" :delay-duration="250">
            <UButton
              icon="carbon-overlay"
              :color="overlay ? 'secondary' : 'neutral'"
              :disabled="!canOverlay"
              :variant="overlay ? 'soft' : 'ghost'"
              size="sm"
              square
              @click="toggleOverlay"
            />
          </UTooltip>
          <div v-if="overlaid" class="flex w-28 items-center gap-2 px-1">
            <UIcon name="i-lucide-blend" class="size-4 text-dimmed" />
            <USlider v-model="msiOpacity" :min="0" :max="1" :step="0.05" color="secondary" />
          </div>
        </div>
      </div>
      <UIcon
        v-if="wsiLoading || msiRendering"
        name="i-lucide-loader-circle"
        class="absolute bottom-4 size-4 animate-spin text-primary"
        :class="showWsi ? 'inset-e-4' : 'inset-s-4'"
      />
    </div>
  </div>
</template>
