import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  Paper,
  Stack,
  Typography,
} from '@mui/material'
import type { ReactNode } from 'react'
import type { SystemStatusResponse } from '../../contracts/systemHealth'
import { tokens } from '../../theme/tokens'
import type { StatusDisplayMeta } from './displayMeta'
import { formatDuration } from './duration'

const technicalTextSx = {
  fontFamily: tokens.font.data,
  fontVariantNumeric: 'tabular-nums',
  overflowWrap: 'anywhere',
} as const

const summaryLabelSx = {
  fontWeight: 700,
  letterSpacing: '0.08em',
  textTransform: 'uppercase',
} as const

const classificationLabels = {
  healthy: 'Healthy',
  degraded: 'Degraded',
  failed: 'Failed',
} as const

const connectionLabels = {
  connected: 'Connected',
  subscribed: 'Subscribed',
  disconnected: 'Disconnected',
  unknown: 'Unknown',
} as const

export type StatusSnapshotDensity = 'compact' | 'detailed'

export interface StatusSnapshotProps {
  snapshot: SystemStatusResponse
  display: StatusDisplayMeta
  density: StatusSnapshotDensity
  onRetry?: () => void
}

function MetricCard({
  label,
  retained,
  children,
}: {
  label: string
  retained: boolean
  children: ReactNode
}) {
  const displayedLabel = retained ? `Last known · ${label}` : label

  return (
    <Card component="article" aria-label={displayedLabel} variant="outlined" sx={{ height: '100%', minWidth: 0 }}>
      <CardContent sx={{ height: '100%' }}>
        <Stack spacing={1} sx={{ height: '100%' }}>
          <Typography color="text.secondary" component="h3" variant="caption" sx={summaryLabelSx}>
            {displayedLabel}
          </Typography>
          {children}
        </Stack>
      </CardContent>
    </Card>
  )
}

function MetricValue({ children }: { children: ReactNode }) {
  return (
    <Typography
      component="p"
      sx={{
        ...technicalTextSx,
        fontSize: tokens.font.size.summaryValue,
        fontWeight: 700,
        lineHeight: tokens.font.lineHeight.summaryValue,
      }}
    >
      {children}
    </Typography>
  )
}

function Counter({ label, value }: { label: string; value: number }) {
  return (
    <Stack spacing={0.25} sx={{ minWidth: 0 }}>
      <Typography component="span" variant="h3" sx={technicalTextSx}>{value}</Typography>
      <Typography color="text.secondary" component="span" variant="caption">{label}</Typography>
    </Stack>
  )
}

function DetailLine({ label, value }: { label: string; value: ReactNode }) {
  return (
    <Typography variant="body2" sx={technicalTextSx}>
      {label}: {value}
    </Typography>
  )
}

function EvidenceItem({ label, value }: { label: string; value: string }) {
  return (
    <Stack spacing={0.5} sx={{ minWidth: 0 }}>
      <Typography color="text.secondary" variant="caption" sx={summaryLabelSx}>{label}</Typography>
      <Typography variant="body2" sx={technicalTextSx}>{value}</Typography>
    </Stack>
  )
}

function DetailGroup({ title, children }: { title: string; children: ReactNode }) {
  return (
    <Stack spacing={0.75} sx={{ minWidth: 0 }}>
      <Typography variant="h3">{title}</Typography>
      {children}
    </Stack>
  )
}

function safeDiagnosticValue(value: unknown): string {
  const serialized = typeof value === 'string' ? value : JSON.stringify(value)
  if (serialized === undefined) return 'Unavailable'
  return serialized.length <= 180 ? serialized : `${serialized.slice(0, 179)}…`
}

function normalizeEvidenceText(value: string): string {
  return value.trim().replace(/\s+/g, ' ').replace(/[.!?]+$/, '').toLocaleLowerCase()
}

