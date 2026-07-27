import {
  Box,
  Button,
  FormControl,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material'
import { alpha, useTheme } from '@mui/material/styles'
import type { GridColDef } from '@mui/x-data-grid'
import { useId, useState } from 'react'
import { ApiError } from '../../api/errors'
import {
  buildWeekdayHourMatrix,
  formatTemporalPercent,
  temporalViews,
  weekdayLabels,
  type TemporalView,
  type WeekdayHourCell,
} from '../../components/charts/temporalEdaOptions'
import { BoundedDataDialog } from '../../components/data/BoundedDataDialog'
import { ApiErrorPanel } from '../../components/states/ApiErrorPanel'
import { EmptyState } from '../../components/states/EmptyState'
import { PanelSkeleton } from '../../components/states/PanelSkeleton'
import { tokens } from '../../theme/tokens'
import { useEdaSectionQuery } from './queries'
import { formatEdaReasonDetail } from './reasonLabels'

export interface WeekdayHourCoveragePanelProps {
  runId: string | null
}

const viewLabels: Record<TemporalView, string> = {
  resolved_raw_pairs: 'Cakupan pasangan exact',
  rule_screened_pairs: 'Retensi setelah screening',
}

const technicalTextSx = {
  fontFamily: tokens.font.data,
  fontVariantNumeric: 'tabular-nums',
  overflowWrap: 'anywhere',
} as const

const matrixColumns: readonly GridColDef<WeekdayHourCell>[] = [
  { field: 'weekdayLabel', headerName: 'Hari', flex: 1 },
  { field: 'hour', headerName: 'Jam lokal', flex: 1 },
  { field: 'exactPairCount', headerName: 'Pasangan exact', flex: 1 },
  { field: 'viewPairCount', headerName: 'Pasangan view', flex: 1 },
  { field: 'expectedSlots', headerName: 'Slot harapan', flex: 1 },
  {
    field: 'coverage',
    headerName: 'Cakupan exact',
    flex: 1,
    valueFormatter: (value: number | null) => formatTemporalPercent(value),
  },
  {
    field: 'retention',
    headerName: 'Retensi view',
    flex: 1,
    valueFormatter: (value: number | null) => formatTemporalPercent(value),
  },
  { field: 'partial', headerName: 'Parsial', type: 'boolean', flex: 1 },
  { field: 'censored', headerName: 'Tersensor', type: 'boolean', flex: 1 },
]

export function WeekdayHourCoveragePanel({ runId }: WeekdayHourCoveragePanelProps) {
  const viewLabelId = useId()
  const [view, setView] = useState<TemporalView>('resolved_raw_pairs')
  const [dialogRunId, setDialogRunId] = useState<string | null>(null)
  const query = useEdaSectionQuery(runId, 'temporal_coverage')
  const theme = useTheme()
  const section = query.data
  const data = section?.status === 'complete' && section.section === 'temporal_coverage'
    ? buildWeekdayHourMatrix(section.payload, view)
    : undefined
  const values = data?.cells.map((cell) => (
    view === 'resolved_raw_pairs' ? cell.coverage : cell.retention
  )).filter((value): value is number => value !== null) ?? []
  const maximum = Math.max(0, ...values)
  const chartDescription = data === undefined
    ? undefined
    : `${viewLabels[view]} menurut hari dan jam lokal Asia/Jakarta. Setiap sel dihitung dari jumlah pasangan dan slot, bukan rata-rata persentase, selama ${data.localWeeks.toFixed(2)} minggu lokal.`

  return (
    <Paper
      component="section"
      aria-labelledby="weekday-hour-coverage-heading"
      variant="outlined"
      sx={{ minWidth: 0, p: 4 }}
    >
      <Stack spacing={2} sx={{ minWidth: 0 }}>
        <Stack
          direction="row"
          spacing={2}
          useFlexGap
          sx={{ alignItems: 'center', flexWrap: 'wrap', minWidth: 0 }}
        >
          <Typography id="weekday-hour-coverage-heading" variant="h2" sx={{ flexGrow: 1 }}>
            Cakupan hari × jam
          </Typography>
          <FormControl size="small" sx={{ minWidth: tokens.size.sidebar }}>
            <InputLabel id={viewLabelId}>Tampilan</InputLabel>
            <Select
              labelId={viewLabelId}
              label="Tampilan"
              value={view}
              onChange={(event) => setView(event.target.value as TemporalView)}
            >
              {temporalViews.map((value) => (
                <MenuItem key={value} value={value}>{viewLabels[value]}</MenuItem>
              ))}
            </Select>
          </FormControl>
        </Stack>

        {runId === null ? (
          <EmptyState
            title="Pilih run EDA"
            detail="Matriks hari dan jam ditampilkan setelah run EDA dipilih."
          />
        ) : section === undefined ? (
          query.isError ? (
            <ApiErrorPanel error={query.error} onRetry={() => void query.refetch()} />
          ) : (
            <PanelSkeleton label="Memuat matriks hari dan jam" />
          )
        ) : section.status === 'not_eligible' ? (
          <EmptyState title="Matriks temporal belum memenuhi syarat" detail={formatEdaReasonDetail(section.reason_code, section.detail)} />
        ) : section.status === 'failed' ? (
          <ApiErrorPanel
            error={new ApiError('problem', section.detail)}
            onRetry={() => void query.refetch()}
          />
        ) : data === undefined || data.localWeeks === 0 ? (
          <EmptyState
            title="Tidak ada baris per jam"
            detail="Run selesai tanpa paparan per jam untuk matriks 7 × 24."
          />
        ) : (
          <>
            <Box
              sx={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(min(320px,100%),1fr))',
                gap: 2,
                minWidth: 0,
              }}
            >
              <Typography variant="body2" color="text.secondary">
                Nilai sel berasal dari Σ pasangan ÷ Σ slot pada baris per jam yang memiliki hari dan jam lokal sama.
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {data.hasTwoLocalWeeks
                  ? `Ringkasan deskriptif mencakup ${data.localWeeks.toFixed(2)} minggu lokal; ini bukan uji kestabilan.`
                  : `Hanya ${data.localWeeks.toFixed(2)} minggu lokal; kesimpulan pola stabil tidak ditampilkan.`}
              </Typography>
            </Box>
            <Box
              role="img"
              aria-label={`Matriks 7 kali 24 ${viewLabels[view].toLowerCase()}`}
              aria-description={chartDescription}
              sx={{ minWidth: 0 }}
            >
              <TableContainer>
                <Table size="small" aria-hidden="true">
                  <TableHead>
                    <TableRow>
                      <TableCell>Hari</TableCell>
                      {Array.from({ length: 24 }, (_, hour) => (
                        <TableCell key={hour} align="center" sx={{ minWidth: tokens.size.sidebarCompact }}>
                          {String(hour).padStart(2, '0')}
                        </TableCell>
                      ))}
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {weekdayLabels.map((weekdayLabel, weekday) => (
                      <TableRow key={weekdayLabel}>
                        <TableCell component="th" scope="row" sx={{ whiteSpace: 'nowrap' }}>
                          {weekdayLabel}
                        </TableCell>
                        {data.cells.slice(weekday * 24, weekday * 24 + 24).map((cell) => {
                          const value = view === 'resolved_raw_pairs' ? cell.coverage : cell.retention
                          const intensity = value === null || maximum === 0 ? 0 : value / maximum
                          const backgroundColor = alpha(
                            view === 'resolved_raw_pairs'
                              ? theme.palette.primary.main
                              : theme.palette.success.main,
                            intensity,
                          )
                          return (
                            <TableCell
                              key={cell.id}
                              align="center"
                              sx={{
                                ...technicalTextSx,
                                backgroundColor,
                                borderColor: cell.censored ? 'error.main' : 'divider',
                                borderStyle: cell.censored ? 'dashed' : 'solid',
                                p: 0.5,
                              }}
                            >
                              {formatTemporalPercent(value)}
                            </TableCell>
                          )
                        })}
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            </Box>
            <Typography variant="caption" color="text.secondary">
              Garis putus-putus menandai sel yang memuat bin batas tersensor. Nilai 0% adalah observasi eksplisit, bukan data hilang.
            </Typography>
            <Button size="small" onClick={() => setDialogRunId(runId)}>Lihat data</Button>
            <BoundedDataDialog<WeekdayHourCell>
              open={dialogRunId !== null && dialogRunId === runId}
              title={`Matriks hari × jam — ${viewLabels[view]}`}
              rows={data.cells}
              returnedCount={data.cells.length}
              columns={matrixColumns}
              onClose={() => setDialogRunId(null)}
            />
          </>
        )}
      </Stack>
    </Paper>
  )
}
