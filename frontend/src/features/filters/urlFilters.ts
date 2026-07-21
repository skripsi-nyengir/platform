import {
  BucketSchema,
  Rfc3339Schema,
  SensorIdSchema,
  type Bucket,
  type SensorId,
} from '../../contracts/common'

export interface UrlFilters {
  sensor?: SensorId
  from: string
  to: string
  bucket: Bucket
  modelVersion?: string
}

const defaults: Pick<UrlFilters, 'from' | 'to' | 'bucket'> = {
  from: '2026-07-18T00:00:00Z',
  to: '2026-07-19T00:00:00Z',
  bucket: '15m',
}

export function parseUrlFilters(params: URLSearchParams, routeSensorId?: string): UrlFilters {
  const routeSensor = SensorIdSchema.safeParse(routeSensorId)
  const querySensor = SensorIdSchema.safeParse(params.get('sensor'))
  const parsedFrom = Rfc3339Schema.safeParse(params.get('from'))
  const parsedTo = Rfc3339Schema.safeParse(params.get('to'))
  const parsedBucket = BucketSchema.safeParse(params.get('bucket'))
  const from = parsedFrom.success ? parsedFrom.data : defaults.from
  const to = parsedTo.success ? parsedTo.data : defaults.to
  const validRange = Date.parse(from) < Date.parse(to)
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