function uniqueReasons(snapshot: SystemStatusResponse): string[] {
  const observationStatements = new Set(
    snapshot.overall_observation
      .split(/(?<=[.!?])\s+/)
      .map(normalizeEvidenceText)
      .filter(Boolean),
  )
  const seen = new Set<string>()

  return snapshot.telemetry.reasons
    .map((reason) => reason.trim())
    .filter((reason) => {
      const normalized = normalizeEvidenceText(reason)
      if (normalized === '' || seen.has(normalized)) return false
      seen.add(normalized)
      return !observationStatements.has(normalized)
    })
}

function TechnicalDetails({ snapshot, display }: Pick<StatusSnapshotProps, 'snapshot' | 'display'>) {
  const telemetry = snapshot.telemetry
  const diagnostics = Object.entries(snapshot.diagnostics ?? {}).slice(0, 12)

  return (
    <Accordion
      disableGutters
      slots={{ heading: 'h3' }}
      variant="outlined"
      sx={{
        minWidth: 0,
        '&::before': { display: 'none' },
        '& > h3': { m: 0 },
        '&.Mui-expanded': { m: 0 },
      }}
    >
      <AccordionSummary
        aria-controls="live-health-technical-details"
        id="live-health-technical-summary"
        sx={{ minHeight: tokens.size.control, px: { xs: 2, sm: 3 } }}
      >
        <Stack direction="row" spacing={2} useFlexGap sx={{ alignItems: 'center', flexWrap: 'wrap', minWidth: 0, width: '100%' }}>
          <Typography component="span" variant="h3">
            {display.retained ? 'Last known technical details' : 'Technical details'}
          </Typography>
          <Typography color="text.secondary" variant="body2">
            Exact timestamps, raw freshness, lease, recovery, and provenance
          </Typography>
          <Typography color="primary.main" variant="body2" sx={{ fontWeight: 700, ml: 'auto' }}>
            View details
          </Typography>
        </Stack>
      </AccordionSummary>
      <AccordionDetails id="live-health-technical-details" sx={{ px: { xs: 2, sm: 3 }, pb: 3, pt: 1 }}>
        <Box
          sx={{
            display: 'grid',
            gap: 3,
            gridTemplateColumns: { xs: 'minmax(0, 1fr)', md: 'repeat(2, minmax(0, 1fr))' },
            minWidth: 0,
          }}
        >
          <DetailGroup title="Freshness evidence">
            <DetailLine label="Status checked (UTC)" value={snapshot.checked_at} />
            <DetailLine label={display.retained ? 'Snapshot retained (UTC)' : 'Snapshot displayed (UTC)'} value={display.displayedAt} />
            <DetailLine label="Status poll age" value={`${display.pollAgeSeconds} seconds`} />
            <DetailLine label="Latest telemetry (Asia/Jakarta, WIB)" value={telemetry.latest_ts ?? 'Unavailable'} />
            <DetailLine label="Telemetry age" value={telemetry.age_seconds === null ? 'Unknown' : `${telemetry.age_seconds} seconds`} />
            <DetailLine label="Last valid reading (Asia/Jakarta, WIB)" value={telemetry.last_valid_reading_ts ?? 'Unavailable'} />
          </DetailGroup>
          <DetailGroup title="Lease and handshake">
            <DetailLine label="Configuration valid" value={telemetry.configuration_valid ? 'Yes' : 'No'} />
            <DetailLine label="Lease active" value={telemetry.lease_active ? 'Yes' : 'No'} />
            <DetailLine label="Fencing token" value={telemetry.fencing_token ?? 'Unavailable'} />
            <DetailLine label="Database heartbeat (UTC)" value={telemetry.database_heartbeat ?? 'Unavailable'} />
            <DetailLine label="CONNACK received" value={telemetry.connack_received === null ? 'Unknown' : telemetry.connack_received ? 'Yes' : 'No'} />
            <DetailLine label="SUBACK received" value={telemetry.suback_received === null ? 'Unknown' : telemetry.suback_received ? 'Yes' : 'No'} />
          </DetailGroup>
          <DetailGroup title="Recovery and backlog">
            <DetailLine label="Recovery ready" value={telemetry.recovery_ready ? 'Yes' : 'No'} />
            <DetailLine label="Retry state" value={telemetry.retry_state} />
            <DetailLine label="Ingress queue" value={telemetry.ingress_queue_depth ?? 'Unavailable'} />
            <DetailLine label="Durable backlog" value={telemetry.durable_backlog_count} />
            <DetailLine label="Pending boundary" value={telemetry.pending_boundary_count} />
            <DetailLine label="Dropped newest" value={telemetry.dropped_newest_count ?? 'Unavailable'} />
            <DetailLine label="Invalid messages" value={telemetry.invalid_message_count ?? 'Unavailable'} />
            <DetailLine label="Retained messages" value={telemetry.retained_message_count ?? 'Unavailable'} />
          </DetailGroup>
          <DetailGroup title="Model and provenance">
            <DetailLine label="Active model" value={telemetry.active_model_version ?? 'Unavailable'} />
            <DetailLine label="Active scaler corpus" value={telemetry.active_scaler_corpus_id ?? 'Unavailable'} />
            <DetailLine label="Cursor timestamp (Asia/Jakarta, WIB)" value={telemetry.cursor_ts ?? 'Unavailable'} />
            <DetailLine label="Cursor ID" value={telemetry.cursor_id ?? 'Unavailable'} />
            <DetailLine label="Request ID" value={snapshot.request_id} />
            {Object.entries(telemetry.artifact_hashes).length === 0 ? (
              <DetailLine label="Artifact hashes" value="Unavailable" />
            ) : Object.entries(telemetry.artifact_hashes).map(([name, hash]) => (
              <DetailLine key={name} label={`${name} hash`} value={hash} />
            ))}
            {diagnostics.length === 0 ? (
              <DetailLine label="Diagnostics" value="Unavailable" />
            ) : diagnostics.map(([name, value]) => (
              <DetailLine key={name} label={`Diagnostic · ${name}`} value={safeDiagnosticValue(value)} />
            ))}
          </DetailGroup>
        </Box>
      </AccordionDetails>
    </Accordion>
  )
}

