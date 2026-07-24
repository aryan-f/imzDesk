import { FILE_TYPES, type FileType } from '~/types/filesystem'

type OpenedFiles = Record<FileType, string | null>

export interface WorkspaceState {
  dirpath: string
  opened: OpenedFiles
  active: FileType | null
}

const emptyOpenedFiles = (): OpenedFiles => Object.fromEntries(
  FILE_TYPES.map(type => [type, null]),
) as OpenedFiles

export function useWorkspace() {
  const state = useState<WorkspaceState>('workspace', () => ({
    dirpath: '',
    opened: emptyOpenedFiles(),
    active: null,
  }))
  const anyOpened = computed(() => FILE_TYPES.some(type => state.value.opened[type]))

  function openDirectory(dirpath: string) {
    state.value.dirpath = dirpath
    state.value.opened = emptyOpenedFiles()
    state.value.active = null
  }

  function openFile(type: FileType, filepath: string) {
    state.value.opened[type] = filepath
    state.value.active = type
  }

  function openFiles(files: Partial<OpenedFiles>, active?: FileType) {
    state.value.opened = { ...emptyOpenedFiles(), ...files }
    state.value.active = active ?? FILE_TYPES.find(fileType => state.value.opened[fileType]) ?? null
  }

  function openDirectoryWithFiles(dirpath: string, files: Partial<OpenedFiles>, active?: FileType) {
    state.value.dirpath = dirpath
    openFiles(files, active)
  }

  function closeFile(type: FileType) {
    state.value.opened[type] = null
    if (state.value.active !== type) return // Nothing further to do
    state.value.active = FILE_TYPES.find(fileType => state.value.opened[fileType]) ?? null
  }

  function setActive(type: FileType) {
    if (!state.value.opened[type]) return
    state.value.active = type
  }

  return {
    state,
    anyOpened,
    openDirectory,
    openFile,
    openFiles,
    openDirectoryWithFiles,
    closeFile,
    setActive,
  }
}
