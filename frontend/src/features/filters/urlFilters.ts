import {
  BucketSchema,
  HistoricalDateTimeSchema,
  SensorIdSchema,
  compareHistoricalDateTimes,
  type Bucket,
  type SensorId,
} from '../../contracts/common'
import {
  EdaPrecomputedPeriodKindSchema,
  type EdaPeriodListQuery,
} from '../../contracts/eda'

export interface UrlFilters {
  sensor?: SensorId
  from: string
  to: string
  bucket: Bucket
  modelVersion?: string
}

export const liveRanges = ['1h', '6h', '12h', '24h', 'custom'] as const
export type LiveRange = typeof liveRanges[number]

export interface LiveUrlFilters {
  sensor?: SensorId
  range: LiveRange
  from?: string
  to?: string
  modelVersion?: string
}

export interface ResolvedLiveRange {
  from: string
  to: string
  bucket: 'raw' | 'one_minute' | 'adaptive'
}

export const historicalDefaultRange = Object.freeze({
  from: '2025-06-23T00:00:00',
  to: '2026-07-24T09:02:05',
})

export const telemetryDefaultRange = Object.freeze({
  from: '2026-02-01T00:00:00',
  to: '2026-06-01T00:00:00',
})

const defaults: Pick<UrlFilters, 'from' | 'to' | 'bucket'> = {
  ...telemetryDefaultRange,
  bucket: 'adaptive',
}

const liveRangeHours = {
  '1h': 1,
  '6h': 6,
  '12h': 12,
  '24h': 24,
} as const

function isLiveRange(value: string | null): value is LiveRange {
  return liveRanges.some((range) => range === value)
}

function isValidCustomRange(from: string, to: string): boolean {
  const duration = Date.parse(`${to}+07:00`) - Date.parse(`${from}+07:00`)
  return duration >= 60 * 60 * 1_000 && duration <= 24 * 60 * 60 * 1_000
}

function toWibHistoricalDateTime(value: Date): string {
  return new Date(value.getTime() + 7 * 60 * 60 * 1_000).toISOString().slice(0, 19)
}

export function parseLiveUrlFilters(
  params: URLSearchParams,
  routeSensorId?: string,
): LiveUrlFilters {
  const routeSensor = SensorIdSchema.safeParse(routeSensorId)
  const querySensor = SensorIdSchema.safeParse(params.get('sensor'))
  const requestedRange = params.get('range')
  const range = isLiveRange(requestedRange) ? requestedRange : '1h'
  const parsedFrom = HistoricalDateTimeSchema.safeParse(params.get('from'))
  const parsedTo = HistoricalDateTimeSchema.safeParse(params.get('to'))
  const customIsValid = range === 'custom' && parsedFrom.success && parsedTo.success &&
    isValidCustomRange(parsedFrom.data, parsedTo.data)
  const result: LiveUrlFilters = customIsValid
    ? { range, from: parsedFrom.data, to: parsedTo.data }
    : { range: range === 'custom' ? '1h' : range }
  const sensor = routeSensor.success
    ? routeSensor.data
    : querySensor.success
      ? querySensor.data
      : undefined
  if (sensor !== undefined) result.sensor = sensor
  const modelVersion = params.get('model_version')?.trim()
  if (modelVersion) result.modelVersion = modelVersion
  return result
}

export function updateLiveUrlFilters(
  current: URLSearchParams,
  patch: Partial<LiveUrlFilters>,
): URLSearchParams {
  const next = new URLSearchParams(current)
  next.delete('bucket')
  if (patch.range !== undefined) {
    next.set('range', patch.range)
    if (patch.range !== 'custom') {
      next.delete('from')
      next.delete('to')
    }
  }
  for (const [property, parameter] of [
    ['from', 'from'],
    ['to', 'to'],
    ['sensor', 'sensor'],
    ['modelVersion', 'model_version'],
  ] as const) {
    if (!Object.hasOwn(patch, property)) continue
    const value = patch[property]
    if (value === '' || value === undefined) next.delete(parameter)
    else next.set(parameter, value)
  }
  return next
}

