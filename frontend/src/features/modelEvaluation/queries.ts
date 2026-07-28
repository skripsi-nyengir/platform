import { skipToken, useQuery } from '@tanstack/react-query'
import { getModelEvaluation, getModelEvaluations } from '../../api/modelEvaluations'
import { getModelRegistry } from '../../api/modelRegistry'
import {
  ModelEvaluationDetailSchema,
  ModelEvaluationsQuerySchema,
  type ModelEvaluationSummary,
  type ModelEvaluationsQuery,
} from '../../contracts/modelEvaluation'

export function normalizeModelEvaluationVersion(
  versions: readonly ModelEvaluationSummary[],
  requested?: string | null,
): string | undefined {
  return requested !== null &&
    requested !== undefined &&
    versions.some((item) => item.version === requested)
    ? requested
    : versions[0]?.version
}

export function useModelEvaluationsQuery(input: ModelEvaluationsQuery = {}) {
  const query = ModelEvaluationsQuerySchema.parse(input)
  return useQuery({
    queryKey: ['model-evaluations', 'list', query.page, query.pageSize],
    queryFn: ({ signal }) => getModelEvaluations(query, signal),
  })
}

export function useModelRegistryQuery() {
  return useQuery({
    queryKey: ['model-registry'],
    queryFn: ({ signal }) => getModelRegistry(signal),
  })
}

export function useModelEvaluationQuery(version?: string) {
  const parsedVersion = ModelEvaluationDetailSchema.shape.version.safeParse(version)
  const modelVersion = parsedVersion.success ? parsedVersion.data : undefined
  return useQuery({
    queryKey: ['model-evaluations', 'detail', modelVersion ?? null],
    queryFn:
      modelVersion === undefined
        ? skipToken
        : ({ signal }) => getModelEvaluation(modelVersion, signal),
  })
}
