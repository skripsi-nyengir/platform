import { z } from 'zod'

export const sensorIds = ['b02f3872-ruang-produksi'] as const
export const SensorIdSchema = z.enum(sensorIds)
export type SensorId = z.infer<typeof SensorIdSchema>

export const CorpusDeviceIdSchema = z.enum([
  'b02f3872-ruang-produksi',
  'b02f3872-simulasi-injeksi',
])
export type CorpusDeviceId = z.infer<typeof CorpusDeviceIdSchema>

export const sensorLabels: Readonly<Record<SensorId, string>> = Object.freeze({
  'b02f3872-ruang-produksi': 'B02',
})

export const publicDeviceId = sensorIds[0]
export const simDeviceId = 'b02f3872-simulasi-injeksi' as const satisfies CorpusDeviceId
export const publicTimeZone = 'Asia/Jakarta' as const

export const BucketSchema = z.enum(['raw', 'one_minute', 'adaptive'])
export type Bucket = z.infer<typeof BucketSchema>

export const SeveritySchema = z.enum(['info', 'warning', 'critical'])
export type Severity = z.infer<typeof SeveritySchema>

export const FreshnessSchema = z.enum(['fresh', 'stale', 'unknown'])
export type Freshness = z.infer<typeof FreshnessSchema>

export const AvailabilitySchema = z.enum(['online', 'offline', 'unknown'])
export type Availability = z.infer<typeof AvailabilitySchema>

export const AlertStatusSchema = z.enum(['detected', 'acknowledged', 'resolved'])
export type AlertStatus = z.infer<typeof AlertStatusSchema>

export const Rfc3339Schema = z.iso.datetime({ offset: true })
export const OperationalInstantSchema = z
  .string()
  .regex(/Z$/, 'operational timestamps must be UTC RFC3339 instants')
  .pipe(z.iso.datetime({ offset: true }))

export const HistoricalDateTimeSchema = z
  .string()
  .regex(
    /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$/,
    'historical timestamps must not contain a timezone offset',
  )
  .pipe(z.iso.datetime({ local: true, precision: 0 }))
export type HistoricalDateTime = z.infer<typeof HistoricalDateTimeSchema>

export function compareHistoricalDateTimes(left: string, right: string): number {
  return left.localeCompare(right)
}

export function historicalDateTimeToDate(value: string): Date {
  const parsed = HistoricalDateTimeSchema.parse(value)
  const [datePart, timePart] = parsed.split('T') as [string, string]
  const [year, month, day] = datePart.split('-').map(Number) as [number, number, number]
  const [hour, minute, second] = timePart.split(':').map(Number) as [number, number, number]

  return new Date(year, month - 1, day, hour, minute, second)
}

export function dateToHistoricalDateTime(value: Date): string {
  return value.toISOString().slice(0, 19)
}

export function wibHistoricalDateTimeToUtcInstant(value: string): string {
  const parsed = HistoricalDateTimeSchema.parse(value)
  return new Date(`${parsed}+07:00`).toISOString()
}

export const ProblemDetailsSchema = z.strictObject({
  type: z.url(),
  title: z.string(),
  status: z.number().int(),
  detail: z.string(),
  instance: z.string(),
  request_id: z.string(),
  errors: z.record(z.string(), z.array(z.string())).optional(),
})
export type ProblemDetails = z.infer<typeof ProblemDetailsSchema>

export const AlertCommandRequestSchema = z.strictObject({
  command_id: z.string(),
  note: z.string().optional(),
})
export type AlertCommandRequest = z.infer<typeof AlertCommandRequestSchema>

export type ApiPath = `/api/${string}` | '/health' | '/ready'
