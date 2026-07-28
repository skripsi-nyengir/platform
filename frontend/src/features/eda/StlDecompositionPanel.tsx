import { Box, Button, Paper, Stack, Typography } from '@mui/material'
import { useTheme } from '@mui/material/styles'
import { LineChart, lineClasses } from '@mui/x-charts/LineChart'
import type { LineChartProps } from '@mui/x-charts/LineChart'
import type { GridColDef } from '@mui/x-data-grid'
import { useState } from 'react'
import { ApiError } from '../../api/errors'
import {
  buildStlData,
  type DiagnosticStatus,
  type StlRow,
} from '../../components/charts/structureEdaOptions'
import { getChartColors } from '../../components/charts/muiChartTheme'
import { BoundedDataDialog } from '../../components/data/BoundedDataDialog'
import { ApiErrorPanel } from '../../components/states/ApiErrorPanel'
import { EmptyState } from '../../components/states/EmptyState'
import { PanelSkeleton } from '../../components/states/PanelSkeleton'
import { tokens } from '../../theme/tokens'
import { useEdaSectionQuery } from './queries'
import { formatEdaReasonDetail } from './reasonLabels'

export interface StlDecompositionPanelProps {
  runId: string | null
}

interface StlDialogRow extends StlRow {
  channel: string
  unit: string
}

const columns: readonly GridColDef<StlDialogRow>[] = [
  { field: 'channel', headerName: 'Kanal', flex: 1 },
  { field: 'timestampIso', headerName: 'Waktu', flex: 2 },
  { field: 'trend', headerName: 'Trend', flex: 1 },
  { field: 'seasonal', headerName: 'Seasonal', flex: 1 },
  { field: 'residual', headerName: 'Residual', flex: 1 },
  { field: 'unit', headerName: 'Unit', flex: 1 },
]

function diagnosticReason(status: DiagnosticStatus): string {
  if (status === 'constant') return 'kanal konstan'
  if (status === 'short') return 'segmen terlalu pendek'
  if (status === 'nonfinite') return 'nilai non-finite'
  return 'perhitungan diagnostik gagal'
}

export function StlDecompositionPanel(props: StlDecompositionPanelProps) {
  return <StlDecompositionPanelContent key={props.runId ?? 'no-run'} {...props} />
}

