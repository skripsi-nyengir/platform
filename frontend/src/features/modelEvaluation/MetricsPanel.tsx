import { Box, Paper, Stack, Typography } from '@mui/material'
import { tokens } from '../../theme/tokens'

const technicalTextSx = {
  fontFamily: tokens.font.data,
  fontVariantNumeric: 'tabular-nums',
  overflowWrap: 'anywhere',
} as const

export interface MetricsPanelProps {
  availableMetrics: readonly string[]
  metrics: Record<string, number>
}

export function MetricsPanel({ availableMetrics, metrics }: MetricsPanelProps) {
  const visibleMetrics = availableMetrics.filter((name) => Object.hasOwn(metrics, name))

  return (
    <section aria-labelledby="artifact-metrics">
      <Stack spacing={2}>
        <Typography id="artifact-metrics" variant="h2">
          Artifact metrics
        </Typography>
        {visibleMetrics.length === 0 ? (
          <Typography variant="body2" color="text.secondary">
            No scalar metrics are available for this artifact.
          </Typography>
        ) : (
          <Box
            component="ul"
            role="list"
            aria-label="Scalar metrics"
            sx={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(min(160px, 100%), 1fr))',
              gap: 4,
              m: 0,
              p: 0,
              minWidth: 0,
            }}
          >
            {visibleMetrics.map((name) => (
              <Paper
                component="li"
                key={name}
                variant="outlined"
                sx={{ minWidth: 0, m: 0, p: 4, listStyle: 'none' }}
              >
                <Typography variant="body1" sx={{ ...technicalTextSx, minWidth: 0 }}>
                  {name}: {metrics[name]}
                </Typography>
              </Paper>
            ))}
          </Box>
        )}
      </Stack>
    </section>
  )
}
