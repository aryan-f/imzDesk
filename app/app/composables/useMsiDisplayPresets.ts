import type { MSIDisplay } from '~/types/images'

const STORAGE_KEY = 'imzdesk.msi-display-presets.v1'

interface MSIDisplayPreset {
  id: string
  name: string
  display: MSIDisplay
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value)
}

function isMsiDisplay(value: unknown): value is MSIDisplay {
  if (!isRecord(value)) return false
  const preprocessing = value.preprocessing
  const cubing = value.cubing
  const reduction = value.reduction
  if (!isRecord(preprocessing) || !isRecord(cubing) || !isRecord(reduction)) return false

  return (
    typeof preprocessing.normalization === 'string'
    && typeof preprocessing.centroiding === 'string'
    && typeof preprocessing.baselineCorrection === 'boolean'
    && typeof preprocessing.smoothing === 'boolean'
    && (cubing.method === 'bin' || cubing.method === 'embed')
    && isFiniteNumber(cubing.mzMin)
    && isFiniteNumber(cubing.mzMax)
    && isFiniteNumber(cubing.binWidth)
    && typeof cubing.model === 'string'
    && ['tic', 'pca', 'nmf', 'tsne', 'umap'].includes(String(reduction.method))
    && isFiniteNumber(reduction.components)
    && ['robust', 'minmax', 'zscore'].includes(String(reduction.scaling))
    && typeof reduction.colormap === 'string'
  )
}

function isPreset(value: unknown): value is MSIDisplayPreset {
  return (
    isRecord(value)
    && typeof value.id === 'string'
    && typeof value.name === 'string'
    && Boolean(value.name.trim())
    && isMsiDisplay(value.display)
  )
}

function cloneDisplay(display: MSIDisplay): MSIDisplay {
  return {
    preprocessing: { ...display.preprocessing },
    cubing: { ...display.cubing },
    reduction: { ...display.reduction },
  }
}

export function useMsiDisplayPresets() {
  const presets = ref<MSIDisplayPreset[]>([])

  onMounted(() => {
    try {
      const stored = window.localStorage.getItem(STORAGE_KEY)
      if (!stored) return
      const values: unknown = JSON.parse(stored)
      if (Array.isArray(values)) {
        presets.value = values.filter(isPreset).map(preset => ({
          ...preset,
          name: preset.name.trim(),
          display: cloneDisplay(preset.display),
        }))
      }
    } catch {
      presets.value = []
    }
  })

  function persist(next: MSIDisplayPreset[]) {
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next))
      presets.value = next
      return true
    } catch {
      return false
    }
  }

  function savePreset(name: string, display: MSIDisplay) {
    const normalizedName = name.trim()
    if (!normalizedName) return false
    const existing = presets.value.find(preset => (
      preset.name.localeCompare(normalizedName, undefined, { sensitivity: 'accent' }) === 0
    ))
    const preset: MSIDisplayPreset = {
      id: existing?.id ?? window.crypto.randomUUID(),
      name: normalizedName,
      display: cloneDisplay(display),
    }
    const next = existing
      ? presets.value.map(value => value.id === existing.id ? preset : value)
      : [...presets.value, preset]
    return persist(next)
  }

  function deletePreset(id: string) {
    return persist(presets.value.filter(preset => preset.id !== id))
  }

  return {
    presets: readonly(presets),
    savePreset,
    deletePreset,
  }
}
