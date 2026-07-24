import type { FilesystemEntry } from '~/types/filesystem'

export type DatasetKind = 'wsi' | 'msi' | 'paired'

export interface DatasetSample {
  id: string
  wsi?: string
  msi?: string
}

export interface DatasetManifest {
  id: string
  name: string
  kind: DatasetKind
  splits: Record<string, DatasetSample[]>
}

export interface DatasetAnnotationSummary {
  id: string
  name: string
  count: number
  color: string
}

export interface DatasetFile extends FilesystemEntry {
  tags: string[]
  annotation_labels: DatasetAnnotationSummary[]
}
