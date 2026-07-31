import { useQuery } from '@tanstack/react-query'
import { getSystemStatus } from '../../api/systemHealth'
import { liveQueryOptions } from '../useLiveTelemetryData'

export function useSystemStatusQuery() {
  return useQuery({
    queryKey: ['system', 'status'],
    queryFn: ({ signal }) => getSystemStatus(signal),
    ...liveQueryOptions,
  })
}
