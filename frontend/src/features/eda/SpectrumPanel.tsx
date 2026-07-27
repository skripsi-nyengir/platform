import { Box, Button, Paper, Stack, Typography } from '@mui/material'
import { useTheme } from '@mui/material/styles'
import { LineChart } from '@mui/x-charts/LineChart'
import type { GridColDef } from '@mui/x-data-grid'
import { useState } from 'react'
import { ApiError } from '../../api/errors'
import {
  buildSpectrumData,
  type DiagnosticStatus,
  type SpectrumRow,
} from '../../components/charts/structureEdaOptions'
import { getChartColors } from '../../components/charts/muiChartTheme'
import { BoundedDataDialog } from '../../components/data/BoundedDataDialog'
import { ApiErrorPanel } from '../../components/states/ApiErrorPanel'
import { EmptyState } from '../../components/states/EmptyState'
import { PanelSkeleton } from '../../components/states/PanelSkeleton'
import { tokens } from '../../theme/tokens'
import { useEdaSectionQuery } from './queries'
import { formatEdaReasonDetail } from './reasonLabels'

export interface SpectrumPanelProps {
  runId: string | null
}

interface SpectrumDialogRow extends SpectrumRow {
  channel: string
}

const columns: readonly GridColDef<SpectrumDialogRow>[] = [
  { field: 'channel', headerName: 'Kanal', flex: 1 },
  { field: 'frequency', headerName: 'Frekuensi (siklus/jam)', flex: 1 },
  { field: 'power', headerName: 'Daya spektral', flex: 1 },
  { field: 'periodHours', headerName: 'Periode turunan (jam)', flex: 1 },
]

function diagnosticReason(status: DiagnosticStatus): string {
  if (status === 'constant') return 'kanal konstan'
  if (status === 'short') return 'segmen terlalu pendek'
  if (status === 'nonfinite') return 'nilai non-finite'
  return 'perhitungan diagnostik gagal'
}

function formatFrequency(frequency: number, includePeriod: boolean): string {
  const formatted = `${frequency.toLocaleString('id-ID', { maximumFractionDigits: 6 })} siklus/jam`
  if (!includePeriod || !Number.isFinite(frequency) || frequency === 0) return formatted
  const period = 1 / frequency
  return Number.isFinite(period)
    ? `${formatted} · periode ${period.toLocaleString('id-ID', { maximumFractionDigits: 2 })} jam`
    : formatted
}

export function SpectrumPanel(props: SpectrumPanelProps) {
  return <SpectrumPanelContent key={props.runId ?? 'no-run'} {...props} />
}

