import { useMutation, useQuery } from '@tanstack/react-query'
import {
  createReplayJob,
  getDevices,
  getReplayJob,
} from '../../api/preview'
import type { ReplayJobRequest } from '../../contracts/preview'

export const previewKeys = {
  devices: ['preview', 'devices'] as const,
  replay: (jobId: string) => ['preview', 'replay', jobId] as const,
}

export function useDevicesQuery() {
  return useQuery({
    queryKey: previewKeys.devices,
    queryFn: ({ signal }) => getDevices(signal),
    staleTime: 60_000,
  })
}

export function useCreateReplayMutation() {
  return useMutation({
    mutationFn: (input: ReplayJobRequest) => createReplayJob(input),
  })
}

export function useReplayJobQuery(jobId: string | undefined) {
  return useQuery({
    queryKey: previewKeys.replay(jobId ?? ''),
    queryFn: ({ signal }) => getReplayJob(jobId ?? '', signal),
    enabled: jobId !== undefined,
    refetchInterval: (query) => {
      const status = query.state.data?.job.status
      return status === 'queued' || status === 'running' ? 1_000 : false
    },
  })
}
