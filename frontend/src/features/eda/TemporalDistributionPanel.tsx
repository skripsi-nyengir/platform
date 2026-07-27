import {
  Box,
  Button,
  Chip,
  FormControl,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  Stack,
  Typography,
} from '@mui/material'
import { useTheme } from '@mui/material/styles'
import { LineChart, lineClasses } from '@mui/x-charts/LineChart'
import type { GridColDef } from '@mui/x-data-grid'
import { useId, useState } from 'react'
import { ApiError } from '../../api/errors'
import {
  buildTemporalDistributionData,
  temporalResolutions,
  temporalViews,
  type DriftConclusion,
  type DriftDirection,
  type TemporalDistributionRow,
  type TemporalResolution,
  type TemporalView,
} from '../../components/charts/temporalEdaOptions'
import { getChartColors } from '../../components/charts/muiChartTheme'
import { BoundedDataDialog } from '../../components/data/BoundedDataDialog'
import { ApiErrorPanel } from '../../components/states/ApiErrorPanel'
import { EmptyState } from '../../components/states/EmptyState'
import { PanelSkeleton } from '../../components/states/PanelSkeleton'
import { tokens } from '../../theme/tokens'
import { useEdaSectionQuery } from './queries'
import { formatEdaReasonDetail } from './reasonLabels'

export interface TemporalDistributionPanelProps {
  runId: string | null
}

const resolutionLabels: Record<TemporalResolution, string> = {
  hourly: 'Per jam',
  daily: 'Harian',
  monthly: 'Bulanan',
}

const viewLabels: Record<TemporalView, string> = {
  resolved_raw_pairs: 'Pasangan exact mentah',
  rule_screened_pairs: 'Setelah screening aturan',
}

const technicalTextSx = {
  fontFamily: tokens.font.data,
  fontVariantNumeric: 'tabular-nums',
  overflowWrap: 'anywhere',
} as const

const distributionColumns: readonly GridColDef<TemporalDistributionRow>[] = [
  { field: 'start', headerName: 'Mulai (Asia/Jakarta)', flex: 2 },
  { field: 'end', headerName: 'Selesai (Asia/Jakarta)', flex: 2 },
  { field: 'count', headerName: 'Jumlah pasangan', flex: 1 },
  { field: 'censored', headerName: 'Tersensor', type: 'boolean', flex: 1 },
  { field: 'suhuMedian', headerName: 'Median Suhu (°C)', flex: 1 },
  { field: 'suhuQ1', headerName: 'Q1 Suhu (°C)', flex: 1 },
  { field: 'suhuQ3', headerName: 'Q3 Suhu (°C)', flex: 1 },
  { field: 'suhuMad', headerName: 'MAD Suhu (°C)', flex: 1 },
  { field: 'rhMedian', headerName: 'Median RH (%)', flex: 1 },
  { field: 'rhQ1', headerName: 'Q1 RH (%)', flex: 1 },
  { field: 'rhQ3', headerName: 'Q3 RH (%)', flex: 1 },
  { field: 'rhMad', headerName: 'MAD RH (%)', flex: 1 },
]

function robustDirection(
  conclusion: DriftConclusion | undefined,
): Exclude<DriftDirection, 'insufficient_data'> | undefined {
  if (conclusion?.status !== 'robust') return undefined
  const directions = Object.values(conclusion.directions)
  const direction = directions[0]
  return direction !== undefined && direction !== 'insufficient_data' ? direction : undefined
}

function directionLabel(direction: Exclude<DriftDirection, 'insufficient_data'>): string {
  if (direction === 'increase') return 'meningkat'
  if (direction === 'decrease') return 'menurun'
  return 'tetap'
}