function SpectrumPanelContent({ runId }: SpectrumPanelProps) {
  const [dialogRunId, setDialogRunId] = useState<string | null>(null)
  const query = useEdaSectionQuery(runId, 'stationarity')
  const theme = useTheme()
  const colors = getChartColors(theme)
  const section = query.data
  const data = section?.status === 'complete' && section.section === 'stationarity'
    ? buildSpectrumData(section.payload)
    : undefined
  const rows: SpectrumDialogRow[] = data?.channels.flatMap((channel) => (
    channel.rows.map((row) => ({ ...row, id: `${channel.key}-${row.id}`, channel: channel.name }))
  )) ?? []

  return (
    <Paper
      component="section"
      aria-labelledby="spectrum-heading"
      variant="outlined"
      sx={{ minWidth: 0, p: 4 }}
    >
      <Stack spacing={2} sx={{ minWidth: 0 }}>
        <Typography id="spectrum-heading" variant="h2">Spektrum frekuensi</Typography>
        {runId === null ? (
          <EmptyState
            title="Pilih run EDA"
            detail="Spektrum frekuensi ditampilkan setelah run EDA dipilih."
          />
        ) : query.isError ? (
          <ApiErrorPanel error={query.error} onRetry={() => void query.refetch()} />
        ) : section === undefined ? (
          <PanelSkeleton label="Memuat spektrum frekuensi" />
        ) : section.status === 'not_eligible' ? (
          <EmptyState title="Spektrum belum memenuhi syarat" detail={formatEdaReasonDetail(section.reason_code, section.detail)} />
        ) : section.status === 'failed' ? (
          <ApiErrorPanel
            error={new ApiError('problem', section.detail)}
            onRetry={() => void query.refetch()}
          />
        ) : data === undefined ? (
          <EmptyState title="Spektrum kosong" detail="Run selesai tanpa frekuensi dan daya yang dapat ditampilkan." />
        ) : (
          <>
            <Typography variant="body2" color="text.secondary">
              Puncak spektrum dapat mencerminkan tren, jendela analisis, atau agregasi; bukan bukti siklus fisik maupun prediksi.
            </Typography>
            <Box
              role="group"
              aria-label="Spektrum frekuensi Suhu dan RH"
              sx={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(min(320px,100%),1fr))',
                gap: 4,
                minWidth: 0,
                '& > *': { minWidth: 0 },
              }}
            >
              {data.channels.map((channel) => {
                const description = `Spektrum ${channel.name} pada median per jam. Tooltip mengubah frekuensi menjadi periode hanya untuk nilai finite dan bukan nol.`
                return (
                  <Paper component="article" key={channel.key} variant="outlined" sx={{ minWidth: 0, p: 4 }}>
                    <Stack spacing={1} sx={{ minWidth: 0 }}>
                      <Typography variant="h3">{channel.name}</Typography>
                      {channel.status === 'ok' && channel.rows.length > 0 ? (
                        <Box
                          role="img"
                          aria-label={`Spektrum frekuensi ${channel.name}`}
                          aria-description={description}
                          sx={{ minWidth: 0 }}
                        >
                          <LineChart
                            id={`spectrum-${channel.key}`}
                            title={`Spektrum ${channel.name}`}
                            desc={description}
                            disableKeyboardNavigation
                            height={tokens.size.control * 7}
                            skipAnimation
                            xAxis={[{
                              id: `${channel.key}-frequency-axis`,
                              data: channel.rows.map((row) => row.frequency),
                              label: 'Frekuensi (siklus/jam)',
                              scaleType: 'linear',
                              valueFormatter: (frequency, context) => formatFrequency(
                                frequency,
                                context.location === 'tooltip',
                              ),
                            }]}
                            yAxis={[{
                              id: `${channel.key}-power-axis`,
                              label: 'Daya spektral',
                              min: 0,
                            }]}
                            series={[{
                              id: `${channel.key}-power`,
                              data: channel.rows.map((row) => row.power),
                              label: `Daya ${channel.name}`,
                              color: channel.key === 'suhu' ? colors.temperature : colors.humidity,
                              curve: 'linear',
                              showMark: false,
                              valueFormatter: (value: number | null) => value === null ? '—' : value.toLocaleString('id-ID', { maximumFractionDigits: 4 }),
                              xAxisId: `${channel.key}-frequency-axis`,
                              yAxisId: `${channel.key}-power-axis`,
                            }]}
                          />
                        </Box>
                      ) : (
                        <EmptyState
                          title={`Spektrum ${channel.name} tidak memenuhi syarat: ${diagnosticReason(channel.status)}.`}
                          detail="Kurva daya tidak digambar sebagai nol atau garis kosong."
                        />
                      )}
                    </Stack>
                  </Paper>
                )
              })}
            </Box>
            {rows.length === 0 ? null : (
              <>
                <Button
                  aria-haspopup="dialog"
                  aria-label="Lihat data spektrum frekuensi"
                  size="small"
                  onClick={() => setDialogRunId(runId)}
                >
                  Lihat data
                </Button>
                <BoundedDataDialog<SpectrumDialogRow>
                  open={dialogRunId !== null && dialogRunId === runId}
                  title="Frekuensi, daya, dan periode turunan"
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
