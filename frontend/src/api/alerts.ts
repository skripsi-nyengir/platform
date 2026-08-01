import { z } from 'zod'
import {
  AlertCommandRequestSchema,
  type AlertCommandRequest,
} from '../contracts/common'
import {
  AcknowledgeAlertResponseSchema,
  AlertDetailResponseSchema,
  AlertEventsQuerySchema,
  AlertEventsResponseSchema,
  CurrentAlertsQuerySchema,
  CurrentAlertsResponseSchema,
  ResolveAlertResponseSchema,
  type AcknowledgeAlertResponse,
  type AlertDetailResponse,
  type AlertEventsQuery,
  type AlertEventsResponse,
  type CurrentAlertsQuery,
  type CurrentAlertsResponse,
  type ResolveAlertResponse,
} from '../contracts/alerts'
import { requestJson } from './http'

const AlertIdSchema = z.string().min(1)

export async function getAlertDetail(
  alertId: string,
  signal?: AbortSignal,
): Promise<AlertDetailResponse> {
  const id = AlertIdSchema.parse(alertId)
  return requestJson(
    `/api/alerts/${encodeURIComponent(id)}`,
    AlertDetailResponseSchema,
    { signal },
  )
}

export async function getAlertEvents(
  input: AlertEventsQuery = {},
  signal?: AbortSignal,
): Promise<AlertEventsResponse> {
  const queryInput = AlertEventsQuerySchema.parse(input)
  const query = new URLSearchParams()
  if (queryInput.alertId !== undefined) query.set('alert_id', queryInput.alertId)
  if (queryInput.deviceId !== undefined) query.set('device_id', queryInput.deviceId)
  if (queryInput.from !== undefined) query.set('from', queryInput.from)
  if (queryInput.to !== undefined) query.set('to', queryInput.to)
  query.set('limit', String(queryInput.limit))
  if (queryInput.cursor !== undefined) query.set('cursor', queryInput.cursor)
  const responseSchema = AlertEventsResponseSchema.superRefine((value, context) => {
    if (value.events.length > queryInput.limit) {
      context.addIssue({
        code: 'custom',
        message: 'events length must not exceed the requested limit',
        path: ['events'],
      })
    }
  })
  return requestJson(`/api/alert-events?${query}`, responseSchema, { signal })
}

export async function getCurrentAlerts(
  input: CurrentAlertsQuery = {},
  signal?: AbortSignal,
): Promise<CurrentAlertsResponse> {
  const queryInput = CurrentAlertsQuerySchema.parse(input)
  const query = new URLSearchParams()
  if (queryInput.deviceId !== undefined) query.set('device_id', queryInput.deviceId)
  if (queryInput.status !== undefined) query.set('status', queryInput.status)
  query.set('page', String(queryInput.page))
  query.set('page_size', String(queryInput.pageSize))
  const responseSchema = CurrentAlertsResponseSchema.superRefine((value, context) => {
    if (value.page !== queryInput.page || value.page_size !== queryInput.pageSize) {
      context.addIssue({
        code: 'custom',
        message: 'response pagination must match the request',
        path: ['page'],
      })
    }
  })
  return requestJson(`/api/alerts/current?${query}`, responseSchema, { signal })
}

export async function acknowledgeAlert(
  alertId: string,
  body: AlertCommandRequest,
  signal?: AbortSignal,
): Promise<AcknowledgeAlertResponse> {
  const id = AlertIdSchema.parse(alertId)
  const payload = AlertCommandRequestSchema.parse(body)
  return requestJson(
    `/api/alerts/${encodeURIComponent(id)}/acknowledge`,
    AcknowledgeAlertResponseSchema,
    {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(payload),
      signal,
    },
  )
}

export async function resolveAlert(
  alertId: string,
  body: AlertCommandRequest,
  signal?: AbortSignal,
): Promise<ResolveAlertResponse> {
  const id = AlertIdSchema.parse(alertId)
  const payload = AlertCommandRequestSchema.parse(body)
  return requestJson(
    `/api/alerts/${encodeURIComponent(id)}/resolve`,
    ResolveAlertResponseSchema,
    {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(payload),
      signal,
    },
  )
}
