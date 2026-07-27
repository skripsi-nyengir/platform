import {
  FormControl,
  InputLabel,
  Paper,
  Select,
  Stack,
  TextField,
  Typography,
} from '@mui/material'
import { useId, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { EmptyState } from '../components/states/EmptyState'
import { ApiErrorPanel } from '../components/states/ApiErrorPanel'
import { PanelSkeleton } from '../components/states/PanelSkeleton'
import { PollingFailureNotice } from '../components/states/PollingFailureNotice'
import {
  AlertStatusSchema,
  SensorIdSchema,
  sensorIds,
  sensorLabels,
  type AlertStatus,
} from '../contracts/common'
import { AlertEventHistory } from '../features/alerts-ui/AlertEventHistory'
import { AlertsGrid } from '../features/alerts-ui/AlertsGrid'
import { useCurrentAlertsQuery } from '../features/alerts/queries'
import { parseUrlFilters, updateUrlFilters } from '../features/filters/urlFilters'
import { tokens } from '../theme/tokens'

export function AlertsPage() {
  const [params, setParams] = useSearchParams()
  const filters = parseUrlFilters(params)
  const [status, setStatus] = useState<AlertStatus>()
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(25)
  const [selectedAlertId, setSelectedAlertId] = useState<string>()
  const sensorId = useId()
  const sensorLabelId = useId()
  const statusId = useId()
  const statusLabelId = useId()
  const currentAlerts = useCurrentAlertsQuery({
    deviceId: filters.sensor,
    status,
    page,
    pageSize,
  })

  const resetCurrentView = () => {
    setPage(1)
    setSelectedAlertId(undefined)
  }

  return (
    <Stack spacing={6}>
      <Stack spacing={0.5}>
        <Typography variant="h1">Alerts</Typography>
        <Typography color="text.secondary" variant="body2">Episode skor historis · Asia/Jakarta (WIB)</Typography>
        <Typography color="text.secondary" variant="body2">
          Waktu episode ditampilkan dalam WIB; waktu lifecycle adalah UTC; provenance per episode
          berasal dari API.
        </Typography>
      </Stack>

      <Paper component="section" aria-label="Alert filters" variant="outlined" sx={{ p: 4 }}>
        <Stack
          role="group"
          aria-label="Alert filters"
          direction="row"
          spacing={2}
          useFlexGap
          sx={{
            width: '100%',
            minWidth: 0,
            alignItems: 'center',
            flexWrap: 'wrap',
            rowGap: 1,
            '& > .MuiFormControl-root': { minWidth: 136 },
            '& > .MuiTextField-root': {
              flex: '1 1 220px',
              minWidth: 220,
              maxWidth: 320,
            },
            '& .MuiInputBase-root': {
              fontFamily: tokens.font.data,
              fontVariantNumeric: 'tabular-nums',
            },
          }}
        >
          <FormControl size="small">
            <InputLabel id={sensorLabelId} htmlFor={sensorId} shrink>Sensor</InputLabel>
            <Select<string>
              native
              id={sensorId}
              labelId={sensorLabelId}
              label="Sensor"
              value={filters.sensor ?? ''}
              onChange={(event) => {
                const parsed = SensorIdSchema.safeParse(event.target.value)
                setParams(updateUrlFilters(params, {
                  sensor: parsed.success ? parsed.data : undefined,
                }))
                resetCurrentView()
              }}
            >
              <option value="">All sensors</option>
               {sensorIds.map((sensor) => (
                 <option key={sensor} value={sensor}>{sensorLabels[sensor]}</option>
              ))}
            </Select>
          </FormControl>
          <FormControl size="small">
            <InputLabel id={statusLabelId} htmlFor={statusId} shrink>Status</InputLabel>
            <Select<string>
              native
              id={statusId}
              labelId={statusLabelId}
              label="Status"
              value={status ?? ''}
              onChange={(event) => {
                const parsed = AlertStatusSchema.safeParse(event.target.value)
                setStatus(parsed.success ? parsed.data : undefined)
                resetCurrentView()
              }}
            >
              <option value="">All statuses</option>
              <option value="detected">Active</option>
              <option value="acknowledged">Acknowledged</option>
              <option value="resolved">Resolved</option>
            </Select>
          </FormControl>
          <TextField
            size="small"
            label="From"
            type="text"
            value={filters.from}
            onChange={(event) => setParams(updateUrlFilters(params, { from: event.target.value }))}
          />
          <TextField
            size="small"
            label="To"
            type="text"
            value={filters.to}
            onChange={(event) => setParams(updateUrlFilters(params, { to: event.target.value }))}
          />
        </Stack>
      </Paper>

      <section aria-labelledby="current-alerts-heading">
        <Stack spacing={2}>
          <Typography id="current-alerts-heading" variant="h2">Current alerts</Typography>
          {currentAlerts.data === undefined ? (
            currentAlerts.isError ? (
              <ApiErrorPanel error={currentAlerts.error} onRetry={() => void currentAlerts.refetch()} />
            ) : (
              <PanelSkeleton label="Loading current alerts" />
            )
          ) : (
            <>
              {currentAlerts.isRefetchError ? (
                <PollingFailureNotice
                  resource="Current alerts"
                  lastUpdated={currentAlerts.data.generated_at}
                  onRetry={() => void currentAlerts.refetch()}
                />
              ) : null}
              {currentAlerts.data.items.length === 0 ? (
                <EmptyState
                  title="No current alerts returned"
                  detail="Adjust the selected sensor or status."
                />
              ) : (
                <AlertsGrid
                  response={currentAlerts.data}
                  page={page}
                  onPageChange={(nextPage) => {
                    setPage(nextPage)
                    setSelectedAlertId(undefined)
                  }}
                  onPageSizeChange={(nextPageSize) => {
                    setPage(1)
                    setPageSize(nextPageSize)
                    setSelectedAlertId(undefined)
                  }}
                  onSelectAlert={setSelectedAlertId}
                />
              )}
            </>
          )}
        </Stack>
      </section>

      <AlertEventHistory
        alertId={selectedAlertId}
        deviceId={filters.sensor}
        from={filters.from}
        to={filters.to}
      />
    </Stack>
  )
}