export function TemporalDistributionPanel({ runId }: TemporalDistributionPanelProps) {
  const resolutionLabelId = useId()
  const viewLabelId = useId()
  const [resolution, setResolution] = useState<TemporalResolution>('monthly')
  const [view, setView] = useState<TemporalView>('rule_screened_pairs')
  const [dialogRunId, setDialogRunId] = useState<string | null>(null)
  const query = useEdaSectionQuery(runId, 'temporal_distribution')
  const theme = useTheme()
  const chartColors = getChartColors(theme)
  const section = query.data
  const data = section?.status === 'complete' && section.section === 'temporal_distribution'
    ? buildTemporalDistributionData(section.payload, view, resolution)
    : undefined
  const totalCount = data?.rows.reduce((total, row) => total + row.count, 0) ?? 0

  return (
    <Paper
      component="section"
      aria-labelledby="temporal-distribution-heading"
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
          <Typography id="temporal-distribution-heading" variant="h2" sx={{ flexGrow: 1 }}>
            Distribusi temporal Suhu dan RH
          </Typography>
          <FormControl size="small" sx={{ minWidth: tokens.size.sidebarCompact * 2 }}>
            <InputLabel id={resolutionLabelId}>Resolusi</InputLabel>
            <Select
              labelId={resolutionLabelId}
              label="Resolusi"
              value={resolution}
              onChange={(event) => setResolution(event.target.value as TemporalResolution)}
            >
              {temporalResolutions.map((value) => (
                <MenuItem key={value} value={value}>{resolutionLabels[value]}</MenuItem>
              ))}
            </Select>
          </FormControl>
          <FormControl size="small" sx={{ minWidth: tokens.size.sidebar }}>
            <InputLabel id={viewLabelId}>Populasi</InputLabel>
            <Select
              labelId={viewLabelId}
              label="Populasi"
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
            detail="Distribusi temporal ditampilkan setelah run EDA dipilih."
          />
        ) : section === undefined ? (
          query.isError ? (
            <ApiErrorPanel error={query.error} onRetry={() => void query.refetch()} />
          ) : (
            <PanelSkeleton label="Memuat distribusi temporal" />
          )
        ) : section.status === 'not_eligible' ? (
          <EmptyState title="Distribusi temporal belum memenuhi syarat" detail={formatEdaReasonDetail(section.reason_code, section.detail)} />
        ) : section.status === 'failed' ? (
          <ApiErrorPanel
            error={new ApiError('problem', section.detail)}
            onRetry={() => void query.refetch()}
          />
        ) : data === undefined || data.rows.length === 0 || !data.hasData ? (
          <EmptyState
            title="Tidak ada statistik distribusi temporal"
            detail="Run selesai tanpa pasangan finite pada resolusi dan populasi ini."
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
                Populasi {viewLabels[view].toLowerCase()}; <Box component="span" sx={technicalTextSx}>{totalCount.toLocaleString('id-ID')}</Box> pasangan pada seluruh bin.
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Median, Q1, dan Q3 digambar sebagai tiga garis. Jumlah dan MAD per bin tersedia melalui Lihat data.
              </Typography>
            </Box>
            {resolution === 'monthly' ? (
              <Stack direction="row" spacing={1} useFlexGap sx={{ flexWrap: 'wrap' }}>
                {data.channels.map((channel) => {
                  const direction = robustDirection(data.driftConclusions[channel.key])
                  return direction === undefined ? null : (
                    <Chip
                      key={channel.key}
                      color="info"
                      size="small"
                      label={`Arah median deskriptif ${channel.name}: ${directionLabel(direction)}`}
                    />
                  )
                })}
                <Typography variant="caption" color="text.secondary">
                  Ringkasan arah hanya ditampilkan saat konsisten pada seluruh ambang sumber; bukan tren terestimasi, prakiraan, penyebab, atau anomali.
                </Typography>
              </Stack>
            ) : null}
            <Box
              role="group"
              aria-label="Grafik distribusi temporal Suhu dan RH"
              sx={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(min(320px,100%),1fr))',
                gap: 4,
                minWidth: 0,
              }}
            >
              {data.channels.map((channel) => {
                const color = channel.key === 'suhu' ? chartColors.temperature : chartColors.humidity
                const censoredCount = channel.points.filter((point) => point.censored).length
                const emptyCount = channel.points.filter((point) => !point.censored && point.count === 0).length
                const description = `${channel.name} ${resolutionLabels[resolution].toLowerCase()} dalam ${channel.unit} untuk ${viewLabels[view].toLowerCase()}. Median, Q1, dan Q3 berhenti pada bin kosong atau tersensor.`
                return (
                  <Paper
                    component="article"
                    key={channel.key}
                    variant="outlined"
                    sx={{ minWidth: 0, p: 4 }}
                  >
                    <Stack spacing={1} sx={{ minWidth: 0 }}>
                      <Typography variant="h3">{channel.name} ({channel.unit})</Typography>
                      {censoredCount === 0 && emptyCount === 0 ? null : (
                        <Typography variant="caption" color="text.secondary">
                          {censoredCount} bin tersensor dan {emptyCount} bin kosong memutus garis median, Q1, dan Q3.
                        </Typography>
                      )}
                      <Box
                        role="img"
                        aria-label={`Distribusi temporal ${channel.name} dalam ${channel.unit}`}
                        aria-description={description}
                        sx={{ minWidth: 0 }}
                      >
                        <LineChart
                          id={`temporal-distribution-${channel.key}`}
                          title={`Distribusi temporal ${channel.name}`}
                          desc={description}
                          disableKeyboardNavigation
                          height={tokens.size.control * 7}
                          skipAnimation
                          sx={{
                            [`& .${lineClasses.line}[data-series="${channel.key}-q1"]`]: {
                              strokeDasharray: `${tokens.spacing.unit} ${tokens.spacing.unit}`,
                            },
                            [`& .${lineClasses.line}[data-series="${channel.key}-q3"]`]: {
                              strokeDasharray: `${tokens.spacing.unit} ${tokens.spacing.unit}`,
                            },
                          }}
                          xAxis={[{
                            id: `${channel.key}-distribution-x`,
                            data: channel.points.map((point) => point.x),
                            label: 'Waktu Asia/Jakarta',
                            scaleType: 'time',
                          }]}
                          yAxis={[{
                            id: `${channel.key}-distribution-y`,
                            label: `${channel.name} (${channel.unit})`,
                          }]}
                          series={[
                            {
                              id: `${channel.key}-median`,
                              data: channel.points.map((point) => point.median),
                              label: `Median ${channel.name} (${channel.unit})`,
                              color,
                              connectNulls: false,
                              curve: 'linear',
                              showMark: false,
                              valueFormatter: (value: number | null) => value === null ? '—' : `${value} ${channel.unit}`,
                              xAxisId: `${channel.key}-distribution-x`,
                              yAxisId: `${channel.key}-distribution-y`,
                            },
                            {
                              id: `${channel.key}-q1`,
                              data: channel.points.map((point) => point.q1),
                              label: `Q1 ${channel.name} (${channel.unit})`,
                              color: channel.key === 'suhu'
                                ? theme.palette.primary.light
                                : theme.palette.success.light,
                              connectNulls: false,
                              curve: 'linear',
                              showMark: false,
                              valueFormatter: (value: number | null) => value === null ? '—' : `${value} ${channel.unit}`,
                              xAxisId: `${channel.key}-distribution-x`,
                              yAxisId: `${channel.key}-distribution-y`,
                            },
                            {
                              id: `${channel.key}-q3`,
                              data: channel.points.map((point) => point.q3),
                              label: `Q3 ${channel.name} (${channel.unit})`,
                              color: channel.key === 'suhu'
                                ? theme.palette.primary.dark
                                : theme.palette.success.dark,
                              connectNulls: false,
                              curve: 'linear',
                              showMark: false,
                              valueFormatter: (value: number | null) => value === null ? '—' : `${value} ${channel.unit}`,
                              xAxisId: `${channel.key}-distribution-x`,
                              yAxisId: `${channel.key}-distribution-y`,
                            },
                          ]}
                        />
                      </Box>
                    </Stack>
                  </Paper>
                )
              })}
            </Box>
            <Button size="small" onClick={() => setDialogRunId(runId)}>Lihat data</Button>
            <BoundedDataDialog<TemporalDistributionRow>
              open={dialogRunId !== null && dialogRunId === runId}
              title={`Distribusi temporal ${resolutionLabels[resolution]} — ${viewLabels[view]}`}
              rows={data.rows}
              returnedCount={data.rows.length}
              columns={distributionColumns}
              onClose={() => setDialogRunId(null)}
            />
          </>
        )}
      </Stack>
    </Paper>
  )
}
