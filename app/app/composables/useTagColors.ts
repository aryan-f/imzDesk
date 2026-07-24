export function useTagColors() {
  const tagBadgeClass = 'inline-flex h-7 max-w-full items-center gap-1 rounded-full border px-2 text-sm leading-none'
  function tagColorStyle(tag: string) {
    const namespace = tag.split('.')[0] || tag
    let hash = 22101376
    for (const character of namespace) {
      hash ^= character.charCodeAt(0)
      hash = Math.imul(hash, 16777619)
    }
    const hue = Math.abs(hash) % 360
    return {
      backgroundColor: `hsl(${hue} 24% 88%)`,
      borderColor: `hsl(${hue} 22% 66%)`,
      color: `hsl(${hue} 32% 26%)`,
    }
  }
  return { tagBadgeClass, tagColorStyle }
}
