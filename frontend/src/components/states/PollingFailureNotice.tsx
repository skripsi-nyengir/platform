import { Alert, Button } from '@mui/material'

export interface PollingFailureNoticeProps {
  resource: string
  lastUpdated: string
  onRetry: () => void
}

export function PollingFailureNotice({
  resource,
  lastUpdated,
  onRetry,
}: PollingFailureNoticeProps) {
  return (
    <Alert
      severity="warning"
      role="alert"
      action={
        <Button color="inherit" onClick={onRetry}>
          Retry
        </Button>
      }
    >
      <strong>{resource} refresh failed</strong>
      <br />
      Showing retained data from {lastUpdated}. Current data may be outdated or unknown.
    </Alert>
  )
}
