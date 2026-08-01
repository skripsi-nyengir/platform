import { useMutation, useQueryClient } from '@tanstack/react-query'
import { acknowledgeAlert, resolveAlert } from '../../api/alerts'
import type { AlertMutationResponse } from '../../contracts/alerts'
import type { AlertLifecycleCommand } from './alertCommand'

export function useAlertLifecycleMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({
      alertId,
      action,
      body,
    }: AlertLifecycleCommand): Promise<AlertMutationResponse> => {
      if (action === 'acknowledge') return acknowledgeAlert(alertId, body)
      return resolveAlert(alertId, body)
    },
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['alerts', 'current'] }),
        queryClient.invalidateQueries({ queryKey: ['alerts', 'events'] }),
        queryClient.invalidateQueries({ queryKey: ['live'] }),
      ])
    },
    onError: () => Promise.all([
      queryClient.invalidateQueries({ queryKey: ['alerts', 'current'] }),
      queryClient.invalidateQueries({ queryKey: ['live', 'current-alerts'] }),
    ]),
  })
}
