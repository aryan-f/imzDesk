import type { MaybeRefOrGetter } from 'vue'

export function useVirtualList<T>(items: MaybeRefOrGetter<T[]>, itemHeight: number, overscan = 8) {
  const listEl = useTemplateRef<HTMLDivElement>('listEl')
  const scrollTop = ref(0)
  const listHeight = ref(0)
  const allItems = computed(() => toValue(items))
  const start = computed(() => Math.max(0, Math.floor(scrollTop.value / itemHeight) - overscan))
  const end = computed(() => Math.min(allItems.value.length, Math.ceil((scrollTop.value + listHeight.value) / itemHeight) + overscan))
  const virtualItems = computed(() => allItems.value.slice(start.value, end.value).map((item, offset) => ({ item, index: start.value + offset })))
  const virtualHeight = computed(() => `${allItems.value.length * itemHeight}px`)
  let resizeObserver: ResizeObserver | null = null
  onMounted(() => {
    if (!listEl.value) return
    listHeight.value = listEl.value.clientHeight
    resizeObserver = new ResizeObserver(([entry]) => {
      if (!entry) return
      listHeight.value = entry.contentRect.height
    })
    resizeObserver.observe(listEl.value)
  })
  onBeforeUnmount(() => {
    resizeObserver?.disconnect()
  })
  watch(allItems, () => {
    if (!listEl.value) return
    const maxScrollTop = Math.max(0, allItems.value.length * itemHeight - listHeight.value)
    if (scrollTop.value > maxScrollTop) {
      listEl.value.scrollTop = maxScrollTop
      scrollTop.value = maxScrollTop
    }
  })
  function updateScroll(event: Event) {
    scrollTop.value = (event.currentTarget as HTMLDivElement).scrollTop
  }
  function itemStyle(index: number, heightAdjustment = 0) {
    return {
      height: `${itemHeight + heightAdjustment}px`,
      transform: `translateY(${index * itemHeight}px)`,
    }
  }
  return {
    listEl,
    virtualItems,
    virtualHeight,
    updateScroll,
    itemStyle,
  }
}
