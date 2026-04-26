import { defineAsyncComponent } from 'vue'

export type FileType = {
  extension: string
  icon: string
  component: ReturnType<typeof defineAsyncComponent>
}

export const FILE_TYPES: FileType[] = [

]

export function getFileType(filename: string): FileType | undefined {
  return FILE_TYPES.find(ft => filename.toLowerCase().endsWith(ft.extension))
}
