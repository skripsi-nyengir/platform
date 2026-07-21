import { Box, Paper, Stack, Typography } from '@mui/material'
import type { ApiError } from '../../api/errors'
import { ApiErrorPanel } from '../../components/states/ApiErrorPanel'
import { EmptyState } from '../../components/states/EmptyState'
import { PanelSkeleton } from '../../components/states/PanelSkeleton'
import type { MissingnessSummary } from '../../contracts/eda'
import { tokens } from '../../theme/tokens'

const technicalTextSx = {
  fontFamily: tokens.font.data,
  fontVariantNumeric: 'tabular-nums',
  overflowWrap: 'anywhere',
} as const

export interface MissingnessPanelProps {
  missingness?: readonly MissingnessSummary[]
  loading: boolean
  error?: ApiError
  onRetry: () => void
}

export function MissingnessPanel({ missingness, loading, error, onRetry }: MissingnessPanelProps) {
  return (
    <Paper
      component="section"
      aria-labelledby="missingness"
      variant="outlined"
      sx={{ minWidth: 0, p: 4 }}
    >
      <Stack spacing={2}>
        <Typography id="missingness" variant="h2">Missingness</Typography>
        <Typography variant="body2" color="text.secondary">
          Null field values are counted separately from absent samples.
        </Typography>
        {loading ? <PanelSkeleton label="Loading missingness" /> : null}
        {error === undefined ? null : <ApiErrorPanel error={error} onRetry={onRetry} />}
        {missingness === undefined ? null : missingness.length === 0 ? (
          <EmptyState
            title="No missingness rows returned"
            detail="The selected bounded sample contains no field-level summary rows."
          />
        ) : (
          <Stack spacing={1}>
            {missingness.map((item) => (
              <Typography key={item.field} variant="body2">
                <Box component="span" sx={technicalTextSx}>{item.field}</Box>: <Box component="span" sx={technicalTextSx}>{item.missing_count}</Box> null field value{item.missing_count === 1 ? '' : 's'} (<Box component="span" sx={technicalTextSx}>{item.missing_pct}%</Box>)
              </Typography>
            ))}
          </Stack>
        )}
      </Stack>
    </Paper>
  )
}
