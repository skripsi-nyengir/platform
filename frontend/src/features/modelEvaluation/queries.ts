import { useQuery } from '@tanstack/react-query'
import { getModelRegistry } from '../../api/modelRegistry'
import { getOfflineEvaluations } from '../../api/offlineEvaluations'

export function useModelRegistryQuery() {
  return useQuery({
    queryKey: ['model-registry'],
    queryFn: ({ signal }) => getModelRegistry(signal),
  })
}

export function useOfflineEvaluationsQuery() {
  return useQuery({
    queryKey: ['offline-evaluations'],
    queryFn: ({ signal }) => getOfflineEvaluations(signal),
  })
}
