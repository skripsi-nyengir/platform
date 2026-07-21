import { useQuery } from '@tanstack/react-query'
import { getSystemStatus } from '../../api/systemHealth'

export function useSystemStatusQuery() {
  return useQuery({
    queryKey: ['system', 'status'],
    queryFn: ({ signal }) => getSystemStatus(signal),
    refetchInterval: 30_000,
    staleTime: 30_000,
  })
}
