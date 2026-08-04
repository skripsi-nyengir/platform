export function formatDuration(seconds: number | null): string {
  if (seconds === null || !Number.isFinite(seconds)) return 'Unknown'
  const wholeSeconds = Math.max(0, Math.floor(seconds))
  if (wholeSeconds < 60) return `${wholeSeconds}s`
  const minutes = Math.floor(wholeSeconds / 60)
  const remainderSeconds = wholeSeconds % 60
  if (minutes < 60) return remainderSeconds === 0 ? `${minutes}m` : `${minutes}m ${remainderSeconds}s`
  const hours = Math.floor(minutes / 60)
  const remainderMinutes = minutes % 60
  if (hours < 24) return remainderMinutes === 0 ? `${hours}h` : `${hours}h ${remainderMinutes}m`
  const days = Math.floor(hours / 24)
  const remainderHours = hours % 24
  return remainderHours === 0 ? `${days}d` : `${days}d ${remainderHours}h`
}
