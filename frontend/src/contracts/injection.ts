import { z } from 'zod'
import {
  HistoricalDateTimeSchema,
  compareHistoricalDateTimes,
  publicTimeZone,
  simDeviceId,
} from './common'

export const SimInjectionFamilySchema = z.enum([
  'spike',
  'drift',
  'stuck',
  'erratic',
  'bias',
  'data_loss',
  'garbage',
])
export const SimInjectionSeveritySchema = z.enum(['low', 'medium', 'high'])

export const SimInjectionEventSchema = z
  .strictObject({
    event_id: z.string().min(1),
    family: SimInjectionFamilySchema,
    severity: SimInjectionSeveritySchema,
    channel: z.string().min(1),
    channel_index: z.number().int().nonnegative(),
    start_ts: HistoricalDateTimeSchema,
    end_ts: HistoricalDateTimeSchema,
    start_idx: z.number().int().nonnegative(),
    end_idx_exclusive: z.number().int().positive(),
    segment_index: z.number().int().nonnegative(),
  })
  .refine((value) => compareHistoricalDateTimes(value.start_ts, value.end_ts) <= 0, {
    message: 'start_ts must not be later than end_ts',
    path: ['start_ts'],
  })
  .refine((value) => value.start_idx < value.end_idx_exclusive, {
    message: 'start_idx must be earlier than end_idx_exclusive',
    path: ['start_idx'],
  })
export type SimInjectionEvent = z.infer<typeof SimInjectionEventSchema>

export const InjectionEventsResponseSchema = z
  .strictObject({
    request_id: z.string(),
    device_id: z.literal(simDeviceId),
    time_zone: z.literal(publicTimeZone),
    events: z.array(SimInjectionEventSchema),
    returned_count: z.number().int().nonnegative(),
  })
  .refine((value) => value.returned_count === value.events.length, {
    message: 'returned_count must equal events length',
    path: ['returned_count'],
  })
export type InjectionEventsResponse = z.infer<typeof InjectionEventsResponseSchema>
