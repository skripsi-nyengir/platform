import { Box, Button, Chip, Paper, Stack, Typography } from '@mui/material'
import { useTheme } from '@mui/material/styles'
import type { GridColDef } from '@mui/x-data-grid'
import { Fragment, useState } from 'react'
import { ApiError } from '../../api/errors'
import {
  buildBootstrapForestData,
  formatCoefficient,
  type BootstrapForestRow,
  type RelationshipStatistic,
} from '../../components/charts/relationshipEdaOptions'
import { getChartColors } from '../../components/charts/muiChartTheme'
import { BoundedDataDialog } from '../../components/data/BoundedDataDialog'
import { ApiErrorPanel } from '../../components/states/ApiErrorPanel'
import { EmptyState } from '../../components/states/EmptyState'
import { PanelSkeleton } from '../../components/states/PanelSkeleton'
import { tokens } from '../../theme/tokens'
import { useEdaSectionQuery } from './queries'
import { edaReasonLabel, formatEdaReasonDetail } from './reasonLabels'

export interface BootstrapUncertaintyPanelProps {
  runId: string | null
}

const statisticLabels: Record<RelationshipStatistic, string> = {
  pearson: 'Pearson',
  spearman: 'Spearman',
}

const sensitivityLabels = {
  robust: 'Konsisten antarblok',
  not_robust: 'Sensitif terhadap panjang blok',
  insufficient_data: 'Bukti antarblok belum cukup',
} as const

const technicalTextSx = {
  fontFamily: tokens.font.data,
  fontVariantNumeric: 'tabular-nums',
  overflowWrap: 'anywhere',
} as const

const bootstrapColumns: readonly GridColDef<BootstrapForestRow>[] = [
  { field: 'blockDays', headerName: 'Blok (hari)', flex: 1 },
  { field: 'statistic', headerName: 'Koefisien', flex: 1 },
  { field: 'blockStatus', headerName: 'Status blok', flex: 1 },
  { field: 'intervalStatus', headerName: 'Status interval', flex: 1 },
  { field: 'reasonCode', headerName: 'Alasan', flex: 1.5 },
  { field: 'pairCount', headerName: 'Hari berpasangan', flex: 1 },
  { field: 'runCount', headerName: 'Run', flex: 1 },
  { field: 'replicateCount', headerName: 'Replikasi', flex: 1 },
  { field: 'estimate', headerName: 'Estimasi', flex: 1, valueFormatter: formatCoefficient },
  { field: 'lower', headerName: 'Batas bawah 95%', flex: 1, valueFormatter: formatCoefficient },
  { field: 'upper', headerName: 'Batas atas 95%', flex: 1, valueFormatter: formatCoefficient },
]

function coefficientPosition(value: number): string {
  return `${((value + 1) / 2) * 100}%`
}

