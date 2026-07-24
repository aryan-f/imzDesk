<script setup lang="ts">
import type { DatasetFile } from '~/types/datasets'

type DatasetFilterField = 'filename' | 'dirpath' | 'tags' | 'annotations'
type TextFilterOperator = 'contains' | 'not_contains' | 'starts_with' | 'not_starts_with' | 'ends_with' | 'not_ends_with' | 'is_exactly' | 'is_not_exactly'
type PresenceFilterOperator = 'has' | 'has_not'
type TagFilterOperator = PresenceFilterOperator | 'starts_with' | 'not_starts_with'
type DatasetFilterOperator = TextFilterOperator | PresenceFilterOperator | TagFilterOperator

export interface DatasetPaneItem {
  id: string
  files: DatasetFile[]
}

interface DatasetFilter {
  id: string
  enabled: boolean
  field: DatasetFilterField
  operator: DatasetFilterOperator
  value: string
}

const props = withDefaults(defineProps<{
  title: string
  items: DatasetPaneItem[]
  selectedIds: string[]
  loading?: boolean
  draggableTitle?: boolean
  addVisible?: boolean
  addDisabled?: boolean
  dropSelectedVisible?: boolean
  itemDropVisible?: boolean
  deleteVisible?: boolean
  dragClass?: string
  itemHeight?: number
  tagOptions?: string[]
  labelOptions?: Array<{ label: string, value: string }>
}>(), {
  loading: false,
  draggableTitle: false,
  addVisible: false,
  addDisabled: false,
  dropSelectedVisible: false,
  itemDropVisible: true,
  deleteVisible: false,
  dragClass: '',
  itemHeight: 93,
  tagOptions: () => [],
  labelOptions: () => [],
})
const emit = defineEmits<{
  toggleItem: [id: string]
  selectItems: [ids: string[]]
  deselectItems: [ids: string[]]
  add: []
  dropItem: [id: string]
  dropSelected: []
  delete: []
  openItem: [id: string]
  titleDragstart: [event: DragEvent]
  titleDragend: [event: DragEvent]
  paneDragover: [event: DragEvent]
}>()
const { fileIcon, fileIconColorClass } = useFileIcon()
const { tagColorStyle } = useTagColors()
const filters = ref<DatasetFilter[]>([])
const fieldOptions: Array<{ label: string, value: DatasetFilterField }> = [
  { label: 'Filename', value: 'filename' },
  { label: 'Directory', value: 'dirpath' },
  { label: 'Tags', value: 'tags' },
  { label: 'Annotations', value: 'annotations' },
]
const textOperatorOptions: Array<{ label: string, value: TextFilterOperator }> = [
  { label: 'Contains', value: 'contains' },
  { label: 'Does not contain', value: 'not_contains' },
  { label: 'Starts with', value: 'starts_with' },
  { label: 'Does not start with', value: 'not_starts_with' },
  { label: 'Ends with', value: 'ends_with' },
  { label: 'Does not end with', value: 'not_ends_with' },
  { label: 'Is exactly', value: 'is_exactly' },
  { label: 'Is not exactly', value: 'is_not_exactly' },
]
const presenceOperatorOptions: Array<{ label: string, value: PresenceFilterOperator }> = [
  { label: 'Has', value: 'has' },
  { label: 'Has not', value: 'has_not' },
]
const tagOperatorOptions: Array<{ label: string, value: TagFilterOperator }> = [
  { label: 'Has', value: 'has' },
  { label: 'Has not', value: 'has_not' },
  { label: 'Starts with', value: 'starts_with' },
  { label: 'Does not start with', value: 'not_starts_with' },
]
const activeFilters = computed(() => filters.value.filter(filter => filter.enabled && filter.value.trim()))
const visibleItems = computed(() => props.items.filter(item => activeFilters.value.every(filter => matchesDatasetFilter(item, filter))))
const visibleItemIds = computed(() => visibleItems.value.map(item => item.id))
const selectedVisibleIds = computed(() => visibleItemIds.value.filter(id => props.selectedIds.includes(id)))
const allVisibleSelected = computed(() => visibleItems.value.length > 0 && selectedVisibleIds.value.length === visibleItems.value.length)
const { virtualItems, virtualHeight, updateScroll, itemStyle } = useVirtualList(visibleItems, () => props.itemHeight)
const selectAllChecked = computed({
  get: () => allVisibleSelected.value,
  set: (checked: boolean | 'indeterminate') => {
    if (checked === true) emit('selectItems', visibleItemIds.value)
    else emit('deselectItems', visibleItemIds.value)
  },
})

function parentPath(file: DatasetFile) {
  return file.parent === '.' ? '' : file.parent
}

function isSelected(id: string) {
  return props.selectedIds.includes(id)
}

