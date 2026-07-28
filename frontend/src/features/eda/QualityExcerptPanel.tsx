import { Alert, Box, Button, Paper, Stack, Typography } from '@mui/material'
import { useTheme } from '@mui/material/styles'
import { LineChart } from '@mui/x-charts/LineChart'
import type { GridColDef } from '@mui/x-data-grid'
import { useState } from 'react'
import {
  buildQualityExcerptData,
  EXCERPT_FLAG_LABELS,
  type ExcerptFlag,
  type QualityExcerptData,
} from '../../components/charts/edaV3Options'
import { getChartColors } from '../../components/charts/muiChartTheme'
import { BoundedDataDialog } from '../../components/data/BoundedDataDialog'
import { ApiErrorPanel } from '../../components/states/ApiErrorPanel'
import { EmptyState } from '../../components/states/EmptyState'
import { PanelSkeleton } from '../../components/states/PanelSkeleton'
import { tokens } from '../../theme/tokens'
import { useEdaSectionQuery } from './queries'
import { formatEdaReasonDetail } from './reasonLabels'

interface ExcerptTableRow {
  id: string
  timestamp: string
  suhu: number | null
  rh: number | null
  non_finite: boolean
  disconnected: boolean
  zero: boolean
  range: boolean
  duplicate: boolean
  conflicting_duplicate: boolean
  stale: boolean
  rule_screened: boolean
}

const flagColumns = (Object.entries(EXCERPT_FLAG_LABELS) as [ExcerptFlag, string][]).map(([field, headerName]) => ({
  field,
  headerName,
  minWidth: tokens.size.sidebarCompact,
  flex: 1,
  valueFormatter: (value: boolean) => value ? 'Ya' : 'Tidak',
}))

const excerptColumns: readonly GridColDef<ExcerptTableRow>[] = [
  { field: 'timestamp', headerName: 'Timestamp (Asia/Jakarta)', minWidth: tokens.size.sidebar, flex: 2 },
  { field: 'suhu', headerName: 'Suhu (°C)', flex: 1 },
  { field: 'rh', headerName: 'RH (%)', flex: 1 },
  ...flagColumns,
]

export interface QualityExcerptPanelProps {
  runId: string | null
}

