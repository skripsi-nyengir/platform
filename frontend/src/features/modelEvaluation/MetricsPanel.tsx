import { Box, Paper, Stack, Typography } from '@mui/material'
import type { ModelEvaluationDetail } from '../../contracts/modelEvaluation'
import { tokens } from '../../theme/tokens'

const technicalTextSx = {
  fontFamily: tokens.font.data,
  fontVariantNumeric: 'tabular-nums',
  overflowWrap: 'anywhere',
} as const

export interface MetricsPanelProps {
  artifact: ModelEvaluationDetail
}

export function MetricsPanel({ artifact }: MetricsPanelProps) {
  const comparison =
    artifact.threshold_policy.comparator ?? artifact.threshold_policy.comparison ?? 'unspecified'
  const facts = [
    ['Threshold', artifact.threshold],
    ['Observed windows', artifact.n_val_windows.toLocaleString('en-US')],
    ['Evaluation kind', artifact.evaluation_kind],
    ['Report source', artifact.report_source],
    ['Threshold comparison', String(comparison)],
  ] as const

  return (
    <section aria-labelledby="calibration-facts">
      <Stack spacing={2}>
        <Typography id="calibration-facts" variant="h2">
          Calibration facts
        </Typography>
        <Box
          component="ul"
          role="list"
          aria-label="Calibration facts"
          sx={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(min(160px, 100%), 1fr))',
            gap: 4,
            m: 0,
            p: 0,
            minWidth: 0,
          }}
        >
          {facts.map(([label, value]) => (
            <Paper
              component="li"
              key={label}
              variant="outlined"
              sx={{ minWidth: 0, m: 0, p: 4, listStyle: 'none' }}
            >
              <Typography variant="caption" color="text.secondary">{label}</Typography>
              <Typography variant="body1" sx={{ ...technicalTextSx, minWidth: 0 }}>
                {value}
              </Typography>
            </Paper>
          ))}
        </Box>
        <Typography variant="body2" color="text.secondary">
          {artifact.summary}
        </Typography>
      </Stack>
    </section>
  )
}
