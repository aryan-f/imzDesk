<script setup lang="ts">
import type OpenSeadragon from 'openseadragon'
import {type TileSource} from 'openseadragon'
import {type WSIMetadata} from '~/types/images'

const { state, setActive, closeFile } = useWorkspace()

const props = withDefaults(defineProps<{
  wsi: string | null
  msi: string | null
  other: boolean
}>(), {
  wsi: null,
  msi: null,
  other: false,
})

const overlaid = computed(() => props.wsi && props.msi)

const viewerEl = ref<HTMLElement | null>(null)

const loading = ref(true)

const cropRect = ref<{ x: number; y: number; width: number; height: number } | null>(null)
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

async function buildTileSource(filepath: string) {
  meta.value = await $fetch<WSIMetadata>('/api/images/wsi/metadata', {
    query: { filepath }
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

function destroy() {
  if (viewer) {
    viewer.destroy()
    viewer = null
  }
}

onMounted(init)
onBeforeUnmount(destroy)

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
        <div class="font-data text-sm truncate">{{ wsi }}</div>
      </div>
      <div v-if="overlaid">and</div>
      <div v-if="msi" class="flex truncate gap-2 cursor-pointer" @click="setActive('MSI')">
        <UBadge label="MSI" color="secondary" variant="soft" class="px-1 py-px" />
        <div class="font-data text-sm truncate">{{ msi }}</div>
      </div>
      <div class="flex-1"></div>
      <UButton
        :icon="cropEnabled ? 'mdi-crop' : 'mdi-crop-free'"
        :color="cropEnabled ? 'primary' : 'neutral'"
        :disabled="!hasCrop"
        variant="ghost"
        size="xs"
        :title="cropEnabled ? 'Show full slide' : 'Show crop only'"
        @click="toggleCrop"
      />
      <UButton
        icon="mdi-close"
        variant="ghost"
        color="error"
        size="xs"
        @click="closeAll"
      />
    </div>
    <div class="relative flex-1">
      <div ref="viewerEl" class="absolute inset-0" />
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
