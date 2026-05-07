import {defineAsyncComponent} from 'vue'
// @ts-ignore
import imzMLViewer from '../components/imzML/Viewer.vue'

export type FileType = {
  extension: string
  icon: string
  component: ReturnType<typeof defineAsyncComponent>
}

export const FILE_TYPES: FileType[] = [
  {
    extension: '.imzml',
    icon: 'dashicons-image-filter',
    component: imzMLViewer,
  },
]

export function getFileType(filename: string): FileType | undefined {
  return FILE_TYPES.find(ft => filename.toLowerCase().endsWith(ft.extension))
}