export function resolveLiveRange(filters: LiveUrlFilters, now = new Date()): ResolvedLiveRange {
  if (filters.range === 'custom') {
    if (filters.from === undefined || filters.to === undefined) {
      throw new Error('custom live range requires from and to')
    }
    return { from: filters.from, to: filters.to, bucket: 'adaptive' }
  }
  const durationMs = liveRangeHours[filters.range] * 60 * 60 * 1_000
  return {
    from: toWibHistoricalDateTime(new Date(now.getTime() - durationMs)),
    to: toWibHistoricalDateTime(now),
    bucket: filters.range === '1h' ? 'raw' : 'one_minute',
  }
}

export type EdaRunMode = 'precompute' | 'custom'

export interface EdaUrlState {
  mode: EdaRunMode
  periodKind: EdaPeriodListQuery['period_kind']
  from: string
  to: string
  runId?: string
}

export function parseUrlFilters(params: URLSearchParams, routeSensorId?: string): UrlFilters {
  const routeSensor = SensorIdSchema.safeParse(routeSensorId)
  const querySensor = SensorIdSchema.safeParse(params.get('sensor'))
  const parsedFrom = HistoricalDateTimeSchema.safeParse(params.get('from'))
  const parsedTo = HistoricalDateTimeSchema.safeParse(params.get('to'))
  const parsedBucket = BucketSchema.safeParse(params.get('bucket'))
  const from = parsedFrom.success ? parsedFrom.data : defaults.from
  const to = parsedTo.success ? parsedTo.data : defaults.to
  const validRange = compareHistoricalDateTimes(from, to) < 0
  const result: UrlFilters = {
    from: validRange ? from : defaults.from,
    to: validRange ? to : defaults.to,
    bucket: parsedBucket.success ? parsedBucket.data : defaults.bucket,
  }
  const sensor = routeSensor.success
    ? routeSensor.data
    : querySensor.success
      ? querySensor.data
      : undefined
  if (sensor !== undefined) result.sensor = sensor
  const modelVersion = params.get('model_version')
  if (modelVersion) result.modelVersion = modelVersion
  return result
}

export function updateUrlFilters(
  current: URLSearchParams,
  patch: Partial<UrlFilters>,
): URLSearchParams {
  const next = new URLSearchParams(current)
  next.delete('sensor')
  next.delete('bucket')
  next.delete('model_version')
  const fields = [
    ['sensor', 'sensor', true],
    ['from', 'from', false],
    ['to', 'to', false],
    ['bucket', 'bucket', false],
    ['modelVersion', 'model_version', true],
  ] as const

  for (const [property, parameter, optional] of fields) {
    if (!Object.hasOwn(patch, property)) continue
    const value = patch[property]
    if (value === '' || (optional && value === undefined)) next.delete(parameter)
    else if (value !== undefined) next.set(parameter, value)
  }
  return next
}

export function parseEdaUrlState(params: URLSearchParams): EdaUrlState {
  const parsedPeriodKind = EdaPrecomputedPeriodKindSchema.safeParse(params.get('period_kind'))
  const parsedFrom = HistoricalDateTimeSchema.safeParse(params.get('from'))
  const parsedTo = HistoricalDateTimeSchema.safeParse(params.get('to'))
  const from = parsedFrom.success ? parsedFrom.data : historicalDefaultRange.from
  const to = parsedTo.success ? parsedTo.data : historicalDefaultRange.to
  const validRange = compareHistoricalDateTimes(from, to) < 0
  const result: EdaUrlState = {
    mode: params.get('mode') === 'custom' ? 'custom' : 'precompute',
    periodKind: parsedPeriodKind.success ? parsedPeriodKind.data : 'monthly',
    from: validRange ? from : historicalDefaultRange.from,
    to: validRange ? to : historicalDefaultRange.to,
  }
  const runId = params.get('run')?.trim()
  if (runId) result.runId = runId
  return result
}

export function updateEdaUrlState(
  current: URLSearchParams,
  patch: Partial<EdaUrlState>,
): URLSearchParams {
  const fields = [
    ['mode', 'mode'],
    ['periodKind', 'period_kind'],
    ['from', 'from'],
    ['to', 'to'],
    ['runId', 'run'],
  ] as const
  const next = new URLSearchParams()

  for (const [, parameter] of fields) {
    const value = current.get(parameter)
    if (value !== null) next.set(parameter, value)
  }

  for (const [property, parameter] of fields) {
    if (!Object.hasOwn(patch, property)) continue
    const value = patch[property]
    if (value === '' || value === undefined) next.delete(parameter)
    else next.set(parameter, value)
  }
  return next
}
