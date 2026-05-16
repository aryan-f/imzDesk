export interface ImageResponse {
  mode: string
  coords: { x: number[], y: number[] }
  values: number[][]
  height: number
  width: number
}

export type Selection = {
  id: string
  label: string
  type: 'rect'
  x0: number
  x1: number
  xref: 'x'
  y0: number
  y1: number
  yref: 'y'
  line: {
    color?: string
    width?: number
    opacity?: number
  }
}