export function QualityExcerptPanel({ runId }: QualityExcerptPanelProps) {
  const [dialogOpen, setDialogOpen] = useState(false)
  const theme = useTheme()
  const colors = getChartColors(theme)
  const query = useEdaSectionQuery(runId, 'quality_excerpt')
  const response = query.data
  const excerptData: QualityExcerptData | null = response?.status === 'complete' && response.section === 'quality_excerpt'
    ? buildQualityExcerptData(response.payload, theme)
    : null
  const retainedTimestamps = new Set(
    excerptData?.records.filter((record) => record.flags.rule_screened).map((record) => record.timestamp.getTime()),
  )
  const rows: ExcerptTableRow[] = excerptData?.records.map((record) => ({
    id: record.id,
    timestamp: new Intl.DateTimeFormat('id-ID', {
      dateStyle: 'medium',
      timeStyle: 'medium',
      timeZone: 'Asia/Jakarta',
    }).format(record.timestamp),
    suhu: record.suhu,
    rh: record.rh,
    ...record.flags,
  })) ?? []

  return (
    <Paper component="section" aria-labelledby="quality-excerpt-title" variant="outlined" sx={{ minWidth: 0, p: 4 }}>
      <Stack spacing={2} sx={{ minWidth: 0 }}>
        <Typography id="quality-excerpt-title" variant="h2">Excerpt kejadian kualitas</Typography>
        {runId === null ? (
          <EmptyState title="Pilih hasil EDA" detail="Excerpt kualitas tersedia setelah satu run dipilih." />
        ) : query.isError ? (
          <ApiErrorPanel error={query.error} onRetry={() => void query.refetch()} />
        ) : response === undefined ? (
          <PanelSkeleton label="Memuat excerpt kualitas" />
        ) : response.status === 'not_eligible' ? (
          <Alert severity="info" role="status">
            <strong>Excerpt kualitas belum memenuhi syarat.</strong><br />{formatEdaReasonDetail(response.reason_code, response.detail)}
          </Alert>
        ) : response.status === 'failed' ? (
          <Alert severity="error" role="alert">
            <strong>Excerpt kualitas gagal dihitung.</strong><br />{response.detail}
          </Alert>
        ) : excerptData === null || excerptData.records.length === 0 ? (
          <EmptyState title="Excerpt kualitas kosong" detail="Run tidak memuat record pada jendela kejadian terpilih." />
        ) : (
          <>
            <Alert severity="warning" role="note">
              <strong>Indikator kandidat kualitas — BUKAN label anomali atau ground truth.</strong>
              <br />Flag dapat tumpang tindih pada timestamp yang sama dan tidak menyatakan penyebab.
            </Alert>
            <Typography variant="body2" color="text.secondary">
              Seleksi <Box component="span" sx={{ fontFamily: tokens.font.data }}>{excerptData.selectionKind}</Box>; jendela konteks same-segment{' '}
              <Box component="span" sx={{ fontFamily: tokens.font.data }}>{excerptData.from.toLocaleString('id-ID', { timeZone: 'Asia/Jakarta' })}</Box>–
              <Box component="span" sx={{ fontFamily: tokens.font.data }}>{excerptData.to.toLocaleString('id-ID', { timeZone: 'Asia/Jakarta' })}</Box>;{' '}
              <Box component="span" sx={{ fontFamily: tokens.font.data }}>{excerptData.records.length.toLocaleString('id-ID')}</Box> record.
            </Typography>
            <Box
              role="group"
              aria-label="Garis Suhu dan RH pada excerpt kualitas"
              sx={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(min(320px, 100%), 1fr))',
                gap: 4,
                minWidth: 0,
              }}
            >
              {([
                { id: 'suhu', label: 'Suhu', unit: '°C', points: excerptData.temperature, color: colors.temperature },
                { id: 'rh', label: 'Kelembapan relatif', unit: '%', points: excerptData.humidity, color: colors.humidity },
              ] as const).map((channel) => {
                const description = `${channel.label} pada jendela kejadian ${excerptData.selectionKind}; garis terputus pada gap di atas 30 detik dan marker menunjukkan record rule-screened yang dipertahankan.`
                return (
                  <Box key={channel.id} component="article" sx={{ backgroundColor: theme.palette.background.default, minWidth: 0, p: 2 }}>
                    <Typography variant="subtitle2">{channel.label}</Typography>
                    <Box role="img" aria-label={`${channel.label} excerpt kualitas`} aria-description={description} sx={{ minWidth: 0 }}>
                      <LineChart
                        id={`quality-excerpt-${channel.id}-chart`}
                        title={`${channel.label} excerpt kualitas`}
                        desc={description}
                        disableKeyboardNavigation
                        height={tokens.size.control * 6}
                        skipAnimation
                        xAxis={[{
                          id: `${channel.id}-excerpt-time-axis`,
                          data: channel.points.map((point) => point.timestamp),
                          label: 'Waktu (Asia/Jakarta)',
                          scaleType: 'time',
                          min: excerptData.from,
                          max: excerptData.to,
                        }]}
                        yAxis={[{ id: `${channel.id}-excerpt-value-axis`, label: `${channel.label} (${channel.unit})` }]}
                        series={[
                          {
                            id: `${channel.id}-raw-series`,
                            data: channel.points.map((point) => point.value),
                            label: `${channel.label} raw`,
                            color: channel.color,
                            connectNulls: false,
                            curve: 'linear' as const,
                            showMark: false,
                            xAxisId: `${channel.id}-excerpt-time-axis`,
                            yAxisId: `${channel.id}-excerpt-value-axis`,
                          },
                          {
                            id: `${channel.id}-retained-series`,
                            data: channel.points.map((point) => (
                              retainedTimestamps.has(point.timestamp.getTime()) ? point.value : null
                            )),
                            label: 'Rule-screened retained',
                            color: theme.palette.success.main,
                            connectNulls: false,
                            curve: 'linear' as const,
                            showMark: true,
                            xAxisId: `${channel.id}-excerpt-time-axis`,
                            yAxisId: `${channel.id}-excerpt-value-axis`,
                          },
                        ]}
                      />
                    </Box>
                  </Box>
                )
              })}
            </Box>
            <Box component="article" sx={{ backgroundColor: theme.palette.background.default, minWidth: 0, p: 2 }}>
              <Stack spacing={1}>
                <Typography variant="subtitle2">Flag diagnostik tumpang tindih</Typography>
                <Box
                  role="img"
                  aria-label="Marker flag diagnostik per timestamp"
                  aria-description="Setiap baris adalah satu flag; beberapa baris dapat memiliki marker pada timestamp yang sama."
                  sx={{ minWidth: 0 }}
                >
                  {excerptData.flagStyles.map((flag) => (
                    <Box
                      key={flag.id}
                      sx={{
                        alignItems: 'center',
                        display: 'grid',
                        gap: 1,
                        gridTemplateColumns: `${tokens.size.sidebarCompact}px minmax(0, 1fr)`,
                        minHeight: tokens.size.control,
                        minWidth: 0,
                      }}
                    >
                      <Typography variant="caption">{flag.label}</Typography>
                      <Box sx={{ bgcolor: 'divider', height: tokens.size.rule, position: 'relative' }}>
                        {excerptData.records.filter((record) => record.flags[flag.id]).map((record) => (
                          <Box
                            key={record.id}
                            component="span"
                            title={`${flag.label}: ${record.timestamp.toISOString()}`}
                            aria-label={`${flag.label} pada ${record.timestamp.toISOString()}`}
                            sx={{
                              bgcolor: flag.color,
                              borderRadius: '50%',
                              height: tokens.spacing.unit * 2,
                              left: `${record.positionPercent}%`,
                              position: 'absolute',
                              top: '50%',
                              transform: 'translate(-50%, -50%)',
                              width: tokens.spacing.unit * 2,
                            }}
                          />
                        ))}
                      </Box>
                    </Box>
                  ))}
                </Box>
              </Stack>
            </Box>
            <Button size="small" onClick={() => setDialogOpen(true)}>Lihat data</Button>
            <BoundedDataDialog<ExcerptTableRow>
              open={dialogOpen}
              title={`Excerpt kualitas — ${excerptData.selectionKind}`}
              rows={rows}
              returnedCount={rows.length}
              columns={excerptColumns}
              onClose={() => setDialogOpen(false)}
            />
          </>
        )}
      </Stack>
    </Paper>
  )
}
