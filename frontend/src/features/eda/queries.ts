import { useQuery } from '@tanstack/react-query'
import { getEdaCorrelation, getEdaDistributions, getEdaSummary } from '../../api/eda'
import {
  EdaCorrelationQuerySchema,
  EdaDistributionQuerySchema,
  EdaSummaryQuerySchema,
  type EdaCorrelationQuery,
  type EdaDistributionQuery,
} from '../../contracts/eda'
import type { UrlFilters } from '../filters/urlFilters'

export function useEdaSummaryQuery(filters: UrlFilters) {
  const query = EdaSummaryQuerySchema.parse({
    deviceId: filters.sensor,
    from: filters.from,
    to: filters.to,
    bucket: filters.bucket,
  })
  return useQuery({
    queryKey: ['eda', 'summary', query.deviceId ?? null, query.from, query.to, query.bucket] as const,
    queryFn: ({ signal }) => getEdaSummary(query, signal),
  })
}

export function useEdaDistributionsQuery(input: EdaDistributionQuery) {
  const query = EdaDistributionQuerySchema.parse(input)
  return useQuery({
    queryKey: [
      'eda',
      'distributions',
      query.deviceId ?? null,
      query.from,
      query.to,
      query.field,
      query.bins,
    ] as const,
    queryFn: ({ signal }) => getEdaDistributions(query, signal),
  })
}

export function useEdaCorrelationQuery(input: EdaCorrelationQuery) {
  const query = EdaCorrelationQuerySchema.parse(input)
  return useQuery({
    queryKey: [
      'eda',
      'correlation',
      query.deviceId ?? null,
      query.from,
      query.to,
      query.xField,
      query.yField,
      query.maxPoints,
      query.cursor ?? null,
    ] as const,
    queryFn: ({ signal }) => getEdaCorrelation(query, signal),
  })
}
