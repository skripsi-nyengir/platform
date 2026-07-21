import { Alert, Button } from '@mui/material'
import type { ApiError } from '../../api/errors'

export interface ApiErrorPanelProps {
  error: ApiError
  onRetry: () => void
}

export function ApiErrorPanel({ error, onRetry }: ApiErrorPanelProps) {
  const requestId = error.requestId ?? error.problem?.request_id

  return (
    <Alert
      severity="error"
      role="alert"
      action={
        <Button color="inherit" onClick={onRetry}>
          Retry
        </Button>
      }
    >
      <strong>{error.problem?.title ?? 'Data request failed'}</strong>
      <br />
      {error.problem?.detail ?? error.message}
      {requestId === undefined ? null : (
        <>
          <br />
          Request ID: {requestId}
        </>
      )}
    </Alert>
  )
}
