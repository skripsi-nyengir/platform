import { Card, CardContent, Chip, Paper, Stack, Typography } from '@mui/material'
import { EmptyState } from '../../components/states/EmptyState'
import type {
  LivenessState,
  ReadinessState,
  SystemServiceStatus,
} from '../../contracts/systemHealth'
import { tokens } from '../../theme/tokens'

const technicalTextSx = {
  fontFamily: tokens.font.data,
  fontVariantNumeric: 'tabular-nums',
  overflowWrap: 'anywhere',
} as const

const serviceLabels: Readonly<Record<string, string>> = Object.freeze({
  api: 'API',
  database: 'Database',
  'live-subscriber': 'Live telemetry subscriber',
  'preview-worker': 'Preview worker',
  'active-selection': 'Active model selection',
})

const livenessLabels: Readonly<Record<LivenessState, string>> = Object.freeze({
  alive: 'Alive',
  not_alive: 'Not alive',
  unknown: 'Unknown',
})

const readinessLabels: Readonly<Record<ReadinessState, string>> = Object.freeze({
  ready: 'Ready',
  not_ready: 'Not ready',
  unknown: 'Unknown',
})

function stateColor(state: LivenessState | ReadinessState) {
  if (state === 'alive' || state === 'ready') return 'success' as const
  if (state === 'not_alive') return 'error' as const
  if (state === 'not_ready') return 'warning' as const
  return 'default' as const
}

function StateChip({
  kind,
  state,
  retained,
}: {
  kind: 'Liveness' | 'Readiness'
  state: LivenessState | ReadinessState
  retained: boolean
}) {
  const label = kind === 'Liveness'
    ? livenessLabels[state as LivenessState]
    : readinessLabels[state as ReadinessState]

  return (
    <Chip
      size="small"
      variant={retained ? 'outlined' : 'filled'}
      color={retained ? 'default' : stateColor(state)}
      label={`${kind}: ${retained ? 'Last known · ' : ''}${label}`}
    />
  )
}

export interface ServiceStatusGridProps {
  services: readonly SystemServiceStatus[]
  retained?: boolean
}

export function ServiceStatusGrid({ services, retained = false }: ServiceStatusGridProps) {
  const readinessCounts = services.reduce(
    (counts, service) => ({ ...counts, [service.readiness]: counts[service.readiness] + 1 }),
    { ready: 0, not_ready: 0, unknown: 0 },
  )

  return (
    <Paper
      component="section"
      aria-labelledby="service-status-heading"
      variant="outlined"
      sx={{ minWidth: 0, p: { xs: 3, md: 4 } }}
    >
      <Stack spacing={3}>
        <Stack spacing={0.5}>
          <Typography id="service-status-heading" variant="h2">
            {retained ? 'Last known service status' : 'Service status'}
          </Typography>
          <Typography color="text.secondary" variant="body2">
            {retained
              ? 'Historical service states are shown in the order reported by the retained snapshot.'
              : 'Services are shown in the order reported by the status API.'}
          </Typography>
          <Stack
            aria-label={retained ? 'Last known service readiness counts' : 'Service readiness counts'}
            direction="row"
            role="group"
            spacing={1}
            useFlexGap
            sx={{ flexWrap: 'wrap', pt: 1 }}
          >
            <Chip size="small" variant="outlined" color={retained ? 'default' : 'success'} label={`Ready ${readinessCounts.ready}`} />
            <Chip size="small" variant="outlined" color={retained ? 'default' : 'warning'} label={`Not ready ${readinessCounts.not_ready}`} />
            <Chip size="small" variant="outlined" label={`Unknown ${readinessCounts.unknown}`} />
          </Stack>
        </Stack>

        {services.length === 0 ? (
          <EmptyState
            title="No service status available"
            detail="The status snapshot did not report any services."
          />
        ) : (
          <Stack
            data-testid="service-status-grid"
            sx={{
              display: 'grid',
              gap: 2,
              gridTemplateColumns: {
                xs: 'minmax(0, 1fr)',
                md: 'repeat(2, minmax(0, 1fr))',
                lg: 'repeat(3, minmax(0, 1fr))',
              },
              minWidth: 0,
            }}
          >
            {services.map((service, index) => (
              <Card
                component="article"
                data-service-name={service.name}
                key={`${service.name}:${index}`}
                variant="outlined"
                sx={{ height: '100%', minWidth: 0 }}
              >
                <CardContent sx={{ height: '100%' }}>
                  <Stack spacing={2} sx={{ height: '100%', minWidth: 0 }}>
                    <Stack spacing={0.25}>
                      <Typography variant="h3">
                        {serviceLabels[service.name] ?? service.name}
                      </Typography>
                      {serviceLabels[service.name] === undefined ? null : (
                        <Typography color="text.secondary" variant="caption" sx={technicalTextSx}>
                          {service.name}
                        </Typography>
                      )}
                    </Stack>
                    <Stack direction="row" spacing={1} useFlexGap sx={{ flexWrap: 'wrap' }}>
                      <StateChip kind="Liveness" state={service.liveness} retained={retained} />
                      <StateChip kind="Readiness" state={service.readiness} retained={retained} />
                    </Stack>
                    <Typography variant="body2" sx={{ overflowWrap: 'anywhere' }}>
                      {service.detail}
                    </Typography>
                    <Typography color="text.secondary" variant="caption" sx={{ ...technicalTextSx, mt: 'auto' }}>
                      Checked at (UTC): {service.checked_at}
                    </Typography>
                  </Stack>
                </CardContent>
              </Card>
            ))}
          </Stack>
        )}
      </Stack>
    </Paper>
  )
}
