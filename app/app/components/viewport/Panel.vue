<script setup lang="ts">
import type OpenSeadragon from 'openseadragon'
import type { TileSource } from 'openseadragon'
import type { MSIDisplay, MSIMetadata, WSIMetadata } from '~/types/images'

type CropRect = { x: number, y: number, width: number, height: number }
type CropHandle = 'move' | 'n' | 's' | 'e' | 'w' | 'nw' | 'ne' | 'sw' | 'se'

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

const cropRect = ref<CropRect | null>(null)
const hasCrop = computed(() => cropRect.value !== null)
const cropEnabled = ref(true)
const cropEditing = ref(false)
const cropSaving = ref(false)
const cropDraft = ref<CropRect | null>(null)
const cropOverlayRect = ref<{ left: number, top: number, width: number, height: number } | null>(null)
const cropHandleClass = 'absolute size-3 rounded-full border border-primary bg-default shadow'
const cropHandles: { handle: CropHandle, class: string }[] = [
  { handle: 'nw', class: '-left-1.5 -top-1.5 cursor-nwse-resize' },
  { handle: 'n', class: 'left-1/2 -top-1.5 -translate-x-1/2 cursor-ns-resize' },
  { handle: 'ne', class: '-right-1.5 -top-1.5 cursor-nesw-resize' },
  { handle: 'e', class: '-right-1.5 top-1/2 -translate-y-1/2 cursor-ew-resize' },
  { handle: 'se', class: '-bottom-1.5 -right-1.5 cursor-nwse-resize' },
  { handle: 's', class: '-bottom-1.5 left-1/2 -translate-x-1/2 cursor-ns-resize' },
  { handle: 'sw', class: '-bottom-1.5 -left-1.5 cursor-nesw-resize' },
  { handle: 'w', class: '-left-1.5 top-1/2 -translate-y-1/2 cursor-ew-resize' },
]

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
    binWidth: 1,
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
let cropDrag: {
  handle: CropHandle
  pointerId: number
  startX: number
  startY: number
  startRect: { left: number, top: number, width: number, height: number }
} | null = null

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
  wsiMeta.value = await $fetch<WSIMetadata>('/api/images/metadata/all', {
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
  msiMeta.value = await $fetch<MSIMetadata>('/api/images/metadata/all', {
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

function clampCrop(crop: CropRect): CropRect {
  const x = Math.min(Math.max(crop.x, 0), 0.999)
  const y = Math.min(Math.max(crop.y, 0), 0.999)
  const width = Math.min(Math.max(crop.width, 0.001), 1 - x)
  const height = Math.min(Math.max(crop.height, 0.001), 1 - y)
  return { x, y, width, height }
}

function cropToElementRect(crop: CropRect) {
  if (!viewer || !osd || !wsiImageLayer) return null
  const size = wsiImageLayer.getContentSize()
  const topLeft = wsiImageLayer.imageToViewportCoordinates(new osd.Point(crop.x * size.x, crop.y * size.y))
  const bottomRight = wsiImageLayer.imageToViewportCoordinates(new osd.Point((crop.x + crop.width) * size.x, (crop.y + crop.height) * size.y))
  const topLeftPixel = viewer.viewport.pixelFromPoint(topLeft, true)
  const bottomRightPixel = viewer.viewport.pixelFromPoint(bottomRight, true)
  const left = Math.min(topLeftPixel.x, bottomRightPixel.x)
  const top = Math.min(topLeftPixel.y, bottomRightPixel.y)
  const right = Math.max(topLeftPixel.x, bottomRightPixel.x)
  const bottom = Math.max(topLeftPixel.y, bottomRightPixel.y)
  return {
    left,
    top,
    width: right - left,
    height: bottom - top,
  }
}

function elementRectToCrop(rect: { left: number, top: number, width: number, height: number }): CropRect | null {
  if (!viewer || !osd || !wsiImageLayer) return null
  const size = wsiImageLayer.getContentSize()
  const topLeftViewport = viewer.viewport.pointFromPixel(new osd.Point(rect.left, rect.top), true)
  const bottomRightViewport = viewer.viewport.pointFromPixel(new osd.Point(rect.left + rect.width, rect.top + rect.height), true)
  const topLeftImage = wsiImageLayer.viewportToImageCoordinates(topLeftViewport)
  const bottomRightImage = wsiImageLayer.viewportToImageCoordinates(bottomRightViewport)
  const left = Math.min(topLeftImage.x, bottomRightImage.x) / size.x
  const top = Math.min(topLeftImage.y, bottomRightImage.y) / size.y
  const right = Math.max(topLeftImage.x, bottomRightImage.x) / size.x
  const bottom = Math.max(topLeftImage.y, bottomRightImage.y) / size.y
  return clampCrop({
    x: left,
    y: top,
    width: right - left,
    height: bottom - top,
  })
}

function cropFromCurrentView(): CropRect {
  if (!viewer || !wsiImageLayer) return { x: 0.1, y: 0.1, width: 0.8, height: 0.8 }
  const bounds = viewer.viewport.getBounds(true)
  const size = wsiImageLayer.getContentSize()
  const topLeft = wsiImageLayer.viewportToImageCoordinates(bounds.getTopLeft())
  const bottomRight = wsiImageLayer.viewportToImageCoordinates(bounds.getBottomRight())
  return clampCrop({
    x: Math.min(topLeft.x, bottomRight.x) / size.x,
    y: Math.min(topLeft.y, bottomRight.y) / size.y,
    width: Math.abs(bottomRight.x - topLeft.x) / size.x,
    height: Math.abs(bottomRight.y - topLeft.y) / size.y,
  })
}

function updateCropOverlay() {
  if (!cropEditing.value || !cropDraft.value) {
    cropOverlayRect.value = null
    return
  }
  cropOverlayRect.value = cropToElementRect(cropDraft.value)
}

function startCropEdit() {
  if (!viewerReady.value || !showWsi.value) return
  cropDraft.value = cropRect.value ? { ...cropRect.value } : cropFromCurrentView()
  cropEditing.value = true
  cropEnabled.value = false
  applyCrop()
  updateCropOverlay()
}

function cancelCropEdit() {
  cropEditing.value = false
  cropDraft.value = null
  cropOverlayRect.value = null
  cropDrag = null
  cropEnabled.value = true
  applyCrop()
}

async function saveCropEdit() {
  if (!wsiFilepath.value || !cropDraft.value) return
  cropSaving.value = true
  try {
    cropRect.value = await $fetch<CropRect | null>('/api/images/metadata/crop', {
      method: 'PUT',
      query: { filepath: wsiFilepath.value },
      body: { crop: cropDraft.value },
    })
    if (wsiMeta.value) wsiMeta.value.crop = cropRect.value
    cropEditing.value = false
    cropDraft.value = null
    cropOverlayRect.value = null
    cropEnabled.value = true
    applyCrop()
  } finally {
    cropSaving.value = false
  }
}

function cropOverlayStyle() {
  if (!cropOverlayRect.value) return {}
  return {
    left: `${cropOverlayRect.value.left}px`,
    top: `${cropOverlayRect.value.top}px`,
    width: `${cropOverlayRect.value.width}px`,
    height: `${cropOverlayRect.value.height}px`,
  }
}

function beginCropDrag(event: PointerEvent, handle: CropHandle) {
  if (!cropOverlayRect.value) return
  const target = event.currentTarget as HTMLElement
  target.setPointerCapture(event.pointerId)
  cropDrag = {
    handle,
    pointerId: event.pointerId,
    startX: event.clientX,
    startY: event.clientY,
    startRect: { ...cropOverlayRect.value },
  }
}

function dragCrop(event: PointerEvent) {
  if (!cropDrag || event.pointerId !== cropDrag.pointerId) return
  const deltaX = event.clientX - cropDrag.startX
  const deltaY = event.clientY - cropDrag.startY
  const start = cropDrag.startRect
  let left = start.left
  let top = start.top
  let right = start.left + start.width
  let bottom = start.top + start.height

  if (cropDrag.handle === 'move') {
    left += deltaX
    right += deltaX
    top += deltaY
    bottom += deltaY
  } else {
    if (cropDrag.handle.includes('w')) left += deltaX
    if (cropDrag.handle.includes('e')) right += deltaX
    if (cropDrag.handle.includes('n')) top += deltaY
    if (cropDrag.handle.includes('s')) bottom += deltaY
  }

  const minSize = 24
  if (right - left < minSize) {
    if (cropDrag.handle.includes('w')) left = right - minSize
    else right = left + minSize
  }
  if (bottom - top < minSize) {
    if (cropDrag.handle.includes('n')) top = bottom - minSize
    else bottom = top + minSize
  }

  const crop = elementRectToCrop({
    left,
    top,
    width: right - left,
    height: bottom - top,
  })
  if (!crop) return
  cropDraft.value = crop
  updateCropOverlay()
}

function endCropDrag(event: PointerEvent) {
  if (!cropDrag || event.pointerId !== cropDrag.pointerId) return
  cropDrag = null
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
      imageSmoothingEnabled: false,
      springStiffness: 12,
      animationTime: 0.4,
    })
    viewer.drawer.setImageSmoothingEnabled(false)
    viewer.addHandler('animation', updateCropOverlay)
    viewer.addHandler('animation-finish', updateCropOverlay)
    viewer.addHandler('resize', updateCropOverlay)

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
  updateCropOverlay()
}

function toggleCrop() {
  if (cropEditing.value) cancelCropEdit()
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
    if (registered) {
      await loadRegistrationMatrix()
      applyMsiLayerTransform()
    } else {
      registrationMatrix.value = null
    }
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
  cropEditing.value = false
  cropDraft.value = null
  cropOverlayRect.value = null
  cropDrag = null
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
  window.addEventListener('resize', updateCropOverlay)
})

onBeforeUnmount(() => {
  destroy()
  document.removeEventListener('fullscreenchange', syncFullscreenState)
  window.removeEventListener('resize', updateCropOverlay)
})

watch(() => [props.wsi, props.msi, props.displayWsi, props.displayMsi], ([wsi, msi], [previousWsi, previousMsi]) => {
  destroy()
  if (wsi !== previousWsi || msi !== previousMsi) cropEnabled.value = true
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
      <div v-if="overlaid" class="mx-2">
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
      <div
        v-if="cropEditing"
        class="pointer-events-auto absolute inset-0 z-20"
        @pointerdown.stop.prevent
        @pointermove.stop.prevent="dragCrop"
        @pointerup.stop.prevent="endCropDrag"
        @pointercancel.stop.prevent="endCropDrag"
      >
        <div
          v-if="cropOverlayRect"
          class="absolute cursor-move border-2 border-primary bg-primary/10 shadow-[0_0_0_9999px_rgba(0,0,0,0.18)]"
          :style="cropOverlayStyle()"
          @pointerdown.stop.prevent="beginCropDrag($event, 'move')"
        >
          <div
            v-for="handle in cropHandles"
            :key="handle.handle"
            :class="[cropHandleClass, handle.class]"
            @pointerdown.stop.prevent="beginCropDrag($event, handle.handle)"
          />
        </div>
        <div class="absolute bottom-3 inset-s-1/2 flex -translate-x-1/2 gap-1 rounded-md border border-default/80 bg-default/80 p-1 shadow-lg backdrop-blur-md">
          <UButton
            label="Save"
            icon="i-lucide-check"
            color="primary"
            variant="soft"
            size="sm"
            :loading="cropSaving"
            :disabled="cropSaving"
            @click="saveCropEdit"
          />
          <UButton
            label="Cancel"
            icon="i-lucide-x"
            color="neutral"
            variant="ghost"
            size="sm"
            :disabled="cropSaving"
            @click="cancelCropEdit"
          />
        </div>
      </div>
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
              :disabled="!hasCrop || cropEditing"
              variant="ghost"
              size="sm"
              square
              @click="toggleCrop"
            />
          </UTooltip>
          <UTooltip v-if="showWsi" text="Edit crop" :delay-duration="250">
            <UButton
              icon="i-lucide-square-pen"
              :color="cropEditing ? 'primary' : 'neutral'"
              :disabled="!viewerReady || cropEditing"
              :variant="cropEditing ? 'soft' : 'ghost'"
              size="sm"
              square
              @click="startCropEdit"
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
