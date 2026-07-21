import { Alert, Button, Stack, Typography } from '@mui/material'
import { ApiError } from '../../api/errors'
import type { CurrentAlert } from '../../contracts/alerts'
import { createAlertLifecycleCommand } from '../alerts/alertCommand'
import { useAlertLifecycleMutation } from '../alerts/useAlertLifecycleMutation'

export interface AlertLifecycleActionsProps {
  alert: CurrentAlert
}

export function AlertLifecycleActions({ alert }: AlertLifecycleActionsProps) {
  const mutation = useAlertLifecycleMutation()
  const conflict = mutation.error instanceof ApiError && mutation.error.status === 409

  const send = (action: 'acknowledge' | 'resolve') => {
    mutation.mutate(createAlertLifecycleCommand(alert.alert_id, action))
  }
  const retry = () => {
    if (mutation.variables !== undefined) mutation.mutate(mutation.variables)
  }

  return (
    <Stack spacing={1} aria-busy={mutation.isPending}>
      {mutation.isPending ? (
        <Typography role="status" variant="caption" color="text.secondary">
          Action pending. The confirmed alert state is unchanged.
        </Typography>
      ) : null}
      {mutation.isError ? (
        conflict ? (
          <Alert severity="warning">
            <strong>{mutation.error.problem?.title ?? 'Lifecycle conflict'} (409)</strong>
            <br />
            {mutation.error.problem?.detail ?? mutation.error.message}
            <br />
            The confirmed current state was refreshed. Review it before taking another action.
          </Alert>
        ) : (
          <Alert severity="error">
            <strong>{mutation.error.problem?.title ?? 'Alert action failed'}</strong>
            <br />
            {mutation.error.problem?.detail ?? mutation.error.message}
            <br />
            Retry sends the original command unchanged.
          </Alert>
        )
      ) : null}
      <Stack
        direction="row"
        spacing={1}
        useFlexGap
        sx={{ minWidth: 0, flexWrap: 'wrap' }}
      >
        {alert.status === 'detected' ? (
          <Button
            variant="contained"
            disabled={mutation.isPending}
            onClick={() => send('acknowledge')}
          >
            Acknowledge alert
          </Button>
        ) : null}
        {alert.status === 'acknowledged' ? (
          <Button
            variant="contained"
            disabled={mutation.isPending}
            onClick={() => send('resolve')}
          >
            Resolve alert
          </Button>
        ) : null}
        {mutation.isError && mutation.variables !== undefined && !conflict ? (
          <Button onClick={retry}>Retry action</Button>
        ) : null}
      </Stack>
    </Stack>
  )
}
