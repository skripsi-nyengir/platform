import { useMutation, useQuery } from '@tanstack/react-query'
import {
  computeEda,
  getEdaJob,
  getEdaPeriods,
  getEdaRun,
  getEdaSection,
} from '../../api/eda'
import {
  EdaPeriodListQuerySchema,
  type EdaComputeRequest,
  type EdaPeriodListQuery,
  type EdaSectionName,
} from '../../contracts/eda'

export const edaQueryKeys = {
  periods: (query: Required<EdaPeriodListQuery>) => [
    'eda',
    'periods',
    query.period_kind,
    query.limit,
    query.cursor,
  ] as const,
  job: (jobId: string | null) => ['eda', 'job', jobId] as const,
  run: (runId: string | null) => ['eda', 'run', runId] as const,
  section: (runId: string | null, section: EdaSectionName) => [
    'eda',
    'run',
    runId,
    'section',
    section,
  ] as const,
}

export function useEdaPeriodsQuery(input: EdaPeriodListQuery) {
  const query = EdaPeriodListQuerySchema.parse(input)
  return useQuery({
    queryKey: edaQueryKeys.periods(query),
    queryFn: ({ signal }) => getEdaPeriods(query, signal),
  })
}

export function useEdaRunQuery(runId: string | null) {
  return useQuery({
    queryKey: edaQueryKeys.run(runId),
    queryFn: ({ signal }) => getEdaRun(runId ?? '', signal),
    enabled: runId !== null,
  })
}

export function useEdaSectionQuery(runId: string | null, section: EdaSectionName) {
  return useQuery({
    queryKey: edaQueryKeys.section(runId, section),
    queryFn: ({ signal }) => getEdaSection(runId ?? '', section, signal),
    enabled: runId !== null,
  })
}

export function useEdaComputeMutation() {
  return useMutation({
    mutationFn: (request: EdaComputeRequest) => computeEda(request),
  })
}

export function useEdaJobQuery(jobId: string | null) {
  return useQuery({
    queryKey: edaQueryKeys.job(jobId),
    queryFn: ({ signal }) => getEdaJob(jobId ?? '', signal),
    enabled: jobId !== null,
    refetchInterval: (query) => {
      const status = query.state.data?.job.status
      return status === 'queued' || status === 'running' ? 1_000 : false
    },
  })
}
