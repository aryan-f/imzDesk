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
}

export interface MSIMetadata {
  width: number | null
  height: number | null
  mpp: { x: number, y: number } | null
  size: { x: number, y: number } | null // centimeters
}

export interface MSIDisplay {
  preprocessing: {
    normalization: string
    centroiding: string
    baselineCorrection: boolean
    smoothing: boolean
  }
  cubing: {
    method: 'binning' | 'dreams'
    mzMin: number
    mzMax: number
    binWidth: number
    model: string
  }
  reduction: {
    method: 'tic' | 'pca' | 'nmf' | 'tsne' | 'umap'
    components: number
    scaling: string
    colormap: string
  }
}