function annotationLabels(file: DatasetFile) {
  const labels = new Map<string, { id: string, name: string, count: number, color: string }>()
  for (const label of file.annotation_labels) {
    const existing = labels.get(label.id)
    if (existing) existing.count += label.count
    else labels.set(label.id, { ...label })
  }
  return [...labels.values()]
}

function addFilter(field: DatasetFilterField = 'filename') {
  filters.value.push({
    id: crypto.randomUUID(),
    enabled: true,
    field,
    operator: defaultFilterOperator(field),
    value: '',
  })
}

function removeFilter(filter: DatasetFilter) {
  filters.value = filters.value.filter(value => value !== filter)
}

function setFilterField(filter: DatasetFilter, field: DatasetFilterField) {
  filter.field = field
  filter.operator = defaultFilterOperator(field)
  filter.value = ''
}

function defaultFilterOperator(field: DatasetFilterField): DatasetFilterOperator {
  return field === 'filename' || field === 'dirpath' ? 'contains' : 'has'
}

function operatorOptions(filter: DatasetFilter) {
  if (filter.field === 'filename' || filter.field === 'dirpath') return textOperatorOptions
  if (filter.field === 'tags') return tagOperatorOptions
  return presenceOperatorOptions
}

function matchesDatasetFilter(item: DatasetPaneItem, filter: DatasetFilter) {
  const value = filter.value.trim().toLowerCase()
  if (!value) return true
  if (filter.field === 'filename') return item.files.some(file => matchesTextFilter(file.name.toLowerCase(), filter.operator as TextFilterOperator, value))
  if (filter.field === 'dirpath') return item.files.some(file => matchesTextFilter(parentPath(file).toLowerCase(), filter.operator as TextFilterOperator, value))
  if (filter.field === 'tags') {
    const hasTag = item.files.some(file => file.tags.some(tag => tag.toLowerCase() === value))
    const hasTagPrefix = item.files.some(file => file.tags.some(tag => tag.toLowerCase().startsWith(value)))
    if (filter.operator === 'has') return hasTag
    if (filter.operator === 'has_not') return !hasTag
    return filter.operator === 'starts_with' ? hasTagPrefix : !hasTagPrefix
  }
  const hasAnnotation = item.files.some(file => file.annotation_labels.some(label => label.id === filter.value))
  return filter.operator === 'has' ? hasAnnotation : !hasAnnotation
}

function matchesTextFilter(source: string, operator: TextFilterOperator, value: string) {
  if (operator === 'contains') return source.includes(value)
  if (operator === 'not_contains') return !source.includes(value)
  if (operator === 'starts_with') return source.startsWith(value)
  if (operator === 'not_starts_with') return !source.startsWith(value)
  if (operator === 'ends_with') return source.endsWith(value)
  if (operator === 'not_ends_with') return !source.endsWith(value)
  if (operator === 'is_exactly') return source === value
  return source !== value
}
</script>

