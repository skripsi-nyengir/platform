import { Alert, Button, Stack } from '@mui/material'
import type { CurrentAlert } from '../../contracts/alerts'
import { createAlertLifecycleCommand } from '../alerts/alertCommand'
import { useAlertLifecycleMutation } from '../alerts/useAlertLifecycleMutation'

export interface ActionQueueProps {
  alert: CurrentAlert
}

export function ActionQueue({ alert }: ActionQueueProps) {
  const mutation = useAlertLifecycleMutation()

  if (alert.status === 'resolved') return null

  const action = alert.status === 'detected' ? 'acknowledge' : 'resolve'
  const actionLabel = action === 'acknowledge' ? 'Acknowledge alert' : 'Resolve alert'
  const submit = () => {
    mutation.mutate(createAlertLifecycleCommand(alert.alert_id, action))
  }
  const retry = () => {
    if (mutation.variables !== undefined) mutation.mutate(mutation.variables)
  }

  return (
    <Stack spacing={1}>
      {mutation.isError ? (
        <Alert severity="error">{actionLabel} failed. Retry the unchanged command.</Alert>
      ) : null}
      <Stack direction="row" spacing={1} useFlexGap sx={{ flexWrap: 'wrap' }}>
        <Button variant="contained" onClick={submit} disabled={mutation.isPending}>
          {actionLabel}
        </Button>
        {mutation.isError && mutation.variables !== undefined ? (
          <Button onClick={retry}>Retry {action}</Button>
        ) : null}
      </Stack>
    </Stack>
  )
}
