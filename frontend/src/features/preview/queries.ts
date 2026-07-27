import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  activateModel,
  createReplayJob,
  getDevices,
  getModels,
  getReplayJob,
} from '../../api/preview'
import type { SensorId } from '../../contracts/common'
import type { ModelActivationRequest, ReplayJobRequest } from '../../contracts/preview'

export const previewKeys = {
  devices: ['preview', 'devices'] as const,
  models: (deviceId: SensorId) => ['preview', 'models', deviceId] as const,
  replay: (jobId: string) => ['preview', 'replay', jobId] as const,
}

export function useDevicesQuery() {
  return useQuery({
    queryKey: previewKeys.devices,
    queryFn: ({ signal }) => getDevices(signal),
    staleTime: 60_000,
  })
}

export function useModelsQuery(deviceId: SensorId) {
  return useQuery({
    queryKey: previewKeys.models(deviceId),
    queryFn: ({ signal }) => getModels(deviceId, signal),
  })
}

export function useActivateModelMutation(deviceId: SensorId) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: ModelActivationRequest) => activateModel(input),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: previewKeys.models(deviceId) }),
        queryClient.invalidateQueries({ queryKey: ['system', 'status'] }),
      ])
    },
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
