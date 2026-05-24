export interface ImageResponse {
  mode: string
  image: string
  height: number
  width: number
  origin: number[]
  delta: number[]
  colorbar?: {
    cmin: number
    cmax: number
    colorscale: string
    tickmode?: string
    tickvals?: number[]
    ticktext?: string[]
    labels?: string[]
  }
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
