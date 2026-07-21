import { Box, Paper, Stack, Typography } from '@mui/material'
import type { ApiError } from '../../api/errors'
import { ApiErrorPanel } from '../../components/states/ApiErrorPanel'
import { EmptyState } from '../../components/states/EmptyState'
import { PanelSkeleton } from '../../components/states/PanelSkeleton'
import type { CandidateOutlier } from '../../contracts/eda'
import { tokens } from '../../theme/tokens'

const technicalTextSx = {
  fontFamily: tokens.font.data,
  fontVariantNumeric: 'tabular-nums',
  overflowWrap: 'anywhere',
} as const

export interface CandidateOutliersPanelProps {
  rows?: readonly CandidateOutlier[]
  loading: boolean
  error?: ApiError
  onRetry: () => void
}

export function CandidateOutliersPanel({ rows, loading, error, onRetry }: CandidateOutliersPanelProps) {
  return (
    <Paper
      component="section"
      aria-labelledby="candidate-outliers"
      variant="outlined"
      sx={{ minWidth: 0, p: 4 }}
    >
      <Stack spacing={2}>
        <Typography id="candidate-outliers" variant="h2">Candidate outliers</Typography>
        <Typography variant="body2" color="text.secondary">
          Exploratory candidates, not alert state.
        </Typography>
        {loading ? <PanelSkeleton label="Loading candidate outliers" /> : null}
        {error === undefined ? null : <ApiErrorPanel error={error} onRetry={onRetry} />}
        {rows === undefined ? null : (
          <Stack spacing={1}>
            <Typography variant="body2">
              <Box component="span" sx={technicalTextSx}>{rows.length}</Box> bounded candidate{rows.length === 1 ? '' : 's'} returned
            </Typography>
            {rows.length === 0 ? (
              <EmptyState
                title="No candidate outliers returned"
                detail="No server-defined candidates exist in this bounded selection."
              />
            ) : (
              rows.map((row) => (
                <Paper
                  component="article"
                  key={`${row.device_id}-${row.start_ts}`}
                  variant="outlined"
                  sx={{ minWidth: 0, p: 4 }}
                >
                  <Typography variant="h3">
                    Sensor <Box component="span" sx={technicalTextSx}>{row.device_id}</Box>
                  </Typography>
                  <Typography variant="body2">
                    {row.reason}; score <Box component="span" sx={technicalTextSx}>{row.score}</Box>
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    <Box component="span" sx={technicalTextSx}>{row.start_ts}</Box> to <Box component="span" sx={technicalTextSx}>{row.end_ts}</Box>
                  </Typography>
                </Paper>
              ))
            )}
          </Stack>
        )}
      </Stack>
    </Paper>
  )
}
