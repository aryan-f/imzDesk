export interface WSIMetadata {
  width: number
  height: number
  tile_size: number
  tile_overlap: number
  objective_power?: number
  vendor?: string
  mpp: { x: number; y: number }
  size: { x: number; y: number }  // centimeters
  crop: { x: number; y: number; width: number; height: number } | null
}
