export interface ActivityTask {
  id: number
  descriptor: string
}

export interface ActivityState {
  nextId: number
  tasks: ActivityTask[]
}

export function useActivity() {
  const state = useState<ActivityState>('activity', () => ({
    nextId: 1,
    tasks: [],
  }))

  const active = computed(() => state.value.tasks.length > 0)
  const message = computed(() => {
    if (state.value.tasks.length === 0) return 'Ready'
    if (state.value.tasks.length === 1) return state.value.tasks[0]!.descriptor
    return `Busy (${state.value.tasks.length})`
  })

  function startTask(descriptor: string) {
    const id = state.value.nextId
    state.value.nextId += 1
    state.value.tasks.push({ id, descriptor })
    return id
  }

  function endTask(id: number) {
    state.value.tasks = state.value.tasks.filter(task => task.id !== id)
  }

  return {
    state,
    active,
    message,
    startTask,
    endTask,
  }
}
