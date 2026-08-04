import type { SystemStatusResponse } from '../../contracts/systemHealth'

export interface StatusDisplayMeta {
  displayedAt: string
  pollAgeSeconds: number
  retained: boolean
}

export function resolveStatusDisplayMeta(
  snapshot: SystemStatusResponse,
  dataUpdatedAt: number,
  retained: boolean,
  now = Date.now(),
): StatusDisplayMeta {
  const displayedAt = dataUpdatedAt === 0
    ? snapshot.checked_at
    : new Date(dataUpdatedAt).toISOString()
  const pollAgeSeconds = dataUpdatedAt === 0
    ? 0
    : Math.max(0, Math.floor((now - dataUpdatedAt) / 1_000))

  return { displayedAt, pollAgeSeconds, retained }
}
