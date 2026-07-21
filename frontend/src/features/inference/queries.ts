import { useQuery } from '@tanstack/react-query'
import { getInferenceResults } from '../../api/inference'
import {
  InferenceResultsQuerySchema,
  type InferenceResultsQuery,
} from '../../contracts/inference'

export function useInferenceResultsQuery(input: InferenceResultsQuery) {
  const query = InferenceResultsQuerySchema.parse(input)
  return useQuery({
    queryKey: [
      'inference',
      'results',
      query.deviceId,
      query.from,
      query.to,
      query.bucket,
      query.limit,
      query.cursor ?? null,
      query.modelVersion ?? null,
    ],
    queryFn: ({ signal }) => getInferenceResults(query, signal),
  })
}
