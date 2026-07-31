import { useQuery } from '@tanstack/react-query'
import { getAlertDetail, getAlertEvents, getCurrentAlerts } from '../../api/alerts'
import {
  AlertEventsQuerySchema,
  CurrentAlertsQuerySchema,
  type AlertEventsQuery,
  type CurrentAlertsQuery,
} from '../../contracts/alerts'
import { liveQueryOptions } from '../useLiveTelemetryData'

export function useCurrentAlertsQuery(input: CurrentAlertsQuery = {}) {
  const query = CurrentAlertsQuerySchema.parse(input)
  return useQuery({
    queryKey: [
      'alerts',
      'current',
      query.deviceId ?? null,
      query.status ?? null,
      query.page,
      query.pageSize,
    ],
    queryFn: ({ signal }) => getCurrentAlerts(query, signal),
    ...liveQueryOptions,
  })
}

export function useAlertEventsQuery(input: AlertEventsQuery = {}) {
  const query = AlertEventsQuerySchema.parse(input)
  return useQuery({
    queryKey: [
      'alerts',
      'events',
      query.alertId ?? null,
      query.deviceId ?? null,
      query.from ?? null,
      query.to ?? null,
      query.limit,
      query.cursor ?? null,
    ],
    queryFn: ({ signal }) => getAlertEvents(query, signal),
    ...liveQueryOptions,
  })
}

export function useAlertDetailQuery(alertId?: string) {
  return useQuery({
    queryKey: ['live', 'alert-detail', alertId ?? null],
    queryFn: ({ signal }) => getAlertDetail(alertId ?? '', signal),
    enabled: alertId !== undefined,
    ...liveQueryOptions,
  })
}