<template>
  <section class="flex min-h-0 flex-col rounded-lg border border-default bg-muted" :class="dragClass" @dragover.prevent="emit('paneDragover', $event)">
    <div class="flex h-12 items-center gap-2 overflow-hidden border-b border-default px-3 py-2">
      <div v-if="draggableTitle" class="flex min-w-0 max-w-20 shrink cursor-grab items-center gap-1.5 active:cursor-grabbing" draggable="true" @dragstart="emit('titleDragstart', $event)" @dragend="emit('titleDragend', $event)">
        <UIcon name="i-lucide-grip-vertical" class="size-4 shrink-0 text-dimmed" />
        <h2 class="min-w-0 truncate font-data text-sm font-semibold text-muted">
          {{ title }}
        </h2>
      </div>
      <h2 v-else class="min-w-0 max-w-28 shrink truncate text-sm font-semibold text-muted">
        {{ title }}
      </h2>
      <UBadge :label="String(visibleItems.length)" color="neutral" variant="soft" size="sm" />
      <UIcon v-if="loading" name="i-lucide-loader-circle" class="size-4 animate-spin text-muted" />
      <div class="ms-auto" />
      <UCheckbox v-model="selectAllChecked" label="Select All" size="sm" :disabled="!visibleItems.length" :ui="{ root: 'items-center', wrapper: 'w-auto ms-1.5', label: 'leading-4' }" />
      <UPopover>
        <UButton icon="i-lucide-filter" color="neutral" variant="ghost" size="sm" square />
        <template #content>
          <div class="w-[42rem] space-y-3 p-3">
            <div class="flex items-center justify-between">
              <div class="text-sm font-semibold text-default">
                Filters
              </div>
              <UButton label="Add Filter" icon="i-lucide-plus" color="neutral" variant="soft" size="sm" @click="addFilter()" />
            </div>
            <div v-if="filters.length" class="space-y-2">
              <div v-for="filter in filters" :key="filter.id" class="grid grid-cols-[auto_8rem_10rem_1fr_auto] items-center gap-2">
                <UCheckbox v-model="filter.enabled" size="sm" :ui="{ root: 'items-center' }" />
                <USelect :model-value="filter.field" :items="fieldOptions" size="sm" @update:model-value="setFilterField(filter, $event as DatasetFilterField)" />
                <USelect v-model="filter.operator" :items="operatorOptions(filter)" size="sm" />
                <UInput v-if="filter.field === 'filename' || filter.field === 'dirpath'" v-model="filter.value" size="sm" placeholder="Value" />
                <UInputMenu v-else-if="filter.field === 'tags'" v-model="filter.value" :items="tagOptions" mode="autocomplete" create-item="always" size="sm" placeholder="Tag" />
                <USelectMenu v-else v-model="filter.value" :items="labelOptions" value-key="value" size="sm" placeholder="Annotation label" />
                <UButton icon="i-lucide-trash-2" color="neutral" variant="ghost" size="sm" square @click="removeFilter(filter)" />
              </div>
            </div>
            <div v-else class="py-2 text-sm text-muted">
              No filters.
            </div>
          </div>
        </template>
      </UPopover>
      <UButton v-if="addVisible" icon="i-lucide-plus" color="neutral" variant="soft" size="sm" square :disabled="addDisabled" @click="emit('add')" />
      <UTooltip v-if="dropSelectedVisible" text="Drop selected samples">
        <UButton icon="i-lucide-circle-minus" color="neutral" variant="soft" size="sm" square @click="emit('dropSelected')" />
      </UTooltip>
      <UButton v-if="deleteVisible" icon="i-lucide-trash-2" color="neutral" variant="ghost" size="sm" square @click="emit('delete')" />
    </div>
    <div ref="listEl" class="min-h-0 flex-1 overflow-y-auto p-2" @scroll="updateScroll">
      <div class="relative" :style="{ height: virtualHeight }">
        <button v-for="{ item, index } in virtualItems" :key="item.id" class="absolute left-0 flex w-full items-start gap-2 overflow-hidden rounded-md px-2 py-2 text-left hover:bg-elevated" :class="isSelected(item.id) ? 'bg-elevated' : ''" :style="itemStyle(index, -4)" @click="emit('toggleItem', item.id)">
          <span class="mt-0.5 flex size-4 shrink-0 items-center justify-center rounded border border-default" :class="isSelected(item.id) ? 'bg-info text-inverted border-info' : 'bg-default text-transparent'">
            <UIcon name="i-lucide-check" class="size-3" />
          </span>
          <span class="min-w-0 flex-1">
            <span v-for="file in item.files" :key="file.path" class="mb-2 block min-w-0 last:mb-0">
              <span class="flex min-w-0 gap-2">
                <UIcon :name="fileIcon(file)" :class="[fileIconColorClass(file), 'mt-0.5 size-4 shrink-0']" />
                <span class="min-w-0">
                  <span class="block truncate font-data text-xs text-dimmed">{{ parentPath(file) }}</span>
                  <span class="block truncate font-data text-sm text-default">{{ file.name }}</span>
                </span>
              </span>
              <span class="mt-1 flex min-h-5 min-w-0 items-center gap-1 overflow-hidden whitespace-nowrap ps-6">
                <template v-if="file.tags.length">
                  <UBadge v-for="tag in file.tags" :key="tag" :label="tag" color="neutral" variant="soft" size="sm" class="max-w-24 shrink-0 px-1.5 py-0.75" :style="tagColorStyle(tag)" />
                </template>
                <span v-else class="text-xs leading-5 text-dimmed">
                  No tags.
                </span>
              </span>
              <span class="mt-0.5 flex min-h-5 min-w-0 items-center gap-1 overflow-hidden whitespace-nowrap ps-6">
                <template v-if="annotationLabels(file).length">
                  <UBadge v-for="label in annotationLabels(file)" :key="label.id" :label="`${label.name} (${label.count})`" color="neutral" variant="soft" size="sm" class="max-w-24 shrink-0 px-1.5 py-0.75" :style="{ backgroundColor: `${label.color}22`, borderColor: `${label.color}66`, color: label.color }" />
                </template>
                <span v-else class="text-xs leading-5 text-dimmed">
                  No annotations.
                </span>
              </span>
            </span>
          </span>
          <UTooltip v-if="itemDropVisible" text="Drop sample">
            <UButton icon="i-lucide-circle-minus" color="neutral" variant="ghost" size="xs" square @click.stop="emit('dropItem', item.id)" />
          </UTooltip>
          <UTooltip text="Open in workspace">
            <UButton icon="i-lucide-external-link" color="neutral" variant="ghost" size="xs" square @click.stop="emit('openItem', item.id)" />
          </UTooltip>
        </button>
      </div>
    </div>
  </section>
</template>
