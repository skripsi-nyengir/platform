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

export const historicalDefaultRange = Object.freeze({
  from: '2025-06-23T00:00:00',
  to: '2026-07-24T09:02:05',
})

const defaults: Pick<UrlFilters, 'from' | 'to' | 'bucket'> = {
  ...historicalDefaultRange,
  bucket: '15m',
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
