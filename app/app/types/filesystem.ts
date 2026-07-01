export const FILE_TYPES = ['MSI', 'WSI'] as const // See `imzdesk.server.utils.filesystem:resolve_filetype`

export type FileType = typeof FILE_TYPES[number]

export interface FilesystemEntry {
  directory: boolean
  parent: string
  name: string
  path: string
  size?: number
  type?: FileType | null
}
