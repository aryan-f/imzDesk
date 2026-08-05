export interface WSIMetadata {
  width: number
  height: number
  tile_size: number
  tile_overlap: number
  objective_power?: number
  vendor?: string
  mpp: { x: number, y: number }
  size: { x: number, y: number } // centimeters
  crop: { x: number, y: number, width: number, height: number } | null
  optional: Record<string, string | number | boolean | null>
}

export interface MSIMetadata {
  width: number | null
  height: number | null
  mpp: { x: number, y: number } | null
  size: { x: number, y: number } | null // centimeters
  optional: Record<string, string | number | boolean | null>
}

export interface MSIDisplay {
  preprocessing: {
    normalization: string
    centroiding: string
    baselineCorrection: boolean
    smoothing: boolean
  }
  cubing: {
    method: 'bin' | 'embed'
    mzMin: number
    mzMax: number
    binWidth: number
    model: string
  }
  reduction: {
    method: 'tic' | 'pca' | 'nmf' | 'tsne' | 'umap'
    components: number
    scaling: 'robust' | 'minmax' | 'zscore'
    colormap: string
  }
}

export interface Annotation {
  id: string
  label: string
  kind: 'box' | 'polygon' | 'freehand'
  notes: string
  export: boolean
  project: boolean
  coordinates: number[][]
}

export interface Label {
  id: string
  name: string
  color: string
}

export interface WorkspaceSettings {
  labels: Label[]
}
