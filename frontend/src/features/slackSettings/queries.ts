import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { getSlackSettings, testSlackSettings, updateSlackSettings } from '../../api/slackSettings'
import type {
  TestSlackSettingsRequest,
  UpdateSlackSettingsRequest,
} from '../../contracts/slackSettings'

export const slackSettingsQueryKey = ['settings', 'slack'] as const

export function useSlackSettingsQuery() {
  return useQuery({
    queryKey: slackSettingsQueryKey,
    queryFn: ({ signal }) => getSlackSettings(signal),
    staleTime: 30_000,
  })
}

export function useUpdateSlackSettings() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: UpdateSlackSettingsRequest) => updateSlackSettings(body),
    onSuccess: (settings) => {
      queryClient.setQueryData(slackSettingsQueryKey, settings)
    },
  })
}

export function useTestSlackSettings() {
  return useMutation({
    mutationFn: (body: TestSlackSettingsRequest) => testSlackSettings(body),
  })
}
