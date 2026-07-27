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
import { LineChart } from '@mui/x-charts/LineChart'
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

              return (
                <Paper key={channel.id} component="article" variant="outlined" sx={{ minWidth: 0, p: 4 }}>
                  <Stack spacing={2} sx={{ minWidth: 0, height: '100%' }}>
                    <Typography variant="h3">{channel.label}</Typography>
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
                </Paper>
              )
            })}
          </Box>
        )}
      </Stack>
    </Paper>
  )
}
