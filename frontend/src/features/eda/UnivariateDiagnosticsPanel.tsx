import {
  Alert,
  Box,
  Button,
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
import { useTheme } from '@mui/material/styles'
import { BarChart } from '@mui/x-charts/BarChart'
import { LineChart, lineClasses } from '@mui/x-charts/LineChart'
import type { GridColDef } from '@mui/x-data-grid'
import { useState } from 'react'
import { buildUnivariateData, formatFinitePercent } from '../../components/charts/edaV3Options'
import { BoundedDataDialog } from '../../components/data/BoundedDataDialog'
import { ApiErrorPanel } from '../../components/states/ApiErrorPanel'
import { EmptyState } from '../../components/states/EmptyState'
import { PanelSkeleton } from '../../components/states/PanelSkeleton'
import { tokens } from '../../theme/tokens'
import { useEdaSectionQuery } from './queries'
import { formatEdaReasonDetail } from './reasonLabels'
import { boxStats, moments as calculateMoments, qqPoints } from './univariateShape'

interface UnivariateBinRow {
  id: string
  start: number
  end: number
  rawCount: number
  screenedCount: number
  rawEcdf: number
  screenedEcdf: number
}

const binColumns: readonly GridColDef<UnivariateBinRow>[] = [
  { field: 'start', headerName: 'Bin mulai', flex: 1 },
  { field: 'end', headerName: 'Bin akhir', flex: 1 },
  { field: 'rawCount', headerName: 'Raw', flex: 1 },
  { field: 'screenedCount', headerName: 'Screened', flex: 1 },
  { field: 'rawEcdf', headerName: 'ECDF raw', flex: 1 },
  { field: 'screenedEcdf', headerName: 'ECDF screened', flex: 1 },
]

const shapeValueSx = {
  fontFamily: tokens.font.data,
  fontSize: tokens.font.size.summaryValue,
  fontVariantNumeric: 'tabular-nums',
  lineHeight: tokens.font.lineHeight.summaryValue,
} as const

const nearZero = 0.1

function shapeNumber(value: number): string {
  return value.toLocaleString('id-ID', { maximumFractionDigits: 3, minimumFractionDigits: 3 })
}

function skewnessLabel(value: number): string {
  if (Math.abs(value) < nearZero) return 'simetris'
  return value > 0 ? 'condong kanan' : 'condong kiri'
}

function kurtosisLabel(value: number): string {
  if (Math.abs(value) < nearZero) return 'mesokurtik'
  return value > 0 ? 'leptokurtik / ekor tebal' : 'platykurtik / ekor tipis'
}

function domainPosition(value: number, minimum: number, maximum: number): string {
  const percent = ((value - minimum) / (maximum - minimum)) * 100
  return `${Math.min(100, Math.max(0, percent))}%`
}

export interface UnivariateDiagnosticsPanelProps {
  runId: string | null
}

export function UnivariateDiagnosticsPanel({ runId }: UnivariateDiagnosticsPanelProps) {
  const [openChannel, setOpenChannel] = useState<'Suhu' | 'RH'>()
  const theme = useTheme()
  const univariateQuery = useEdaSectionQuery(runId, 'univariate')
  const overviewQuery = useEdaSectionQuery(runId, 'quality_overview')
  const univariate = univariateQuery.data
  const overview = overviewQuery.data
  const channels = (
    univariate?.status === 'complete' && univariate.section === 'univariate' &&
    overview?.status === 'complete' && overview.section === 'quality_overview'
  ) ? buildUnivariateData(univariate.payload, overview.payload, theme) : []
  const pending = univariate === undefined || overview === undefined
  const ineligible = univariate?.status === 'not_eligible'
    ? univariate
    : overview?.status === 'not_eligible' ? overview : null

  return (
    <Paper component="section" aria-labelledby="univariate-title" variant="outlined" sx={{ minWidth: 0, p: 4 }}>
      <Stack spacing={2} sx={{ minWidth: 0 }}>
        <Typography id="univariate-title" variant="h2">Diagnostik univariat</Typography>
        {runId === null ? (
          <EmptyState title="Pilih hasil EDA" detail="Distribusi univariat tersedia setelah satu run dipilih." />
        ) : univariateQuery.isError || overviewQuery.isError ? (
          <Stack spacing={1}>
            {univariateQuery.isError ? (
              <ApiErrorPanel error={univariateQuery.error} onRetry={() => void univariateQuery.refetch()} />
            ) : null}
            {overviewQuery.isError ? (
              <ApiErrorPanel error={overviewQuery.error} onRetry={() => void overviewQuery.refetch()} />
            ) : null}
          </Stack>
        ) : pending ? (
          <PanelSkeleton label="Memuat diagnostik univariat" />
        ) : ineligible !== null ? (
          <Alert severity="info" role="status">
            <strong>Diagnostik univariat belum memenuhi syarat.</strong><br />
            {formatEdaReasonDetail(ineligible.reason_code, ineligible.detail)}
          </Alert>
        ) : univariate.status === 'failed' || overview.status === 'failed' ? (
          <Alert severity="error" role="alert">
            <strong>Diagnostik univariat gagal dihitung.</strong><br />
            {univariate.status === 'failed' ? univariate.detail : overview.detail}
          </Alert>
        ) : channels.length === 0 ? (
          <EmptyState title="Distribusi univariat kosong" detail="Histogram, ECDF, atau audit finite tidak tersedia pada run ini." />
        ) : (
          <Box
            role="group"
            aria-label="Diagnostik univariat Suhu dan RH"
            sx={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(min(320px, 100%), 1fr))',
              gap: 4,
              minWidth: 0,
            }}
          >
            {channels.map((channel) => {
              const rows: UnivariateBinRow[] = channel.edges.slice(0, -1).map((start, index) => ({
                id: `${channel.id}-${index}`,
                start,
                end: channel.edges[index + 1] ?? start,
                rawCount: channel.views[0].histogram[index] ?? 0,
                screenedCount: channel.views[1].histogram[index] ?? 0,
                rawEcdf: channel.views[0].ecdfFraction[index] ?? 0,
                screenedEcdf: channel.views[1].ecdfFraction[index] ?? 0,
              }))
              const description = `${channel.label} ${channel.unit}; ${channel.edges.length - 1} bin dalam domain. Raw finite ${channel.views[0].finite.toLocaleString('id-ID')} dan screened finite ${channel.views[1].finite.toLocaleString('id-ID')}.`
              const auditRows = [
                { label: 'Penyebut finite', values: channel.views.map((view) => view.finite) },
                { label: 'Non-finite', values: channel.views.map((view) => view.nonFinite) },
                { label: 'Underflow', values: channel.views.map((view) => view.underflow) },
                { label: 'Dalam domain', values: channel.views.map((view) => view.inDomain) },
                { label: 'Overflow', values: channel.views.map((view) => view.overflow) },
                { label: 'Excluded finite', values: channel.views.map((view) => view.excludedFinite) },
              ]
              const shapeViews = channel.views.map((view) => {
                const input = { edges: channel.edges, histogram: view.histogram }
                const qq = qqPoints(input)
                const referenceData = qq === null ? [] : qq.points.map((point) => {
                  const [start, end] = qq.referenceLine
                  const fraction = (point.theoretical - start!.theoretical) /
                    (end!.theoretical - start!.theoretical)
                  return start!.sample + fraction * (end!.sample - start!.sample)
                })
                return {
                  view,
                  box: boxStats(input),
                  moments: calculateMoments(input),
                  qq,
                  referenceData,
                }
              })

              return (
                <Box key={channel.id} component="article" sx={{ backgroundColor: theme.palette.background.default, minWidth: 0, p: 4 }}>
                  <Stack spacing={2} sx={{ minWidth: 0, height: '100%' }}>
                    <Typography variant="subtitle2">{channel.label}</Typography>
                    <Typography variant="body2" color="text.secondary">{description}</Typography>
                    <Box role="img" aria-label={`Histogram ${channel.label}`} aria-description={description} sx={{ minWidth: 0 }}>
                      <BarChart
                        id={`${channel.id.toLowerCase()}-histogram-chart`}
                        title={`Histogram ${channel.label}`}
                        desc={description}
                        disableKeyboardNavigation
                        height={tokens.size.control * 6}
                        skipAnimation
                        xAxis={[{
                          id: `${channel.id}-histogram-axis`,
                          data: channel.centers,
                          label: `${channel.label} (${channel.unit})`,
                          scaleType: 'band',
                          categoryGapRatio: 0,
                          barGapRatio: 0,
                        }]}
                        yAxis={[{ id: `${channel.id}-histogram-count-axis`, label: 'Jumlah dalam domain' }]}
                        series={channel.views.map((view) => ({
                          id: `${channel.id}-${view.id}-histogram`,
                          data: view.histogram,
                          label: view.label,
                          color: view.color,
                          xAxisId: `${channel.id}-histogram-axis`,
                          yAxisId: `${channel.id}-histogram-count-axis`,
                        }))}
                      />
                    </Box>
                    <Box role="img" aria-label={`ECDF ${channel.label}`} aria-description={description} sx={{ minWidth: 0 }}>
                      <LineChart
                        id={`${channel.id.toLowerCase()}-ecdf-chart`}
                        title={`ECDF ${channel.label}`}
                        desc={description}
                        disableKeyboardNavigation
                        height={tokens.size.control * 6}
                        skipAnimation
                        xAxis={[{
                          id: `${channel.id}-ecdf-axis`,
                          data: channel.ecdfX,
                          label: `${channel.label} (${channel.unit})`,
                          scaleType: 'linear',
                        }]}
                        yAxis={[{
                          id: `${channel.id}-ecdf-fraction-axis`,
                          label: 'Fraksi histogram dalam domain',
                          min: 0,
                          max: 1,
                        }]}
                        series={channel.views.map((view) => ({
                          id: `${channel.id}-${view.id}-ecdf`,
                          data: view.ecdfFraction,
                          label: view.label,
                          color: view.color,
                          curve: 'stepAfter' as const,
                          showMark: false,
                          valueFormatter: (value: number | null) => value === null ? null : value.toFixed(4),
                          xAxisId: `${channel.id}-ecdf-axis`,
                          yAxisId: `${channel.id}-ecdf-fraction-axis`,
                        }))}
                      />
                    </Box>
                    <TableContainer>
                      <Table size="small" aria-label={`Audit finite ${channel.label}`}>
                        <TableHead>
                          <TableRow>
                            <TableCell scope="col">Audit massa</TableCell>
                            {channel.views.map((view) => <TableCell key={view.id} scope="col" align="right">{view.label}</TableCell>)}
                          </TableRow>
                        </TableHead>
                        <TableBody>
                          {auditRows.map((row) => (
                            <TableRow key={row.label}>
                              <TableCell component="th" scope="row">{row.label}</TableCell>
                              {row.values.map((value, index) => (
                                <TableCell key={channel.views[index].id} align="right" sx={{ fontFamily: tokens.font.data }}>
                                  {value.toLocaleString('id-ID')}
                                  {row.label === 'Penyebut finite' ? '' : ` (${formatFinitePercent(value, channel.views[index].finite)})`}
                                </TableCell>
                              ))}
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </TableContainer>
                    <Typography variant="caption" color="text.secondary">
                      Penyebut ECDF dalam-domain: raw {channel.views[0].ecdfDenominator.toLocaleString('id-ID')}; screened {channel.views[1].ecdfDenominator.toLocaleString('id-ID')}.
                    </Typography>
                    <Stack spacing={2} sx={{ minWidth: 0 }}>
                      <Typography variant="subtitle2">Bentuk distribusi</Typography>
                      <Typography variant="caption" color="text.secondary">
                        Semua ringkasan berikut adalah aproksimasi berbasis histogram/ECDF ter-bin, bukan dari sampel mentah.
                      </Typography>

                      <Stack spacing={1} sx={{ minWidth: 0 }}>
                        <Typography variant="body2" sx={{ fontWeight: 700 }}>Boxplot horizontal</Typography>
                        <Box
                          data-testid={`univariate-boxplot-${channel.id}`}
                          role="group"
                          aria-label={`Boxplot aproksimasi ${channel.label}`}
                          sx={{
                            display: 'grid',
                            gridTemplateColumns: `repeat(auto-fit, minmax(min(${tokens.size.sidebar}px, 100%), 1fr))`,
                            gap: 2,
                            minWidth: 0,
                          }}
                        >
                          {shapeViews.map((shape) => {
                            if (shape.box === null || shape.moments === null || shape.qq === null) {
                              return (
                                <Stack key={shape.view.id} spacing={0.5}>
                                  <Typography variant="caption" sx={{ color: shape.view.color, fontWeight: 700 }}>
                                    {shape.view.label}
                                  </Typography>
                                  <Typography variant="caption" color="text.secondary">Tidak cukup data untuk bentuk distribusi.</Typography>
                                </Stack>
                              )
                            }
                            const stats = shape.box
                            const boxDescription = `${shape.view.label}; Q1 ${shapeNumber(stats.q1)}, median ${shapeNumber(stats.median)}, Q3 ${shapeNumber(stats.q3)}, whisker ${shapeNumber(stats.whiskerLow)} sampai ${shapeNumber(stats.whiskerHigh)} ${channel.unit}.`
                            const low = domainPosition(stats.whiskerLow, stats.min, stats.max)
                            const high = domainPosition(stats.whiskerHigh, stats.min, stats.max)
                            const q1 = domainPosition(stats.q1, stats.min, stats.max)
                            const q3 = domainPosition(stats.q3, stats.min, stats.max)
                            return (
                              <Stack key={shape.view.id} spacing={0.5} sx={{ minWidth: 0 }}>
                                <Typography variant="caption" sx={{ color: shape.view.color, fontWeight: 700 }}>
                                  {shape.view.label}
                                </Typography>
                                <Box
                                  role="img"
                                  aria-label={`Boxplot ${shape.view.label} ${channel.label}`}
                                  aria-description={boxDescription}
                                  sx={{
                                    position: 'relative',
                                    height: tokens.size.control,
                                    minWidth: 0,
                                    borderBlock: `${tokens.size.rule}px solid ${theme.palette.divider}`,
                                    backgroundColor: theme.palette.background.default,
                                  }}
                                >
                                  <Box
                                    aria-hidden
                                    sx={{
                                      position: 'absolute',
                                      top: '50%',
                                      left: low,
                                      width: `calc(${high} - ${low})`,
                                      borderTop: `${tokens.spacing.unit / 2}px solid ${shape.view.color}`,
                                      '&::before, &::after': {
                                        content: '""',
                                        position: 'absolute',
                                        top: -tokens.spacing.unit,
                                        height: tokens.spacing.unit * 2,
                                        borderLeft: `${tokens.spacing.unit / 2}px solid ${shape.view.color}`,
                                      },
                                      '&::before': { left: 0 },
                                      '&::after': { right: 0 },
                                    }}
                                  />
                                  <Box
                                    aria-hidden
                                    sx={{
                                      position: 'absolute',
                                      top: '50%',
                                      left: q1,
                                      width: `calc(${q3} - ${q1})`,
                                      height: tokens.spacing.unit * 5,
                                      border: `${tokens.spacing.unit / 2}px solid ${shape.view.color}`,
                                      backgroundColor: theme.palette.background.paper,
                                      transform: 'translateY(-50%)',
                                    }}
                                  />
                                  <Box
                                    aria-hidden
                                    sx={{
                                      position: 'absolute',
                                      top: '50%',
                                      left: domainPosition(stats.median, stats.min, stats.max),
                                      width: tokens.spacing.unit / 2,
                                      height: tokens.spacing.unit * 7,
                                      backgroundColor: shape.view.color,
                                      transform: 'translate(-50%, -50%)',
                                    }}
                                  />
                                </Box>
                                <Stack direction="row" sx={{ justifyContent: 'space-between' }}>
                                  <Typography variant="caption" color="text.secondary">{shapeNumber(stats.min)} {channel.unit}</Typography>
                                  <Typography variant="caption" color="text.secondary">{shapeNumber(stats.max)} {channel.unit}</Typography>
                                </Stack>
                              </Stack>
                            )
                          })}
                        </Box>
                      </Stack>

                      <Stack spacing={1} sx={{ minWidth: 0 }}>
                        <Typography variant="body2" sx={{ fontWeight: 700 }}>QQ-plot normal</Typography>
                        <Box
                          data-testid={`univariate-qq-${channel.id}`}
                          role="group"
                          aria-label={`QQ-plot normal aproksimasi ${channel.label}`}
                          sx={{
                            display: 'grid',
                            gridTemplateColumns: `repeat(auto-fit, minmax(min(${tokens.size.sidebar}px, 100%), 1fr))`,
                            gap: 2,
                            minWidth: 0,
                          }}
                        >
                          {shapeViews.map((shape) => {
                            if (shape.box === null || shape.moments === null || shape.qq === null) {
                              return (
                                <Typography key={shape.view.id} variant="caption" color="text.secondary">
                                  {shape.view.label}: tidak cukup data untuk QQ-plot.
                                </Typography>
                              )
                            }
                            const sampleSeriesId = `${channel.id}-${shape.view.id}-qq-sample`
                            const referenceSeriesId = `${channel.id}-${shape.view.id}-qq-reference`
                            const qqDescription = `${shape.view.label}; kuantil sampel diaproksimasi dari histogram ter-bin dan dibandingkan dengan garis normal berbasis mean ${shapeNumber(shape.moments.mean)} serta simpangan baku ${shapeNumber(shape.moments.std)} ${channel.unit}.`
                            return (
                              <Box
                                key={shape.view.id}
                                role="img"
                                aria-label={`QQ-plot normal ${shape.view.label} ${channel.label}`}
                                aria-description={qqDescription}
                                sx={{ minWidth: 0 }}
                              >
                                <LineChart
                                  id={`${channel.id.toLowerCase()}-${shape.view.id}-qq-chart`}
                                  title={`QQ-plot ${shape.view.label} ${channel.label}`}
                                  desc={qqDescription}
                                  disableKeyboardNavigation
                                  height={tokens.size.control * 6}
                                  skipAnimation
                                  sx={{
                                    [`& .${lineClasses.line}[data-series="${sampleSeriesId}"]`]: {
                                      display: 'none',
                                    },
                                    [`& .${lineClasses.line}[data-series="${referenceSeriesId}"]`]: {
                                      strokeDasharray: `${tokens.spacing.unit} ${tokens.spacing.unit}`,
                                    },
                                  }}
                                  xAxis={[{
                                    id: `${channel.id}-${shape.view.id}-qq-theoretical-axis`,
                                    data: shape.qq.points.map((point) => point.theoretical),
                                    label: 'Kuantil normal teoretis',
                                    scaleType: 'linear',
                                  }]}
                                  yAxis={[{
                                    id: `${channel.id}-${shape.view.id}-qq-sample-axis`,
                                    label: `${channel.label} (${channel.unit})`,
                                  }]}
                                  series={[
                                    {
                                      id: sampleSeriesId,
                                      data: shape.qq.points.map((point) => point.sample),
                                      label: `${shape.view.label} — kuantil sampel`,
                                      color: shape.view.color,
                                      curve: 'linear',
                                      showMark: true,
                                      valueFormatter: (value: number | null) => value === null ? '—' : `${shapeNumber(value)} ${channel.unit}`,
                                      xAxisId: `${channel.id}-${shape.view.id}-qq-theoretical-axis`,
                                      yAxisId: `${channel.id}-${shape.view.id}-qq-sample-axis`,
                                    },
                                    {
                                      id: referenceSeriesId,
                                      data: shape.referenceData,
                                      label: 'Referensi normal',
                                      color: shape.view.color,
                                      curve: 'linear',
                                      disableHighlight: true,
                                      showMark: false,
                                      valueFormatter: (value: number | null) => value === null ? '—' : `${shapeNumber(value)} ${channel.unit}`,
                                      xAxisId: `${channel.id}-${shape.view.id}-qq-theoretical-axis`,
                                      yAxisId: `${channel.id}-${shape.view.id}-qq-sample-axis`,
                                    },
                                  ]}
                                />
                              </Box>
                            )
                          })}
                        </Box>
                      </Stack>

                      <Stack spacing={1} sx={{ minWidth: 0 }}>
                        <Typography variant="body2" sx={{ fontWeight: 700 }}>Momen bentuk</Typography>
                        <Box
                          data-testid={`univariate-skew-${channel.id}`}
                          role="group"
                          aria-label={`Skewness dan excess kurtosis aproksimasi ${channel.label}`}
                          sx={{
                            display: 'grid',
                            gridTemplateColumns: `repeat(auto-fit, minmax(min(${tokens.size.sidebar}px, 100%), 1fr))`,
                            gap: 2,
                            minWidth: 0,
                          }}
                        >
                          {shapeViews.map((shape) => (
                            <Stack key={shape.view.id} spacing={1} sx={{ minWidth: 0 }}>
                              <Typography variant="caption" sx={{ color: shape.view.color, fontWeight: 700 }}>
                                {shape.view.label}
                              </Typography>
                              {shape.moments === null || shape.box === null || shape.qq === null ? (
                                <Typography variant="caption" color="text.secondary">Tidak cukup data untuk momen bentuk.</Typography>
                              ) : (
                                <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: 2 }}>
                                  <Stack spacing={0.5}>
                                    <Typography sx={shapeValueSx}>{shapeNumber(shape.moments.skewness)}</Typography>
                                    <Typography variant="body2">Skewness · {skewnessLabel(shape.moments.skewness)}</Typography>
                                  </Stack>
                                  <Stack spacing={0.5}>
                                    <Typography sx={shapeValueSx}>{shapeNumber(shape.moments.excessKurtosis)}</Typography>
                                    <Typography variant="body2">Excess kurtosis · {kurtosisLabel(shape.moments.excessKurtosis)}</Typography>
                                  </Stack>
                                </Box>
                              )}
                            </Stack>
                          ))}
                        </Box>
                      </Stack>
                    </Stack>
                    <Button size="small" onClick={() => setOpenChannel(channel.id)} sx={{ mt: 'auto' }}>
                      Lihat data
                    </Button>
                    <BoundedDataDialog<UnivariateBinRow>
                      open={openChannel === channel.id}
                      title={`${channel.label} — histogram dan ECDF`}
                      rows={rows}
                      returnedCount={rows.length}
                      columns={binColumns}
                      onClose={() => setOpenChannel(undefined)}
                    />
                  </Stack>
                </Box>
              )
            })}
          </Box>
        )}
      </Stack>
    </Paper>
  )
}
