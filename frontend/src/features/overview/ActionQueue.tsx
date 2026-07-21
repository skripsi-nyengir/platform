import { Alert, Button, Stack } from '@mui/material'
import type { CurrentAlert } from '../../contracts/alerts'
import { createAlertLifecycleCommand } from '../alerts/alertCommand'
import { useAlertLifecycleMutation } from '../alerts/useAlertLifecycleMutation'

export interface ActionQueueProps {
  alert: CurrentAlert
}

export function ActionQueue({ alert }: ActionQueueProps) {
  const mutation = useAlertLifecycleMutation()

  if (alert.status !== 'detected') return null

  const acknowledge = () => {
    mutation.mutate(createAlertLifecycleCommand(alert.alert_id, 'acknowledge'))
  }
  const retry = () => {
    if (mutation.variables !== undefined) mutation.mutate(mutation.variables)
  }

  return (
    <Stack spacing={1}>
      {mutation.isError ? (
        <Alert severity="error">Acknowledgement failed. Retry the unchanged command.</Alert>
      ) : null}
      <Stack direction="row" spacing={1} useFlexGap sx={{ flexWrap: 'wrap' }}>
        <Button variant="contained" onClick={acknowledge} disabled={mutation.isPending}>
          Acknowledge alert
        </Button>
        {mutation.isError && mutation.variables !== undefined ? (
          <Button onClick={retry}>Retry acknowledgement</Button>
        ) : null}
      </Stack>
    </Stack>
  )
}
