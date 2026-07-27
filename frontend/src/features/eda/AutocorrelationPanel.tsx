import { Box, Button, Paper, Stack, Typography } from '@mui/material'
import { useTheme } from '@mui/material/styles'
import { LineChart } from '@mui/x-charts/LineChart'
import type { GridColDef } from '@mui/x-data-grid'
import { useState } from 'react'
import { ApiError } from '../../api/errors'
import {
  AUTOCORRELATION_DOMAIN,
  buildAutocorrelationData,
  type AutocorrelationChannelData,
  type DiagnosticStatus,
} from '../../components/charts/structureEdaOptions'
import { getChartColors } from '../../components/charts/muiChartTheme'
import { BoundedDataDialog } from '../../components/data/BoundedDataDialog'
import { ApiErrorPanel } from '../../components/states/ApiErrorPanel'
import { EmptyState } from '../../components/states/EmptyState'
import { PanelSkeleton } from '../../components/states/PanelSkeleton'
import { tokens } from '../../theme/tokens'
import { useEdaSectionQuery } from './queries'
import { formatEdaReasonDetail } from './reasonLabels'

export interface AutocorrelationPanelProps {
  runId: string | null
}

interface AutocorrelationRow {
  id: string
  channel: string
  lagHours: number
  autocorrelation: number | null
  partialAutocorrelation: number | null
}

const columns: readonly GridColDef<AutocorrelationRow>[] = [
  { field: 'channel', headerName: 'Kanal', flex: 1 },
  { field: 'lagHours', headerName: 'Lag (jam)', flex: 1 },
  { field: 'autocorrelation', headerName: 'ACF', flex: 1 },
  { field: 'partialAutocorrelation', headerName: 'PACF', flex: 1 },
]

function diagnosticReason(status: DiagnosticStatus): string {
  if (status === 'constant') return 'kanal konstan'
  if (status === 'short') return 'segmen terlalu pendek'
  if (status === 'nonfinite') return 'nilai non-finite'
  return 'perhitungan diagnostik gagal'
}

function channelUnavailable(channel: AutocorrelationChannelData): string | null {
  if (channel.autocorrelationStatus !== 'ok') {
    return diagnosticReason(channel.autocorrelationStatus)
  }
  if (channel.partialAutocorrelationStatus !== 'ok') {
    return diagnosticReason(channel.partialAutocorrelationStatus)
  }
  return null
}

export function AutocorrelationPanel(props: AutocorrelationPanelProps) {
  return <AutocorrelationPanelContent key={props.runId ?? 'no-run'} {...props} />
}

