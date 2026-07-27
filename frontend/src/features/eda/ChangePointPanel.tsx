import { Box, Button, Chip, Paper, Stack, Typography } from '@mui/material'
import { useTheme } from '@mui/material/styles'
import { LineChart, lineClasses } from '@mui/x-charts/LineChart'
import type { GridColDef } from '@mui/x-data-grid'
import { useState } from 'react'
import { ApiError } from '../../api/errors'
import {
  buildChangePointData,
  type ChangePointAuditRow,
} from '../../components/charts/structureEdaOptions'
import { getChartColors } from '../../components/charts/muiChartTheme'
import { BoundedDataDialog } from '../../components/data/BoundedDataDialog'
import { ApiErrorPanel } from '../../components/states/ApiErrorPanel'
import { EmptyState } from '../../components/states/EmptyState'
import { PanelSkeleton } from '../../components/states/PanelSkeleton'
import { tokens } from '../../theme/tokens'
import { useEdaSectionQuery } from './queries'
import { formatEdaReasonDetail } from './reasonLabels'

export interface ChangePointPanelProps {
  runId: string | null
}

const columns: readonly GridColDef<ChangePointAuditRow>[] = [
  { field: 'blockRange', headerName: 'Rentang blok harian', flex: 2 },
  { field: 'blockStatus', headerName: 'Status blok', flex: 1 },
  { field: 'pairCount', headerName: 'Median harian', flex: 1 },
  { field: 'candidateDate', headerName: 'Tanggal kandidat', flex: 1 },
  { field: 'stabilityCount', headerName: 'Jumlah penalti stabil', flex: 1 },
  { field: 'penaltyFactors', headerName: 'Faktor penalti mentah', flex: 1 },
  { field: 'observedDays', headerName: 'Hari teramati', flex: 2 },
  { field: 'scaleMedianSuhu', headerName: 'Skala median Suhu (°C)', flex: 1 },
  { field: 'scaleMedianRh', headerName: 'Skala median RH (%)', flex: 1 },
  { field: 'scaleMadSuhu', headerName: 'Skala MAD Suhu (°C)', flex: 1 },
  { field: 'scaleMadRh', headerName: 'Skala MAD RH (%)', flex: 1 },
  { field: 'constantChannels', headerName: 'Kanal konstan', flex: 1 },
  { field: 'confirmations', headerName: 'Konfirmasi minimum-segmen', flex: 3 },
]

const technicalTextSx = {
  fontFamily: tokens.font.data,
  fontVariantNumeric: 'tabular-nums',
  overflowWrap: 'anywhere',
} as const

export function ChangePointPanel(props: ChangePointPanelProps) {
  return <ChangePointPanelContent key={props.runId ?? 'no-run'} {...props} />
}

