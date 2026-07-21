import { Box, Paper, Stack, Typography } from '@mui/material'
import type { ApiError } from '../../api/errors'
import { ApiErrorPanel } from '../../components/states/ApiErrorPanel'
import { EmptyState } from '../../components/states/EmptyState'
import { PanelSkeleton } from '../../components/states/PanelSkeleton'
import type { CoverageSummary } from '../../contracts/eda'
import { tokens } from '../../theme/tokens'

const technicalTextSx = {
  fontFamily: tokens.font.data,
  fontVariantNumeric: 'tabular-nums',
  overflowWrap: 'anywhere',
} as const

export interface CoveragePanelProps {
  coverage?: CoverageSummary
  loading: boolean
  error?: ApiError
  onRetry: () => void
}

export function CoveragePanel({ coverage, loading, error, onRetry }: CoveragePanelProps) {
  const absentSamples = coverage === undefined
    ? undefined
    : Math.max(0, coverage.expected_count - coverage.observed_count)

  return (
    <Paper
      component="section"
      aria-labelledby="quality-coverage"
      variant="outlined"
      sx={{ minWidth: 0, p: 4 }}
    >
      <Stack spacing={2}>
        <Typography id="quality-coverage" variant="h2">Quality and coverage</Typography>
        {loading ? <PanelSkeleton label="Loading quality and coverage" /> : null}
        {error === undefined ? null : <ApiErrorPanel error={error} onRetry={onRetry} />}
        {coverage === undefined ? null : (
          <>
            {coverage.observed_count === 0 ? (
              <EmptyState
                title="No EDA records returned"
                detail="0 observed readings returned. Adjust the selected time range or sensor scope."
              />
            ) : null}
            <Box
              sx={{
                display: 'grid',
                gridTemplateColumns: 'repeat(4, minmax(0, 1fr))',
                gap: 2,
                minWidth: 0,
                '& > *': { minWidth: 0 },
              }}
            >
              <Stack spacing={0.5}>
                <Typography variant="caption" color="text.secondary">Observed readings</Typography>
                <Typography variant="h3" sx={technicalTextSx}>{coverage.observed_count}</Typography>
              </Stack>
              <Stack spacing={0.5}>
                <Typography variant="caption" color="text.secondary">Expected readings</Typography>
                <Typography variant="h3" sx={technicalTextSx}>{coverage.expected_count}</Typography>
              </Stack>
              <Stack spacing={0.5}>
                <Typography variant="caption" color="text.secondary">Coverage</Typography>
                <Typography variant="h3" sx={technicalTextSx}>{coverage.coverage_pct}%</Typography>
              </Stack>
              <Stack spacing={0.5}>
                <Typography variant="caption" color="text.secondary">Sampling quality</Typography>
                <Typography variant="body2">
                  <Box component="span" sx={technicalTextSx}>{absentSamples}</Box> absent sample{absentSamples === 1 ? '' : 's'}
                </Typography>
                <Typography variant="body2">
                  <Box component="span" sx={technicalTextSx}>{coverage.gap_count}</Box> cadence gap{coverage.gap_count === 1 ? '' : 's'}
                </Typography>
              </Stack>
            </Box>
          </>
        )}
      </Stack>
    </Paper>
  )
}
