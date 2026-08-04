import { Stack } from '@mui/material'
import type { SystemStatusResponse } from '../../contracts/systemHealth'
import type { StatusDisplayMeta } from './displayMeta'
import { ServiceStatusGrid } from './ServiceStatusTable'
import { StatusSnapshot } from './StatusSnapshot'

export interface SystemHealthDashboardProps {
  snapshot: SystemStatusResponse
  display: StatusDisplayMeta
  onRetry?: () => void
}

export function SystemHealthDashboard({ snapshot, display, onRetry }: SystemHealthDashboardProps) {
  return (
    <Stack
      component="section"
      aria-label={display.retained ? 'System health retained last known snapshot' : 'System health current snapshot'}
      spacing={4}
      sx={{ minWidth: 0 }}
    >
      <StatusSnapshot
        snapshot={snapshot}
        display={display}
        density="detailed"
        onRetry={onRetry}
      />
      <ServiceStatusGrid services={snapshot.services} retained={display.retained} />
    </Stack>
  )
}
