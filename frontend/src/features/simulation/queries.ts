import { skipToken, useQuery } from '@tanstack/react-query'
import { ApiError } from '../../api/errors'
import { getSimulationMetrics } from '../../api/simulation'
import { SimModelVersionSchema } from '../../contracts/simulation'

export function useSimulationMetricsQuery(modelVersion?: string) {
  const parsedVersion = SimModelVersionSchema.safeParse(modelVersion)
  const version = parsedVersion.success ? parsedVersion.data : undefined

  return useQuery({
    queryKey: ['simulation', 'metrics', version ?? null, 10],
    queryFn: version === undefined
      ? skipToken
      : ({ signal }) => getSimulationMetrics({ modelVersion: version }, signal),
    retry: (failureCount, error) =>
      !(error instanceof ApiError && error.status === 404) && failureCount < 3,
  })
}
