import type { FilesystemEntry } from '~/types/filesystem'

export function useFileIcon() {
  function fileIcon(entry: Pick<FilesystemEntry, 'directory' | 'type'>) {
    if (entry.directory) return 'mdi-folder'
    if (entry.type === 'MSI') return 'streamline-image-blur'
    if (entry.type === 'WSI') return 'healthicons-cell-nuclei-outline-24px'
    return 'iconamoon-file'
  }
  function fileIconColorClass(entry: Pick<FilesystemEntry, 'directory' | 'type'>) {
    if (entry.directory) return 'text-primary'
    if (entry.type) return 'text-neutral'
    return 'text-dimmed'
  }
  return { fileIcon, fileIconColorClass }
}