export function BootstrapUncertaintyPanel({ runId }: BootstrapUncertaintyPanelProps) {
  const [dialogRunId, setDialogRunId] = useState<string | null>(null)
  const query = useEdaSectionQuery(runId, 'uncertainty')
  const theme = useTheme()
  const colors = getChartColors(theme)
  const section = query.data
  const data = section?.status === 'complete' && section.section === 'uncertainty'
    ? buildBootstrapForestData(section.payload)
    : undefined
  const description = data === undefined
    ? undefined
    : `Forest plot estimasi Pearson dan Spearman dengan interval bootstrap 95 persen untuk blok 7, 14, dan 28 hari. Garis vertikal menunjukkan nol. Baris tanpa bukti yang cukup tidak memiliki titik atau whisker.`

  return (
    <Paper
      component="section"
      aria-labelledby="bootstrap-uncertainty-heading"
      variant="outlined"
      sx={{ minWidth: 0, p: 4 }}
    >
      <Stack spacing={2} sx={{ minWidth: 0 }}>
        <Stack
          direction="row"
          spacing={1}
          useFlexGap
          sx={{ alignItems: 'center', flexWrap: 'wrap', minWidth: 0 }}
        >
          <Typography id="bootstrap-uncertainty-heading" variant="h2" sx={{ flexGrow: 1 }}>
            Ketidakpastian bootstrap asosiasi
          </Typography>
          {section?.status === 'complete' && section.section === 'uncertainty' ? (
            <Chip
              size="small"
              color={section.payload.sensitivity_status === 'robust' ? 'success' : 'default'}
              label={sensitivityLabels[section.payload.sensitivity_status]}
            />
          ) : null}
        </Stack>

        {runId === null ? (
          <EmptyState
            title="Pilih run EDA"
            detail="Ketidakpastian bootstrap ditampilkan setelah run EDA dipilih."
          />
        ) : section === undefined ? (
          query.isError ? (
            <ApiErrorPanel error={query.error} onRetry={() => void query.refetch()} />
          ) : (
            <PanelSkeleton label="Memuat ketidakpastian bootstrap" />
          )
        ) : section.status === 'not_eligible' ? (
          <EmptyState title="Bootstrap belum memenuhi syarat" detail={formatEdaReasonDetail(section.reason_code, section.detail)} />
        ) : section.status === 'failed' ? (
          <ApiErrorPanel
            error={new ApiError('problem', section.detail)}
            onRetry={() => void query.refetch()}
          />
        ) : data === undefined || data.length === 0 ? (
          <EmptyState
            title="Tidak ada hasil bootstrap"
            detail="Run selesai tanpa blok bootstrap yang dapat ditampilkan."
          />
        ) : (
          <>
            <Typography variant="body2" color="text.secondary">
              Bootstrap paired moving-block ini menggambarkan populasi median harian berpasangan, bukan pasangan mentah. Interval 95% menunjukkan variasi hasil replikasi pada skema blok yang ditetapkan; bukan bukti sebab-akibat atau observasi independen.
            </Typography>
            <Box
              role="group"
              aria-label="Forest plot ketidakpastian Pearson dan Spearman"
              aria-description={description}
              sx={{ minWidth: 0 }}
            >
              <Box
                sx={{
                  display: 'grid',
                  gridTemplateColumns: 'minmax(0,0.8fr) minmax(0,2fr) minmax(0,1fr)',
                  gap: 2,
                  alignItems: 'center',
                  minWidth: 0,
                  '& [data-mobile-label]': { display: 'none' },
                  '@media (max-width: 720px)': {
                    gridTemplateColumns: 'minmax(0,1fr)',
                    '& > [data-desktop-header]': { display: 'none' },
                    '& [data-mobile-label]': { display: 'block' },
                    '& > [data-track-cell]': { mb: 1 },
                  },
                }}
              >
                <Typography data-desktop-header variant="caption" color="text.secondary">Blok dan koefisien</Typography>
                <Typography data-desktop-header variant="caption" color="text.secondary">Koefisien (−1 sampai 1)</Typography>
                <Typography data-desktop-header variant="caption" color="text.secondary">Hari berpasangan / run</Typography>
                {data.map((row) => {
                  const color = row.statistic === 'pearson' ? colors.temperature : colors.humidity
                  const eligible = row.blockStatus === 'complete' && row.intervalStatus === 'ok' &&
                    row.estimate !== null && row.lower !== null && row.upper !== null
                  return (
                    <Fragment key={row.id}>
                      <Stack spacing={0.5} sx={{ minWidth: 0 }}>
                        <Typography variant="body2" sx={{ fontWeight: 700 }}>
                          {row.blockDays} hari · {statisticLabels[row.statistic]}
                        </Typography>
                        {eligible ? (
                          <Typography variant="caption" color="text.secondary" sx={technicalTextSx}>
                            {formatCoefficient(row.estimate)} [{formatCoefficient(row.lower)}, {formatCoefficient(row.upper)}]
                            {row.crossesZero ? ' · melintasi nol' : ''}
                          </Typography>
                        ) : (
                          <Chip size="small" label="Tidak memenuhi syarat" sx={{ alignSelf: 'flex-start' }} />
                        )}
                      </Stack>
                      <Stack data-track-cell spacing={0.5} sx={{ minWidth: 0 }}>
                        <Typography data-mobile-label variant="caption" color="text.secondary">
                          Koefisien (−1 sampai 1)
                        </Typography>
                        <Box
                          role={eligible ? 'img' : undefined}
                          aria-label={eligible
                            ? `Interval bootstrap ${statisticLabels[row.statistic]} blok ${row.blockDays} hari`
                            : undefined}
                          aria-description={eligible
                            ? `Estimasi ${formatCoefficient(row.estimate)}, interval 95 persen ${formatCoefficient(row.lower)} sampai ${formatCoefficient(row.upper)}; garis referensi nol.`
                            : undefined}
                          sx={{
                            position: 'relative',
                            height: tokens.size.control,
                            minWidth: 0,
                            borderBlock: `1px solid ${theme.palette.divider}`,
                            backgroundColor: theme.palette.background.default,
                          }}
                        >
                          <Box
                            aria-hidden
                            sx={{
                              position: 'absolute',
                              insetBlock: 0,
                              left: '50%',
                              borderLeft: `1px dashed ${colors.threshold}`,
                            }}
                          />
                          {eligible ? (
                            <>
                              <Box
                                data-testid={`bootstrap-whisker-${row.blockDays}-${row.statistic}`}
                                aria-hidden
                                sx={{
                                  position: 'absolute',
                                  top: '50%',
                                  left: coefficientPosition(row.lower!),
                                  width: `calc(${coefficientPosition(row.upper!)} - ${coefficientPosition(row.lower!)})`,
                                  borderTop: `${tokens.spacing.unit / 2}px solid ${color}`,
                                  '&::before, &::after': {
                                    content: '""',
                                    position: 'absolute',
                                    top: -tokens.spacing.unit,
                                    height: tokens.spacing.unit * 2,
                                    borderLeft: `${tokens.spacing.unit / 2}px solid ${color}`,
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
                                  left: coefficientPosition(row.estimate!),
                                  width: tokens.spacing.unit * 3,
                                  height: tokens.spacing.unit * 3,
                                  borderRadius: '50%',
                                  backgroundColor: color,
                                  transform: 'translate(-50%, -50%)',
                                }}
                              />
                            </>
                          ) : (
                            <Typography
                              variant="caption"
                              color="text.secondary"
                              sx={{
                                position: 'absolute',
                                inset: 0,
                                display: 'grid',
                                placeItems: 'center',
                                px: 1,
                                textAlign: 'center',
                              }}
                            >
                              {row.reasonCode === null ? row.intervalStatus : edaReasonLabel(row.reasonCode)}
                            </Typography>
                          )}
                        </Box>
                      </Stack>
                      <Stack spacing={0.5} sx={{ minWidth: 0 }}>
                        <Typography data-mobile-label variant="caption" color="text.secondary">
                          Hari berpasangan / run
                        </Typography>
                        <Typography variant="body2" sx={technicalTextSx}>
                          {row.pairCount.toLocaleString('id-ID')} / {row.runCount.toLocaleString('id-ID')}
                        </Typography>
                      </Stack>
                    </Fragment>
                  )
                })}
              </Box>
            </Box>
            <Button
              size="small"
              aria-label="Lihat data bootstrap"
              onClick={() => setDialogRunId(runId)}
            >
              Lihat data
            </Button>
            <BoundedDataDialog<BootstrapForestRow>
              open={dialogRunId !== null && dialogRunId === runId}
              title="Data bootstrap asosiasi median harian"
              rows={data}
              returnedCount={data.length}
              columns={bootstrapColumns}
              onClose={() => setDialogRunId(null)}
            />
          </>
        )}
      </Stack>
    </Paper>
  )
}
