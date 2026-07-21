import {
  Box,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material'
import type { ApiError } from '../../api/errors'
import { ApiErrorPanel } from '../../components/states/ApiErrorPanel'
import { EmptyState } from '../../components/states/EmptyState'
import { PanelSkeleton } from '../../components/states/PanelSkeleton'
import type { SensorComparison } from '../../contracts/eda'
import { tokens } from '../../theme/tokens'

const technicalTextSx = {
  fontFamily: tokens.font.data,
  fontVariantNumeric: 'tabular-nums',
  overflowWrap: 'anywhere',
} as const

export interface SensorComparisonPanelProps {
  rows?: readonly SensorComparison[]
  loading: boolean
  error?: ApiError
  onRetry: () => void
}

export function SensorComparisonPanel({ rows, loading, error, onRetry }: SensorComparisonPanelProps) {
  return (
    <Paper
      component="section"
      aria-labelledby="sensor-comparison"
      variant="outlined"
      sx={{ minWidth: 0, p: 4 }}
    >
      <Stack spacing={2}>
        <Typography id="sensor-comparison" variant="h2">Sensor comparison</Typography>
        {loading ? <PanelSkeleton label="Loading sensor comparison" /> : null}
        {error === undefined ? null : <ApiErrorPanel error={error} onRetry={onRetry} />}
        {rows === undefined ? null : (
          <>
            <Typography variant="body2">
              <Box component="span" sx={technicalTextSx}>{rows.length}</Box> sensor{rows.length === 1 ? '' : 's'} returned
            </Typography>
            {rows.length === 0 ? (
              <EmptyState
                title="No sensor comparison returned"
                detail="Adjust the selected period or sensor scope."
              />
            ) : (
              <TableContainer sx={{ maxWidth: '100%', minWidth: 0 }}>
                <Table size="small" aria-label="Bounded sensor comparison">
                  <TableHead>
                    <TableRow>
                      <TableCell>Sensor</TableCell>
                      <TableCell>Samples</TableCell>
                      <TableCell>Coverage</TableCell>
                      <TableCell>Temperature mean (p05–p95)</TableCell>
                      <TableCell>RH mean (p05–p95)</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {rows.map((row) => (
                      <TableRow key={row.device_id}>
                        <TableCell sx={technicalTextSx}>{row.device_id}</TableCell>
                        <TableCell sx={technicalTextSx}>{row.sample_count}</TableCell>
                        <TableCell sx={technicalTextSx}>{row.coverage_pct}%</TableCell>
                        <TableCell sx={technicalTextSx}>{row.temperature_c.mean} ({row.temperature_c.p05}–{row.temperature_c.p95})</TableCell>
                        <TableCell sx={technicalTextSx}>{row.relative_humidity_pct.mean} ({row.relative_humidity_pct.p05}–{row.relative_humidity_pct.p95})</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            )}
          </>
        )}
      </Stack>
    </Paper>
  )
}