function StlDecompositionPanelContent({ runId }: StlDecompositionPanelProps) {
  const [dialogRunId, setDialogRunId] = useState<string | null>(null)
  const query = useEdaSectionQuery(runId, 'stationarity')
  const theme = useTheme()
  const colors = getChartColors(theme)
  const section = query.data
  const data = section?.status === 'complete' && section.section === 'stationarity'
    ? buildStlData(section.payload)
    : undefined
  const rows: StlDialogRow[] = data?.channels.flatMap((channel) => (
    channel.rows.map((row) => ({
      ...row,
      id: `${channel.key}-${row.id}`,
      channel: channel.name,
      unit: channel.unit,
    }))
  )) ?? []

  return (
    <Paper
      component="section"
      aria-labelledby="stl-heading"
      variant="outlined"
      sx={{ minWidth: 0, p: 4 }}
    >
      <Stack spacing={2} sx={{ minWidth: 0 }}>
        <Typography id="stl-heading" variant="h2">Dekomposisi STL</Typography>
        {runId === null ? (
          <EmptyState
            title="Pilih run EDA"
            detail="Dekomposisi STL ditampilkan setelah run EDA dipilih."
          />
        ) : query.isError ? (
          <ApiErrorPanel error={query.error} onRetry={() => void query.refetch()} />
        ) : section === undefined ? (
          <PanelSkeleton label="Memuat dekomposisi STL" />
        ) : section.status === 'not_eligible' ? (
          <EmptyState title="STL belum memenuhi syarat" detail={formatEdaReasonDetail(section.reason_code, section.detail)} />
        ) : section.status === 'failed' ? (
          <ApiErrorPanel
            error={new ApiError('problem', section.detail)}
            onRetry={() => void query.refetch()}
          />
        ) : data === undefined ? (
          <EmptyState title="Dekomposisi STL kosong" detail="Run selesai tanpa komponen STL yang dapat ditampilkan." />
        ) : (
          <>
            <Typography variant="body2" color="text.secondary">
              Trend, seasonal, dan residual sejajar memakai periode tetap 24 jam. Ini adalah spesifikasi metode, bukan klaim siklus fisik yang benar.
            </Typography>
            <Box
              role="group"
              aria-label="Dekomposisi STL Suhu dan RH"
              sx={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(min(320px,100%),1fr))',
                gap: 4,
                minWidth: 0,
                '& > *': { minWidth: 0 },
              }}
            >
              {data.channels.map((channel) => {
                const description = `Trend, seasonal, dan residual ${channel.name} dalam ${channel.unit}, sejajar per median jam dengan periode STL tetap 24 jam.`
                const sharedSeries = {
                  curve: 'linear' as const,
                  showMark: false,
                  valueFormatter: (value: number | null) => value === null ? '—' : `${value.toLocaleString('id-ID', { maximumFractionDigits: 4 })} ${channel.unit}`,
                  xAxisId: `${channel.key}-stl-time-axis`,
                  yAxisId: `${channel.key}-stl-value-axis`,
                }
                const series: LineChartProps['series'] = [
                  {
                    ...sharedSeries,
                    id: `${channel.key}-trend`,
                    data: channel.rows.map((row) => row.trend),
                    label: `Trend ${channel.name}`,
                    color: channel.key === 'suhu' ? colors.temperature : colors.humidity,
                  },
                  {
                    ...sharedSeries,
                    id: `${channel.key}-seasonal`,
                    data: channel.rows.map((row) => row.seasonal),
                    label: `Seasonal ${channel.name}`,
                    color: colors.anomalyScore,
                  },
                  {
                    ...sharedSeries,
                    id: `${channel.key}-residual`,
                    data: channel.rows.map((row) => row.residual),
                    label: `Residual ${channel.name}`,
                    color: theme.palette.text.secondary,
                  },
                ]
                return (
                  <Box component="article" key={channel.key} sx={{ backgroundColor: theme.palette.background.default, minWidth: 0, p: 4 }}>
                    <Stack spacing={1} sx={{ minWidth: 0 }}>
                      <Typography variant="subtitle2">{channel.name} ({channel.unit})</Typography>
                      {channel.status === 'ok' && channel.rows.length > 0 ? (
                        <Box
                          role="img"
                          aria-label={`Dekomposisi STL ${channel.name}`}
                          aria-description={description}
                          sx={{ minWidth: 0 }}
                        >
                          <LineChart
                            id={`stl-${channel.key}`}
                            title={`Dekomposisi STL ${channel.name}`}
                            desc={description}
                            disableKeyboardNavigation
                            height={tokens.size.control * 7}
                            skipAnimation
                            sx={{
                              [`& .${lineClasses.line}[data-series="${channel.key}-seasonal"]`]: {
                                strokeDasharray: `${tokens.spacing.unit} ${tokens.spacing.unit}`,
                              },
                              [`& .${lineClasses.line}[data-series="${channel.key}-residual"]`]: {
                                strokeDasharray: `${tokens.spacing.unit * 2} ${tokens.spacing.unit}`,
                              },
                            }}
                            xAxis={[{
                              id: `${channel.key}-stl-time-axis`,
                              data: channel.rows.map((row) => row.timestamp),
                              label: 'Waktu Asia/Jakarta',
                              scaleType: 'time',
                            }]}
                            yAxis={[{
                              id: `${channel.key}-stl-value-axis`,
                              label: `${channel.name} (${channel.unit})`,
                            }]}
                            series={series}
                          />
                        </Box>
                      ) : (
                        <EmptyState
                          title={`STL ${channel.name} tidak memenuhi syarat: ${diagnosticReason(channel.status)}.`}
                          detail="Komponen trend, seasonal, dan residual tidak digambar sebagai garis kosong."
                        />
                      )}
                    </Stack>
                  </Box>
                )
              })}
            </Box>
            {rows.length === 0 ? null : (
              <>
                <Button
                  aria-haspopup="dialog"
                  aria-label="Lihat data dekomposisi STL"
                  size="small"
                  onClick={() => setDialogRunId(runId)}
                >
                  Lihat data
                </Button>
                <BoundedDataDialog<StlDialogRow>
                  open={dialogRunId !== null && dialogRunId === runId}
                  title="Komponen STL sejajar"
                  rows={rows}
                  returnedCount={rows.length}
                  columns={columns}
                  onClose={() => setDialogRunId(null)}
                />
              </>
            )}
          </>
        )}
      </Stack>
    </Paper>
  )
}
