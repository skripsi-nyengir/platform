import {
  Alert,
  Box,
  Card,
  CardContent,
  Chip,
  Grid,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from '@mui/material'
import type {
  SimulationMetricsResponse,
  SimulationScopeMetrics,
  SimulationBucketHours,
} from '../../contracts/simulation'
import { tokens } from '../../theme/tokens'

const technicalTextSx = {
  fontFamily: tokens.font.data,
  fontVariantNumeric: 'tabular-nums',
} as const

function formatPercent(value: number): string {
  return value.toLocaleString('id-ID', {
    style: 'percent',
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  })
}

function formatScore(value: number): string {
  return Math.abs(value) < 0.001
    ? value.toExponential(3)
    : value.toLocaleString('id-ID', { maximumFractionDigits: 6 })
}

const bucketIntervals = [
  { hours: 24, label: 'Per hari' },
  { hours: 6, label: 'Per 6 jam' },
  { hours: 1, label: 'Per jam' },
] as const satisfies readonly { hours: SimulationBucketHours; label: string }[]

function formatBucketDateTime(value: string): string {
  return new Intl.DateTimeFormat('id-ID', {
    timeZone: 'Asia/Jakarta',
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(`${value}+07:00`))
}

function ScopeCard({
  label,
  detail,
  metrics,
  primary = false,
}: {
  label: string
  detail: string
  metrics: SimulationScopeMetrics
  primary?: boolean
}) {
  const measures = [
    ['Precision', metrics.precision],
    ['Recall', metrics.recall],
    ['F1', metrics.f1],
  ] as const

  return (
    <Card
      component="article"
      variant="outlined"
      sx={{
        height: '100%',
        borderTop: `${tokens.size.activeRule}px solid`,
        borderTopColor: primary ? 'primary.main' : 'divider',
        backgroundColor: primary ? tokens.color.signalSoft : 'background.paper',
      }}
    >
      <CardContent sx={{ p: 3, '&:last-child': { pb: 3 } }}>
        <Stack spacing={2}>
          <Stack direction="row" spacing={1} useFlexGap sx={{ alignItems: 'center', flexWrap: 'wrap' }}>
            <Typography variant="h3">{label}</Typography>
            {primary ? <Chip label="Primary thesis metric" color="primary" size="small" /> : null}
          </Stack>
          <Typography variant="body2" color="text.secondary">{detail}</Typography>
          {primary ? (
            <Stack spacing={0.5}>
              <Typography variant="caption" color="text.secondary">Headline F1</Typography>
              <Typography
                sx={{
                  ...technicalTextSx,
                  fontSize: tokens.font.size.summaryValue,
                  fontWeight: 700,
                  lineHeight: tokens.font.lineHeight.summaryValue,
                }}
              >
                {formatPercent(metrics.f1)}
              </Typography>
            </Stack>
          ) : null}
          <Box
            component="dl"
            sx={{
              display: 'grid',
              gridTemplateColumns: 'repeat(3, minmax(0, 1fr))',
              gap: 2,
              m: 0,
            }}
          >
            {measures.map(([name, value]) => (
              <Box key={name}>
                <Typography component="dt" variant="caption" color="text.secondary">{name}</Typography>
                <Typography component="dd" sx={{ ...technicalTextSx, m: 0, fontWeight: 700 }}>
                  {formatPercent(value)}
                </Typography>
              </Box>
            ))}
          </Box>
          <Typography variant="body2" color="text.secondary" sx={technicalTextSx}>
            TN {metrics.tn.toLocaleString('id-ID')} · FP {metrics.fp.toLocaleString('id-ID')} · FN {metrics.fn.toLocaleString('id-ID')} · TP {metrics.tp.toLocaleString('id-ID')}
          </Typography>
          <Typography variant="caption" color="text.secondary" sx={technicalTextSx}>
            {metrics.n_evaluated.toLocaleString('id-ID')} evaluated · {metrics.n_anomalous.toLocaleString('id-ID')} anomalous
          </Typography>
        </Stack>
      </CardContent>
    </Card>
  )
}

export function SimulationMetricsPanels({
  metrics,
  bucketHours,
  onBucketHoursChange,
}: {
  metrics: SimulationMetricsResponse
  bucketHours: SimulationBucketHours
  onBucketHoursChange: (value: SimulationBucketHours) => void
}) {
  const scopes = [
    {
      label: 'Timestamp scope',
      detail: 'Scores each corpus timestamp against the injected ground truth at that instant.',
      metrics: metrics.timestamp_scope,
    },
    {
      label: 'Overlapping model windows',
      detail: 'Credits a scored model window when it overlaps an injected event interval.',
      metrics: metrics.overlapping_scope,
    },
    {
      label: 'Non-overlapping evaluation bins',
      detail: 'Measures disjoint evaluation bins so repeated overlapping windows do not double-count evidence.',
      metrics: metrics.bins_scope,
      primary: true,
    },
  ] as const

  return (
    <Stack spacing={3}>
      <Alert severity="info" role="note">
        Research metrics measure offline accuracy against known injected events; the primary F1 uses non-overlapping bins. Operational metrics count the discrete alerts an operator would see after consecutive abnormal points are merged.
      </Alert>

      <Paper component="section" aria-labelledby="research-scoreboard-heading" variant="outlined" sx={{ p: 4 }}>
        <Stack spacing={3}>
          <Stack spacing={0.5}>
            <Typography id="research-scoreboard-heading" variant="h2">Research scoreboard</Typography>
            <Typography variant="body2" color="text.secondary">
              Offline accuracy across {metrics.event_count.toLocaleString('id-ID')} known injection events and {metrics.frame_count.toLocaleString('id-ID')} corpus frames.
            </Typography>
          </Stack>
          <Grid container spacing={2}>
            {scopes.map((scope) => (
              <Grid key={scope.metrics.scope} size={{ sm: 12, lg: 4 }}>
                <ScopeCard {...scope} />
              </Grid>
            ))}
          </Grid>
          <Typography variant="caption" color="text.secondary" sx={technicalTextSx}>
            {metrics.scored_windows.toLocaleString('id-ID')} scored windows · threshold {String(metrics.threshold)} · window size {metrics.window_size}
          </Typography>
        </Stack>
      </Paper>

      <Paper component="section" aria-labelledby="operational-events-heading" variant="outlined" sx={{ p: 4 }}>
        <Grid container spacing={3}>
          <Grid size={{ sm: 12, lg: 3 }}>
            <Stack spacing={1}>
              <Typography id="operational-events-heading" variant="h2">Operational alerts</Typography>
              <Typography
                sx={{
                  ...technicalTextSx,
                  color: 'warning.main',
                  fontSize: tokens.font.size.summaryValue,
                  fontWeight: 700,
                  lineHeight: tokens.font.lineHeight.summaryValue,
                }}
              >
                {metrics.operational_event_count.toLocaleString('id-ID')}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Discrete alert events after merging consecutive abnormal candidates with the configured cooldown.
              </Typography>
            </Stack>
          </Grid>
          <Grid size={{ sm: 12, lg: 9 }}>
            <Stack spacing={3}>
              <Stack spacing={1}>
                <Stack
                  direction="row"
                  spacing={2}
                  useFlexGap
                  sx={{ alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap' }}
                >
                  <Stack spacing={0.25}>
                    <Typography variant="h3">Alerts by period</Typography>
                    <Typography variant="caption" color="text.secondary">
                      Zero-count periods remain visible for a continuous operational timeline.
                    </Typography>
                  </Stack>
                  <ToggleButtonGroup
                    exclusive
                    size="small"
                    value={bucketHours}
                    aria-label="Interval operasional"
                    onChange={(_, value: SimulationBucketHours | null) => {
                      if (value !== null) onBucketHoursChange(value)
                    }}
                  >
                    {bucketIntervals.map((interval) => (
                      <ToggleButton
                        key={interval.hours}
                        value={interval.hours}
                        aria-label={interval.label}
                      >
                        {interval.label}
                      </ToggleButton>
                    ))}
                  </ToggleButtonGroup>
                </Stack>
                <TableContainer sx={{ maxHeight: tokens.size.control * 6 }}>
                  <Table stickyHeader size="small" aria-label="Operational alerts by period">
                    <TableHead>
                      <TableRow>
                        <TableCell>Period start (WIB)</TableCell>
                        <TableCell>Period end (WIB)</TableCell>
                        <TableCell align="right">Alerts</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {metrics.operational_buckets.map((bucket) => (
                        <TableRow key={bucket.bucket_start}>
                          <TableCell sx={technicalTextSx}>{formatBucketDateTime(bucket.bucket_start)}</TableCell>
                          <TableCell sx={technicalTextSx}>{formatBucketDateTime(bucket.bucket_end)}</TableCell>
                          <TableCell align="right" sx={technicalTextSx}>{bucket.event_count}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              </Stack>

              {metrics.operational_events.length === 0 ? (
                <Typography variant="body2" color="text.secondary">No operational alert events were produced.</Typography>
              ) : (
                <Stack spacing={1}>
                  <Typography variant="h3">Merged alert events</Typography>
                <Typography variant="caption" color="text.secondary">
                  Scroll to inspect all {metrics.operational_event_count.toLocaleString('id-ID')} merged alert events.
                </Typography>
                <TableContainer sx={{ maxHeight: tokens.size.control * 8 }}>
                  <Table stickyHeader size="small" aria-label="Operational alert events">
                    <TableHead>
                      <TableRow>
                        <TableCell>Event</TableCell>
                        <TableCell>Segment</TableCell>
                        <TableCell>Index span</TableCell>
                        <TableCell align="right">Candidates</TableCell>
                        <TableCell align="right">Peak score</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {metrics.operational_events.map((event, index) => (
                        <TableRow key={`${event.segment_id}:${event.start_idx}:${event.end_idx}`}>
                          <TableCell sx={technicalTextSx}>{index + 1}</TableCell>
                          <TableCell sx={technicalTextSx}>{event.segment_id}</TableCell>
                          <TableCell sx={technicalTextSx}>{event.start_idx}–{event.end_idx}</TableCell>
                          <TableCell align="right" sx={technicalTextSx}>{event.n_candidates}</TableCell>
                          <TableCell align="right" sx={technicalTextSx}>{formatScore(event.peak_score)}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              </Stack>
              )}
            </Stack>
          </Grid>
        </Grid>
      </Paper>
    </Stack>
  )
}