export function StatusSnapshot({ snapshot, display, density, onRetry }: StatusSnapshotProps) {
  const telemetry = snapshot.telemetry
  const reasons = uniqueReasons(snapshot)
  const showObservation = density === 'detailed' || telemetry.classification !== 'healthy' || display.retained

  return (
    <Paper
      component="section"
      aria-labelledby="status-snapshot-heading"
      variant="outlined"
      sx={{
        borderColor: display.retained ? 'warning.main' : 'divider',
        minWidth: 0,
        p: { xs: 2, sm: density === 'detailed' ? 4 : 3 },
      }}
    >
      <Stack spacing={density === 'detailed' ? 3 : 2}>
        <Stack direction="row" spacing={1.5} useFlexGap sx={{ alignItems: 'center', flexWrap: 'wrap' }}>
          <Typography id="status-snapshot-heading" variant="h2">Live telemetry health</Typography>
          <Chip
            size="small"
            variant={display.retained ? 'outlined' : 'filled'}
            color={display.retained
              ? 'default'
              : telemetry.classification === 'healthy'
                ? 'success'
                : telemetry.classification === 'degraded' ? 'warning' : 'error'}
            label={`${display.retained ? 'Last known · ' : ''}${classificationLabels[telemetry.classification]}`}
          />
          {density === 'detailed' && !display.retained ? (
            <Typography color="text.secondary" variant="caption">Telemetry classification only</Typography>
          ) : null}
        </Stack>

        {display.retained ? (
          <Stack role="status" direction={{ xs: 'column', sm: 'row' }} spacing={1.5} sx={{ alignItems: { sm: 'center' } }}>
            <Box sx={{ flex: 1 }}>
              <Typography color="warning.main" variant="body2" sx={{ fontWeight: 700 }}>
                Current reachability: Unknown
              </Typography>
              <Typography color="text.secondary" variant="body2">
                Showing a retained, last known snapshot. Status colors are neutralized.
              </Typography>
            </Box>
            {onRetry === undefined ? null : <Button onClick={onRetry} variant="outlined">Retry</Button>}
          </Stack>
        ) : null}

        <Box
          role="group"
          aria-label={display.retained ? 'Last known live telemetry indicators' : 'Live telemetry indicators'}
          sx={{
            display: 'grid',
            gap: 1.5,
            gridTemplateColumns: {
              xs: 'minmax(0, 1fr)',
              sm: 'repeat(2, minmax(0, 1fr))',
              lg: 'repeat(4, minmax(0, 1fr))',
            },
            minWidth: 0,
          }}
        >
          <MetricCard label="Telemetry age" retained={display.retained}>
            <MetricValue>{formatDuration(telemetry.age_seconds)}</MetricValue>
            <Typography color="text.secondary" variant="caption">Server-observed</Typography>
          </MetricCard>
          <MetricCard label="Sensor freshness" retained={display.retained}>
            <Stack direction="row" spacing={2} useFlexGap sx={{ flexWrap: 'wrap' }}>
              <Counter label="Fresh" value={telemetry.fresh_sensor_count} />
              <Counter label="Stale" value={telemetry.stale_sensor_count} />
              <Counter label="Offline" value={telemetry.offline_sensor_count} />
            </Stack>
          </MetricCard>
          <MetricCard label="Connection state" retained={display.retained}>
            <MetricValue>{display.retained ? 'Unknown' : connectionLabels[telemetry.connection_state]}</MetricValue>
            {display.retained ? (
              <Typography color="text.secondary" variant="caption">
                Last known: {connectionLabels[telemetry.connection_state]}
              </Typography>
            ) : null}
          </MetricCard>
          <MetricCard label="Status-poll freshness" retained={display.retained}>
            <MetricValue>{formatDuration(display.pollAgeSeconds)}</MetricValue>
            <Typography color="text.secondary" variant="caption">
              {display.retained ? 'Age of retained result' : 'Age of displayed result'}
            </Typography>
          </MetricCard>
        </Box>

        {showObservation ? (
          <Stack spacing={0.75}>
            <Typography color="text.secondary" variant="caption" sx={summaryLabelSx}>
              {display.retained ? 'Last known operational observation' : 'Operational observation'}
            </Typography>
            <Typography variant="body2">{snapshot.overall_observation}</Typography>
            {reasons.length === 0 ? null : (
              <Stack component="ul" spacing={0.5} sx={{ m: 0, pl: 2.5 }}>
                {reasons.map((reason) => (
                  <Typography component="li" color="warning.main" key={reason} variant="body2">
                    {reason}
                  </Typography>
                ))}
              </Stack>
            )}
          </Stack>
        ) : null}

        {density === 'detailed' ? (
          <Box
            component="section"
            aria-label="Snapshot evidence"
            sx={{
              display: 'grid',
              gap: 2,
              gridTemplateColumns: { xs: 'minmax(0, 1fr)', md: 'repeat(3, minmax(0, 1fr))' },
              minWidth: 0,
            }}
          >
            <EvidenceItem label="Status checked (UTC)" value={snapshot.checked_at} />
            <EvidenceItem label={display.retained ? 'Snapshot retained (UTC)' : 'Snapshot displayed (UTC)'} value={display.displayedAt} />
            <EvidenceItem label="Latest telemetry (Asia/Jakarta, WIB)" value={telemetry.latest_ts ?? 'Unavailable'} />
          </Box>
        ) : null}

        {density === 'detailed' ? <TechnicalDetails snapshot={snapshot} display={display} /> : null}
      </Stack>
    </Paper>
  )
}