function ChangePointPanelContent({ runId }: ChangePointPanelProps) {
  const [dialogRunId, setDialogRunId] = useState<string | null>(null)
  const query = useEdaSectionQuery(runId, 'change_points')
  const theme = useTheme()
  const colors = getChartColors(theme)
  const section = query.data
  const data = section?.status === 'complete' && section.section === 'change_points'
    ? buildChangePointData(section.payload)
    : undefined

  return (
    <Paper
      component="section"
      aria-labelledby="change-point-heading"
      variant="outlined"
      sx={{ minWidth: 0, p: 4 }}
    >
      <Stack spacing={2} sx={{ minWidth: 0 }}>
        <Typography id="change-point-heading" variant="h2">Kandidat perubahan rezim</Typography>
        {runId === null ? (
          <EmptyState
            title="Pilih run EDA"
            detail="Kandidat perubahan rezim ditampilkan setelah run EDA dipilih."
          />
        ) : query.isError ? (
          <ApiErrorPanel error={query.error} onRetry={() => void query.refetch()} />
        ) : section === undefined ? (
          <PanelSkeleton label="Memuat kandidat perubahan rezim" />
        ) : section.status === 'not_eligible' ? (
          <EmptyState title="Kandidat perubahan belum memenuhi syarat" detail={formatEdaReasonDetail(section.reason_code, section.detail)} />
        ) : section.status === 'failed' ? (
          <ApiErrorPanel
            error={new ApiError('problem', section.detail)}
            onRetry={() => void query.refetch()}
          />
        ) : data === undefined ? (
          <EmptyState title="Kandidat perubahan kosong" detail="Run selesai tanpa blok harian yang dapat diaudit." />
        ) : (
          <>
            <Typography variant="body2" color="text.secondary">
              Batas yang ditampilkan adalah kandidat agregat harian, bukan timestamp kejadian, label anomali, atau bukti sebab-akibat.
            </Typography>
            <Box
              sx={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(min(320px,100%),1fr))',
                gap: 2,
                minWidth: 0,
                '& > *': { minWidth: 0 },
              }}
            >
              {data.blockSummaries.map((block) => (
                <Paper component="article" key={block.id} variant="outlined" sx={{ minWidth: 0, p: 2 }}>
                  <Stack spacing={0.5}>
                    <Typography variant="h3">Blok {block.startDate} – {block.endDate}</Typography>
                    <Typography variant="body2" color="text.secondary" sx={technicalTextSx}>
                      {block.pairCount.toLocaleString('id-ID')} median harian
                    </Typography>
                    <Typography variant="body2">
                      Blok harian berstatus {block.status}; {block.stableChangeCount} kandidat stabil; {block.confirmationCount} aturan konfirmasi.
                    </Typography>
                  </Stack>
                </Paper>
              ))}
            </Box>
            {data.confirmationSummary.length === 0 ? (
              <Typography variant="caption" color="text.secondary">
                Metadata konfirmasi minimum-segmen tidak tersedia; detail blok tetap ada di Lihat data.
              </Typography>
            ) : (
              <Stack direction="row" spacing={1} useFlexGap sx={{ flexWrap: 'wrap' }}>
                {data.confirmationSummary.map((confirmation) => (
                   <Chip
                     key={confirmation.id}
                     size="small"
                     color={confirmation.status === 'ok' ? 'success' : 'default'}
                     label={`Konfirmasi minimum segmen ${confirmation.minimumSegmentDays} hari: ${confirmation.status}, ${confirmation.matchedStableChanges}/${confirmation.requestedBreakpoints} cocok`}
                     sx={{
                       height: 'auto',
                       maxWidth: '100%',
                       '& .MuiChip-label': {
                         overflowWrap: 'anywhere',
                         py: 0.5,
                         whiteSpace: 'normal',
                       },
                     }}
                   />
                ))}
              </Stack>
            )}
            {data.candidates.length === 0 ? (
              <EmptyState
                title="Tidak ada kandidat perubahan stabil"
                detail="Tidak ada batas yang stabil pada sedikitnya tiga penalti; chart titik dan efek tidak digambar."
              />
            ) : (
              <>
                <Box
                  role="img"
                  aria-label="Tanggal kandidat perubahan stabil"
                  aria-description="Penanda titik menunjukkan tanggal batas kandidat pada agregat harian. Garis penghubung disembunyikan karena setiap batas adalah kandidat diskret."
                  sx={{ minWidth: 0 }}
                >
                  <LineChart
                    id="change-point-dates"
                    title="Tanggal kandidat perubahan stabil"
                    desc="Penanda titik tanggal kandidat agregat harian."
                    disableKeyboardNavigation
                    height={tokens.size.control * 4}
                    skipAnimation
                    sx={{
                       [`& .${lineClasses.line}[data-series="candidate-dates"]`]: {
                         display: 'none',
                       },
                    }}
                    xAxis={[{
                      id: 'candidate-date-axis',
                      data: data.candidates.map((candidate) => candidate.date),
                      label: 'Tanggal historis',
                      scaleType: 'time',
                    }]}
                     yAxis={[{
                       id: 'candidate-marker-axis',
                       min: -1,
                       max: 1,
                       position: 'none',
                     }]}
                    series={[{
                      id: 'candidate-dates',
                      data: data.candidates.map(() => 0),
                      label: 'Kandidat stabil',
                      color: colors.anomalyScore,
                      curve: 'linear',
                       shape: 'diamond',
                       showMark: true,
                       valueFormatter: () => 'Kandidat stabil',
                       xAxisId: 'candidate-date-axis',
                      yAxisId: 'candidate-marker-axis',
                    }]}
                  />
                </Box>
                <Stack direction="row" spacing={1} useFlexGap sx={{ flexWrap: 'wrap' }}>
                  {data.candidates.map((candidate) => (
                    <Chip
                      key={candidate.id}
                      size="small"
                      color="info"
                      label={`${candidate.dateLabel}: ${candidate.stabilityCount} penalti stabil`}
                    />
                  ))}
                </Stack>
                <Box
                  role="group"
                  aria-label="Perubahan dan efek MAD kandidat per kanal"
                  sx={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(min(320px,100%),1fr))',
                    gap: 4,
                    minWidth: 0,
                    '& > *': { minWidth: 0 },
                  }}
                >
                  {data.channels.flatMap((channel) => {
                    const color = channel.key === 'suhu' ? colors.temperature : colors.humidity
                    const xAxisId = `${channel.key}-candidate-axis`
                    return [
                      {
                        key: `${channel.key}-shift`,
                        id: `change-point-${channel.key}-shift`,
                        title: `Perubahan median ${channel.name}`,
                        axisLabel: `Perubahan ${channel.name} (${channel.shiftUnit})`,
                        data: channel.shifts,
                        unit: channel.shiftUnit,
                      },
                      {
                        key: `${channel.key}-effect`,
                        id: `change-point-${channel.key}-effect`,
                        title: `Efek MAD ${channel.name}`,
                        axisLabel: `Efek ${channel.name} (${channel.effectUnit})`,
                        data: channel.effects,
                        unit: channel.effectUnit,
                      },
                    ].map((chart) => {
                      const description = `${chart.title} pada tanggal kandidat agregat harian; ${channel.name} ditampilkan pada sumbu numeriknya sendiri.`
                      return (
                        <Paper component="article" key={chart.key} variant="outlined" sx={{ minWidth: 0, p: 4 }}>
                          <Stack spacing={1} sx={{ minWidth: 0 }}>
                            <Typography variant="h3">{chart.title}</Typography>
                            <Box
                              role="img"
                              aria-label={chart.title}
                              aria-description={description}
                              sx={{ minWidth: 0 }}
                            >
                              <LineChart
                                id={chart.id}
                                title={chart.title}
                                desc={description}
                                disableKeyboardNavigation
                                 height={tokens.size.control * 6}
                                 skipAnimation
                                 sx={{
                                   [`& .${lineClasses.line}[data-series="${chart.key}"]`]: {
                                     display: 'none',
                                   },
                                 }}
                                 xAxis={[{
                                  id: xAxisId,
                                  data: data.candidates.map((candidate) => candidate.date),
                                  label: 'Tanggal historis',
                                  scaleType: 'time',
                                }]}
                                yAxis={[{
                                  id: `${chart.key}-value-axis`,
                                  label: chart.axisLabel,
                                }]}
                                series={[{
                                  id: chart.key,
                                  data: chart.data,
                                  label: chart.title,
                                  color,
                                  connectNulls: false,
                                  curve: 'linear',
                                  showMark: true,
                                  valueFormatter: (value: number | null) => value === null ? '—' : `${value.toLocaleString('id-ID', { maximumFractionDigits: 4 })} ${chart.unit}`,
                                  xAxisId,
                                  yAxisId: `${chart.key}-value-axis`,
                                }]}
                              />
                            </Box>
                          </Stack>
                        </Paper>
                      )
                    })
                  })}
                </Box>
              </>
            )}
            {data.auditRows.length === 0 ? null : (
              <>
                <Button
                  aria-haspopup="dialog"
                  aria-label="Lihat data kandidat perubahan rezim"
                  size="small"
                  onClick={() => setDialogRunId(runId)}
                >
                  Lihat data
                </Button>
                <BoundedDataDialog<ChangePointAuditRow>
                  open={dialogRunId !== null && dialogRunId === runId}
                  title="Audit kandidat perubahan dan konfirmasi"
                  rows={data.auditRows}
                  returnedCount={data.auditRows.length}
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