function AutocorrelationPanelContent({ runId }: AutocorrelationPanelProps) {
  const [dialogRunId, setDialogRunId] = useState<string | null>(null)
  const query = useEdaSectionQuery(runId, 'stationarity')
  const theme = useTheme()
  const colors = getChartColors(theme)
  const section = query.data
  const data = section?.status === 'complete' && section.section === 'stationarity'
    ? buildAutocorrelationData(section.payload)
    : undefined
  const rows: AutocorrelationRow[] = data?.channels.flatMap((channel) => (
    channel.lags.map((lag, index) => ({
      id: `${channel.key}-${lag}`,
      channel: channel.name,
      lagHours: lag,
      autocorrelation: channel.autocorrelation[index] ?? null,
      partialAutocorrelation: channel.partialAutocorrelation[index] ?? null,
    }))
  )) ?? []

  return (
    <Paper
      component="section"
      aria-labelledby="autocorrelation-heading"
      variant="outlined"
      sx={{ minWidth: 0, p: 4 }}
    >
      <Stack spacing={2} sx={{ minWidth: 0 }}>
        <Typography id="autocorrelation-heading" variant="h2">
          Autokorelasi ACF dan PACF
        </Typography>
        {runId === null ? (
          <EmptyState
            title="Pilih run EDA"
            detail="ACF dan PACF ditampilkan setelah run EDA dipilih."
          />
        ) : query.isError ? (
          <ApiErrorPanel error={query.error} onRetry={() => void query.refetch()} />
        ) : section === undefined ? (
          <PanelSkeleton label="Memuat ACF dan PACF" />
        ) : section.status === 'not_eligible' ? (
          <EmptyState title="ACF/PACF belum memenuhi syarat" detail={formatEdaReasonDetail(section.reason_code, section.detail)} />
        ) : section.status === 'failed' ? (
          <ApiErrorPanel
            error={new ApiError('problem', section.detail)}
            onRetry={() => void query.refetch()}
          />
        ) : data === undefined ? (
          <EmptyState title="ACF/PACF kosong" detail="Run selesai tanpa urutan lag yang dapat ditampilkan." />
        ) : (
          <>
            <Typography variant="body2" color="text.secondary">
              Koefisien pada lag 0–72 jam memakai domain tetap −1 sampai 1, tanpa pita kepercayaan dan tanpa rekomendasi orde model.
            </Typography>
            <Box
              role="group"
              aria-label="Grafik ACF dan PACF Suhu dan RH"
              sx={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(min(320px,100%),1fr))',
                gap: 4,
                minWidth: 0,
                '& > *': { minWidth: 0 },
              }}
            >
              {data.channels.map((channel) => {
                const unavailable = channelUnavailable(channel)
                const description = `ACF dan PACF ${channel.name} untuk lag 0 sampai 72 jam pada median per jam; domain koefisien tetap dari minus satu sampai satu.`
                return (
                  <Paper component="article" key={channel.key} variant="outlined" sx={{ minWidth: 0, p: 4 }}>
                    <Stack spacing={1} sx={{ minWidth: 0 }}>
                      <Typography variant="h3">{channel.name}</Typography>
                      {unavailable === null && channel.lags.length > 0 ? (
                        <Box
                          role="img"
                          aria-label={`ACF dan PACF ${channel.name}`}
                          aria-description={description}
                          sx={{ minWidth: 0 }}
                        >
                          <LineChart
                            id={`autocorrelation-${channel.key}`}
                            title={`ACF dan PACF ${channel.name}`}
                            desc={description}
                            disableKeyboardNavigation
                            height={tokens.size.control * 7}
                            skipAnimation
                            xAxis={[{
                              id: `${channel.key}-lag-axis`,
                              data: channel.lags,
                              label: 'Lag (jam)',
                              min: 0,
                              max: 72,
                              scaleType: 'linear',
                            }]}
                            yAxis={[{
                              id: `${channel.key}-coefficient-axis`,
                              label: 'Koefisien',
                              min: AUTOCORRELATION_DOMAIN[0],
                              max: AUTOCORRELATION_DOMAIN[1],
                            }]}
                            series={[
                              {
                                id: `${channel.key}-acf`,
                                data: channel.autocorrelation,
                                label: 'ACF',
                                color: channel.key === 'suhu' ? colors.temperature : colors.humidity,
                                curve: 'linear',
                                showMark: false,
                                valueFormatter: (value: number | null) => value === null ? '—' : value.toFixed(4),
                                xAxisId: `${channel.key}-lag-axis`,
                                yAxisId: `${channel.key}-coefficient-axis`,
                              },
                              {
                                id: `${channel.key}-pacf`,
                                data: channel.partialAutocorrelation,
                                label: 'PACF',
                                color: colors.anomalyScore,
                                curve: 'linear',
                                showMark: false,
                                valueFormatter: (value: number | null) => value === null ? '—' : value.toFixed(4),
                                xAxisId: `${channel.key}-lag-axis`,
                                yAxisId: `${channel.key}-coefficient-axis`,
                              },
                            ]}
                          />
                        </Box>
                      ) : (
                        <EmptyState
                          title={`ACF/PACF ${channel.name} tidak memenuhi syarat: ${unavailable ?? 'data kosong'}.`}
                          detail="Urutan koefisien tidak digambar sebagai nol atau garis kosong."
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
                  aria-label="Lihat data autokorelasi ACF dan PACF"
                  size="small"
                  onClick={() => setDialogRunId(runId)}
                >
                  Lihat data
                </Button>
                <BoundedDataDialog<AutocorrelationRow>
                  open={dialogRunId !== null && dialogRunId === runId}
                  title="Nilai ACF dan PACF per lag"
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
