<script setup lang="ts">
import type OpenSeadragon from 'openseadragon'
import type { TileSource } from 'openseadragon'
import type { MSIDisplay, MSIMetadata, WSIMetadata } from '~/types/images'

type CropRect = { x: number, y: number, width: number, height: number }
type CropHandle = 'move' | 'n' | 's' | 'e' | 'w' | 'nw' | 'ne' | 'sw' | 'se'
type Point = { x: number, y: number }
type ManualRegistrationHandle = 'move' | 'rotate' | 'n' | 's' | 'e' | 'w' | 'nw' | 'ne' | 'sw' | 'se'
type ManualRegistrationState = { origin: Point, xVector: Point, yVector: Point }
type ManualRegistrationFrame = { origin: Point, width: number, height: number, angle: number }
type MsiImageOverlay = { width: number, height: number, transform: string, opacity: number }

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
const manualRegistrationEditing = ref(false)
const manualRegistrationSaving = ref(false)
const manualRegistration = ref<ManualRegistrationState | null>(null)
const manualRegistrationFrame = ref<ManualRegistrationFrame | null>(null)
const manualRegistrationOriginalMatrix = ref<number[][] | null>(null)
const msiImageOverlay = ref<MsiImageOverlay | null>(null)

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
const manualRegistrationHandleClass = 'absolute z-20 size-4 border-2 border-secondary bg-default shadow'
const manualRegistrationEdges: { handle: ManualRegistrationHandle, class: string }[] = [
  { handle: 'n', class: 'left-0 top-0 z-10 h-1.5 w-full -translate-y-1/2' },
  { handle: 'e', class: 'right-0 top-0 z-10 h-full w-1.5 translate-x-1/2' },
  { handle: 's', class: 'bottom-0 left-0 z-10 h-1.5 w-full translate-y-1/2' },
  { handle: 'w', class: 'left-0 top-0 z-10 h-full w-1.5 -translate-x-1/2' },
]
const manualRegistrationCorners: { handle: ManualRegistrationHandle, class: string }[] = [
  { handle: 'nw', class: '-left-2 -top-2' },
  { handle: 'ne', class: '-right-2 -top-2' },
  { handle: 'se', class: '-bottom-2 -right-2' },
  { handle: 'sw', class: '-bottom-2 -left-2' },
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
let manualRegistrationDrag: {
  handle: ManualRegistrationHandle
  pointerId: number
  startX: number
  startY: number
  startState: ManualRegistrationState
  startCenter: Point
  startAngle: number
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

function addPoint(a: Point, b: Point): Point {
  return { x: a.x + b.x, y: a.y + b.y }
}

function subtractPoint(a: Point, b: Point): Point {
  return { x: a.x - b.x, y: a.y - b.y }
}

function scalePoint(point: Point, factor: number): Point {
  return { x: point.x * factor, y: point.y * factor }
}

function pointLength(point: Point) {
  return Math.hypot(point.x, point.y)
}

function normalizePoint(point: Point): Point {
  const length = pointLength(point)
  if (length === 0) return { x: 0, y: 0 }
  return scalePoint(point, 1 / length)
}

function dotPoint(a: Point, b: Point) {
  return a.x * b.x + a.y * b.y
}

function rotatePoint(point: Point, angle: number): Point {
  const cosine = Math.cos(angle)
  const sine = Math.sin(angle)
  return {
    x: point.x * cosine - point.y * sine,
    y: point.x * sine + point.y * cosine,
  }
}

function cloneManualRegistrationState(state: ManualRegistrationState): ManualRegistrationState {
  return {
    origin: { ...state.origin },
    xVector: { ...state.xVector },
    yVector: { ...state.yVector },
  }
}

function manualRegistrationCenter(state: ManualRegistrationState): Point {
  return addPoint(state.origin, scalePoint(addPoint(state.xVector, state.yVector), 0.5))
}

function imageContentSize() {
  const size = msiImageLayer?.getContentSize()
  if (size) return { x: size.x, y: size.y }
  if (msiMeta.value?.width && msiMeta.value?.height) return { x: msiMeta.value.width, y: msiMeta.value.height }
  return null
}

function registrationMatrixToManualState(matrix: number[][]): ManualRegistrationState | null {
  if (!viewer || !osd || !wsiImageLayer || !wsiMeta.value || !msiMeta.value?.mpp) return null
  const size = imageContentSize()
  if (!size) return null
  const row0 = matrix[0]
  const row1 = matrix[1]
  if (!row0 || !row1) return null
  const xScale = msiMeta.value.mpp.x / wsiMeta.value.mpp.x
  const yScale = msiMeta.value.mpp.y / wsiMeta.value.mpp.y
  const a = (row0[0] ?? 1) * xScale
  const b = (row0[1] ?? 0) * xScale
  const c = (row0[2] ?? 0) * xScale
  const d = (row1[0] ?? 0) * yScale
  const e = (row1[1] ?? 1) * yScale
  const f = (row1[2] ?? 0) * yScale
  const origin = wsiImageLayer.imageToViewportCoordinates(new osd.Point(c, f))
  const xAxis = wsiImageLayer.imageToViewportCoordinates(new osd.Point(c + a * size.x, f + d * size.x))
  const yAxis = wsiImageLayer.imageToViewportCoordinates(new osd.Point(c + b * size.y, f + e * size.y))
  return {
    origin: { x: origin.x, y: origin.y },
    xVector: { x: xAxis.x - origin.x, y: xAxis.y - origin.y },
    yVector: { x: yAxis.x - origin.x, y: yAxis.y - origin.y },
  }
}

function manualStateToRegistrationMatrix(state: ManualRegistrationState): number[][] | null {
  if (!viewer || !osd || !wsiImageLayer || !wsiMeta.value || !msiMeta.value?.mpp) return null
  const size = imageContentSize()
  if (!size) return null
  const origin = new osd.Point(state.origin.x, state.origin.y)
  const xAxis = new osd.Point(state.origin.x + state.xVector.x / size.x, state.origin.y + state.xVector.y / size.x)
  const yAxis = new osd.Point(state.origin.x + state.yVector.x / size.y, state.origin.y + state.yVector.y / size.y)
  const originImage = wsiImageLayer.viewportToImageCoordinates(origin)
  const xAxisImage = wsiImageLayer.viewportToImageCoordinates(xAxis)
  const yAxisImage = wsiImageLayer.viewportToImageCoordinates(yAxis)
  const xScale = msiMeta.value.mpp.x / wsiMeta.value.mpp.x
  const yScale = msiMeta.value.mpp.y / wsiMeta.value.mpp.y
  return [
    [
      (xAxisImage.x - originImage.x) / xScale,
      (yAxisImage.x - originImage.x) / xScale,
      originImage.x / xScale,
    ],
    [
      (xAxisImage.y - originImage.y) / yScale,
      (yAxisImage.y - originImage.y) / yScale,
      originImage.y / yScale,
    ],
    [0, 0, 1],
  ]
}

function stateToElementFrame(state: ManualRegistrationState): ManualRegistrationFrame | null {
  if (!viewer || !osd) return null
  const origin = viewer.viewport.pixelFromPoint(new osd.Point(state.origin.x, state.origin.y), true)
  const xAxis = viewer.viewport.pixelFromPoint(new osd.Point(state.origin.x + state.xVector.x, state.origin.y + state.xVector.y), true)
  const yAxis = viewer.viewport.pixelFromPoint(new osd.Point(state.origin.x + state.yVector.x, state.origin.y + state.yVector.y), true)
  const xVector = { x: xAxis.x - origin.x, y: xAxis.y - origin.y }
  const yVector = { x: yAxis.x - origin.x, y: yAxis.y - origin.y }
  return {
    origin,
    width: pointLength(xVector),
    height: pointLength(yVector),
    angle: Math.atan2(xVector.y, xVector.x),
  }
}

function updateManualRegistrationFrame() {
  if (!manualRegistrationEditing.value || !manualRegistration.value) {
    manualRegistrationFrame.value = null
    return
  }
  manualRegistrationFrame.value = stateToElementFrame(manualRegistration.value)
}

function manualRegistrationFrameStyle() {
  if (!manualRegistrationFrame.value) return {}
  const frame = manualRegistrationFrame.value
  return {
    left: `${frame.origin.x}px`,
    top: `${frame.origin.y}px`,
    width: `${frame.width}px`,
    height: `${frame.height}px`,
    transform: `rotate(${frame.angle}rad)`,
  }
}

function cursorForAngle(angle: number) {
  const quarterTurn = Math.PI / 4
  const normalized = ((angle % Math.PI) + Math.PI) % Math.PI
  const index = Math.round(normalized / quarterTurn) % 4
  return ['ew-resize', 'nwse-resize', 'ns-resize', 'nesw-resize'][index]
}

function manualRegistrationHandleStyle(handle: ManualRegistrationHandle) {
  if (!manualRegistrationFrame.value) return {}
  const frame = manualRegistrationFrame.value
  const diagonal = Math.atan2(frame.height, frame.width)
  let angle = frame.angle
  if (handle === 'n' || handle === 's') angle += Math.PI / 2
  if (handle === 'nw' || handle === 'se') angle += diagonal
  if (handle === 'ne' || handle === 'sw') angle -= diagonal
  return { cursor: cursorForAngle(angle) }
}

function updateMsiImageOverlay() {
  if (!overlaid.value || !registrationMatrix.value || !msiImageUrl.value || !viewer || !osd || !wsiImageLayer || !wsiMeta.value || !msiMeta.value?.mpp) {
    msiImageOverlay.value = null
    return
  }
  const size = imageContentSize()
  const state = registrationMatrixToManualState(registrationMatrix.value)
  if (!size || !state) {
    msiImageOverlay.value = null
    return
  }
  const origin = viewer.viewport.pixelFromPoint(new osd.Point(state.origin.x, state.origin.y), true)
  const xAxis = viewer.viewport.pixelFromPoint(new osd.Point(state.origin.x + state.xVector.x / size.x, state.origin.y + state.xVector.y / size.x), true)
  const yAxis = viewer.viewport.pixelFromPoint(new osd.Point(state.origin.x + state.yVector.x / size.y, state.origin.y + state.yVector.y / size.y), true)
  msiImageOverlay.value = {
    width: size.x,
    height: size.y,
    opacity: msiOpacity.value,
    transform: `matrix(${xAxis.x - origin.x}, ${xAxis.y - origin.y}, ${yAxis.x - origin.x}, ${yAxis.y - origin.y}, ${origin.x}, ${origin.y})`,
  }
}

function msiImageOverlayStyle() {
  if (!msiImageOverlay.value) return {}
  return {
    width: `${msiImageOverlay.value.width}px`,
    height: `${msiImageOverlay.value.height}px`,
    opacity: String(msiImageOverlay.value.opacity),
    transform: msiImageOverlay.value.transform,
  }
}

function applyManualRegistrationState() {
  if (!manualRegistration.value) return
  const matrix = manualStateToRegistrationMatrix(manualRegistration.value)
  if (matrix) {
    registrationMatrix.value = matrix
    applyMsiLayerTransform()
  }
  updateManualRegistrationFrame()
}

function startManualRegistrationEdit() {
  if (!overlaid.value || !registrationMatrix.value) return
  const state = registrationMatrixToManualState(registrationMatrix.value)
  if (!state) return
  if (cropEditing.value) cancelCropEdit()
  manualRegistrationOriginalMatrix.value = registrationMatrix.value.map(row => [...row])
  manualRegistration.value = state
  manualRegistrationEditing.value = true
  updateManualRegistrationFrame()
}

function cancelManualRegistrationEdit() {
  registrationMatrix.value = manualRegistrationOriginalMatrix.value
  manualRegistrationEditing.value = false
  manualRegistrationSaving.value = false
  manualRegistration.value = null
  manualRegistrationFrame.value = null
  manualRegistrationOriginalMatrix.value = null
  manualRegistrationDrag = null
  applyMsiLayerTransform()
}

async function saveManualRegistrationEdit() {
  const query = registrationRequestParams()
  if (!query || !manualRegistration.value) return
  const matrix = manualStateToRegistrationMatrix(manualRegistration.value)
  if (!matrix) return
  manualRegistrationSaving.value = true
  try {
    await $fetch<boolean>('/api/images/msi/registered/transform', {
      method: 'PUT',
      body: {
        filepath: query.filepath,
        reference: query.reference,
        transform: matrix,
      },
    })
    registrationMatrix.value = matrix
    emit('update:registered', true)
    manualRegistrationEditing.value = false
    manualRegistration.value = null
    manualRegistrationFrame.value = null
    manualRegistrationOriginalMatrix.value = null
    manualRegistrationDrag = null
    applyMsiLayerTransform()
  } finally {
    manualRegistrationSaving.value = false
  }
}

function beginManualRegistrationDrag(event: PointerEvent, handle: ManualRegistrationHandle) {
  if (!manualRegistration.value || !viewer || !osd) return
  const target = event.currentTarget as HTMLElement
  target.setPointerCapture(event.pointerId)
  const center = manualRegistrationCenter(manualRegistration.value)
  const centerPixel = viewer.viewport.pixelFromPoint(new osd.Point(center.x, center.y), true)
  manualRegistrationDrag = {
    handle,
    pointerId: event.pointerId,
    startX: event.clientX,
    startY: event.clientY,
    startState: cloneManualRegistrationState(manualRegistration.value),
    startCenter: { x: centerPixel.x, y: centerPixel.y },
    startAngle: Math.atan2(event.clientY - centerPixel.y, event.clientX - centerPixel.x),
  }
}

function dragManualRegistration(event: PointerEvent) {
  if (!manualRegistrationDrag || event.pointerId !== manualRegistrationDrag.pointerId || !viewer || !osd) return
  const start = manualRegistrationDrag.startState
  const startPoint = viewer.viewport.pointFromPixel(new osd.Point(manualRegistrationDrag.startX, manualRegistrationDrag.startY), true)
  const currentPoint = viewer.viewport.pointFromPixel(new osd.Point(event.clientX, event.clientY), true)
  const delta = { x: currentPoint.x - startPoint.x, y: currentPoint.y - startPoint.y }
  if (manualRegistrationDrag.handle === 'move') {
    manualRegistration.value = {
      origin: addPoint(start.origin, delta),
      xVector: { ...start.xVector },
      yVector: { ...start.yVector },
    }
  } else if (manualRegistrationDrag.handle === 'rotate') {
    const angle = Math.atan2(event.clientY - manualRegistrationDrag.startCenter.y, event.clientX - manualRegistrationDrag.startCenter.x)
    manualRegistration.value = rotateManualRegistration(start, angle - manualRegistrationDrag.startAngle)
  } else if (manualRegistrationDrag.handle.length === 2) {
    manualRegistration.value = resizeManualRegistrationCorner(start, manualRegistrationDrag.handle, delta)
  } else {
    manualRegistration.value = resizeManualRegistrationEdge(start, manualRegistrationDrag.handle, delta)
  }
  applyManualRegistrationState()
}

function rotateManualRegistration(start: ManualRegistrationState, angle: number): ManualRegistrationState {
  const center = manualRegistrationCenter(start)
  const rotatedX = rotatePoint(start.xVector, angle)
  const rotatedY = rotatePoint(start.yVector, angle)
  return {
    origin: subtractPoint(center, scalePoint(addPoint(rotatedX, rotatedY), 0.5)),
    xVector: rotatedX,
    yVector: rotatedY,
  }
}

function resizeManualRegistrationEdge(start: ManualRegistrationState, handle: ManualRegistrationHandle, delta: Point): ManualRegistrationState {
  const xLength = pointLength(start.xVector)
  const yLength = pointLength(start.yVector)
  const xUnit = normalizePoint(start.xVector)
  const yUnit = normalizePoint(start.yVector)
  const xChange = dotPoint(delta, xUnit)
  const yChange = dotPoint(delta, yUnit)
  let origin = { ...start.origin }
  let width = xLength
  let height = yLength
  if (handle === 'e') width += xChange
  if (handle === 'w') {
    width -= xChange
    origin = addPoint(origin, scalePoint(xUnit, xChange))
  }
  if (handle === 's') height += yChange
  if (handle === 'n') {
    height -= yChange
    origin = addPoint(origin, scalePoint(yUnit, yChange))
  }
  width = Math.max(width, 0.0001)
  height = Math.max(height, 0.0001)
  return {
    origin,
    xVector: scalePoint(xUnit, width),
    yVector: scalePoint(yUnit, height),
  }
}

function resizeManualRegistrationCorner(start: ManualRegistrationState, handle: ManualRegistrationHandle, delta: Point): ManualRegistrationState {
  const xLength = pointLength(start.xVector)
  const yLength = pointLength(start.yVector)
  const xUnit = normalizePoint(start.xVector)
  const yUnit = normalizePoint(start.yVector)
  const xSign = handle.includes('e') ? 1 : -1
  const ySign = handle.includes('s') ? 1 : -1
  const xScale = (xLength + dotPoint(delta, xUnit) * xSign) / xLength
  const yScale = (yLength + dotPoint(delta, yUnit) * ySign) / yLength
  const scale = Math.max(Math.abs(xScale - 1) > Math.abs(yScale - 1) ? xScale : yScale, 0.02)
  const xVector = scalePoint(xUnit, xLength * scale)
  const yVector = scalePoint(yUnit, yLength * scale)
  let anchor = start.origin
  if (handle === 'nw') anchor = addPoint(start.origin, addPoint(start.xVector, start.yVector))
  if (handle === 'ne') anchor = addPoint(start.origin, start.yVector)
  if (handle === 'sw') anchor = addPoint(start.origin, start.xVector)
  if (handle === 'se') anchor = start.origin
  if (handle === 'nw') return { origin: subtractPoint(anchor, addPoint(xVector, yVector)), xVector, yVector }
  if (handle === 'ne') return { origin: subtractPoint(anchor, yVector), xVector, yVector }
  if (handle === 'sw') return { origin: subtractPoint(anchor, xVector), xVector, yVector }
  return { origin: anchor, xVector, yVector }
}

function endManualRegistrationDrag(event: PointerEvent) {
  if (!manualRegistrationDrag || event.pointerId !== manualRegistrationDrag.pointerId) return
  manualRegistrationDrag = null
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
  msiImageLayer.setOpacity(overlaid.value ? 0 : 1)
  updateMsiImageOverlay()
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
  updateMsiImageOverlay()
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
    viewer.addHandler('animation', updateMsiImageOverlay)
    viewer.addHandler('animation-finish', updateMsiImageOverlay)
    viewer.addHandler('resize', updateMsiImageOverlay)
    viewer.addHandler('animation', updateManualRegistrationFrame)
    viewer.addHandler('animation-finish', updateManualRegistrationFrame)
    viewer.addHandler('resize', updateManualRegistrationFrame)

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
  manualRegistrationEditing.value = false
  manualRegistrationSaving.value = false
  manualRegistration.value = null
  manualRegistrationFrame.value = null
  manualRegistrationOriginalMatrix.value = null
  manualRegistrationDrag = null
  msiImageOverlay.value = null
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
  window.addEventListener('resize', updateMsiImageOverlay)
  window.addEventListener('resize', updateManualRegistrationFrame)
})

onBeforeUnmount(() => {
  destroy()
  document.removeEventListener('fullscreenchange', syncFullscreenState)
  window.removeEventListener('resize', updateCropOverlay)
  window.removeEventListener('resize', updateMsiImageOverlay)
  window.removeEventListener('resize', updateManualRegistrationFrame)
})

watch(() => [props.wsi, props.msi, props.displayWsi, props.displayMsi], ([wsi, msi], [previousWsi, previousMsi]) => {
  destroy()
  if (wsi !== previousWsi || msi !== previousMsi) cropEnabled.value = true
  init()
})

watch(msiOpacity, () => {
  applyMsiLayerTransform()
})

watch(overlaid, () => {
  if (!overlaid.value && manualRegistrationEditing.value) cancelManualRegistrationEdit()
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
    <div ref="viewportEl" class="relative flex-1 overflow-hidden bg-default">
      <div ref="viewerEl" class="absolute inset-0" />
      <img
        v-if="msiImageUrl && msiImageOverlay"
        :src="msiImageUrl"
        class="pointer-events-none absolute left-0 top-0 z-[1] max-w-none origin-top-left select-none [image-rendering:pixelated]"
        :style="msiImageOverlayStyle()"
        draggable="false"
      >
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
      <div
        v-if="manualRegistrationEditing"
        class="pointer-events-auto absolute inset-0 z-20"
        @pointerdown.stop.prevent
        @pointermove.stop.prevent="dragManualRegistration"
        @pointerup.stop.prevent="endManualRegistrationDrag"
        @pointercancel.stop.prevent="endManualRegistrationDrag"
      >
        <div
          v-if="manualRegistrationFrame"
          class="absolute origin-top-left border-2 border-secondary bg-secondary/10"
          :style="manualRegistrationFrameStyle()"
        >
          <div class="absolute -top-8 left-1/2 h-8 border-l-2 border-secondary" />
          <div
            class="absolute -top-10 left-1/2 size-4 -translate-x-1/2 cursor-grab rounded-full border-2 border-secondary bg-default shadow"
            @pointerdown.stop.prevent="beginManualRegistrationDrag($event, 'rotate')"
          />
          <div
            v-for="edge in manualRegistrationEdges"
            :key="edge.handle"
            class="absolute bg-secondary/50"
            :class="edge.class"
            :style="manualRegistrationHandleStyle(edge.handle)"
            @pointerdown.stop.prevent="beginManualRegistrationDrag($event, edge.handle)"
          />
          <div
            v-for="corner in manualRegistrationCorners"
            :key="corner.handle"
            :class="[manualRegistrationHandleClass, corner.class]"
            :style="manualRegistrationHandleStyle(corner.handle)"
            @pointerdown.stop.prevent="beginManualRegistrationDrag($event, corner.handle)"
          />
          <div class="absolute inset-0 z-0 cursor-move" @pointerdown.stop.prevent="beginManualRegistrationDrag($event, 'move')" />
        </div>
        <div class="absolute bottom-3 inset-s-1/2 flex -translate-x-1/2 gap-1 rounded-md border border-default/80 bg-default/80 p-1 shadow-lg backdrop-blur-md">
          <UButton
            label="Save"
            icon="i-lucide-check"
            color="secondary"
            variant="soft"
            size="sm"
            :loading="manualRegistrationSaving"
            :disabled="manualRegistrationSaving"
            @click="saveManualRegistrationEdit"
          />
          <UButton
            label="Cancel"
            icon="i-lucide-x"
            color="neutral"
            variant="ghost"
            size="sm"
            :disabled="manualRegistrationSaving"
            @click="cancelManualRegistrationEdit"
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
          <UTooltip v-if="showMsi" text="Manual registration" :delay-duration="250">
            <UButton
              icon="i-lucide-scan"
              :color="manualRegistrationEditing ? 'secondary' : 'neutral'"
              :disabled="!overlaid || !registrationMatrix || manualRegistrationEditing"
              :variant="manualRegistrationEditing ? 'soft' : 'ghost'"
              size="sm"
              square
              @click="startManualRegistrationEdit"
            />
          </UTooltip>
          <UTooltip v-if="showMsi" :text="overlay ? 'Show separately' : 'Overlay'" :delay-duration="250">
            <UButton
              icon="carbon-overlay"
              :color="overlay ? 'secondary' : 'neutral'"
              :disabled="!canOverlay || manualRegistrationEditing"
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
