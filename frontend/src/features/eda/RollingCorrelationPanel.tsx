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
  buildRollingCorrelationData,
  coefficientDomain,
  formatCoefficient,
  rollingGapSeconds,
  rollingWindowMinutes,
  type RelationshipView,
  type RollingCorrelationRow,
  type RollingGapSeconds,
  type RollingWindowMinutes,
} from '../../components/charts/relationshipEdaOptions'
import { getChartColors } from '../../components/charts/muiChartTheme'
import { BoundedDataDialog } from '../../components/data/BoundedDataDialog'
import { ApiErrorPanel } from '../../components/states/ApiErrorPanel'
import { EmptyState } from '../../components/states/EmptyState'
import { PanelSkeleton } from '../../components/states/PanelSkeleton'
import { tokens } from '../../theme/tokens'
import { useEdaSectionQuery } from './queries'
import { formatEdaReasonDetail } from './reasonLabels'

export interface RollingCorrelationPanelProps {
  runId: string | null
}

const viewLabels: Record<RelationshipView, string> = {
  resolved_raw_pairs: 'Pasangan exact mentah',
  rule_screened_pairs: 'Lolos screening aturan',
}

const technicalTextSx = {
  fontFamily: tokens.font.data,
  fontVariantNumeric: 'tabular-nums',
  overflowWrap: 'anywhere',
} as const

const rollingColumns: readonly GridColDef<RollingCorrelationRow>[] = [
  { field: 'timestamp', headerName: 'Akhir jendela (UTC)', flex: 2 },
  {
    field: 'correlation',
    headerName: 'Pearson',
    flex: 1,
    valueFormatter: (value: number | null) => formatCoefficient(value),
  },
  { field: 'gapBreak', headerName: 'Pemutus gap', type: 'boolean', flex: 1 },
]

export function RollingCorrelationPanel({ runId }: RollingCorrelationPanelProps) {
  const viewLabelId = useId()
  const windowLabelId = useId()
  const gapLabelId = useId()
  const [view, setView] = useState<RelationshipView>('rule_screened_pairs')
  const [windowMinutes, setWindowMinutes] = useState<RollingWindowMinutes>(30)
  const [gapSeconds, setGapSeconds] = useState<RollingGapSeconds>(30)
  const [dialogRunId, setDialogRunId] = useState<string | null>(null)
  const query = useEdaSectionQuery(runId, 'relationships')
  const theme = useTheme()
  const colors = getChartColors(theme)
  const section = query.data
  const data = section?.status === 'complete' && section.section === 'relationships'
    ? buildRollingCorrelationData(section.payload, view, windowMinutes, gapSeconds)
    : undefined
  const description = data?.status === 'complete'
    ? `Korelasi Pearson bergulir untuk ${viewLabels[view].toLowerCase()}, jendela ${windowMinutes} menit, dan batas gap ${gapSeconds} detik. Domain tetap minus satu sampai satu; nilai null memutus garis pada gap besar.`
    : undefined

  function selectWindow(next: RollingWindowMinutes) {
    setWindowMinutes(next)
    if (next !== 30) setGapSeconds(30)
  }

  function selectGap(next: RollingGapSeconds) {
    setGapSeconds(next)
    if (next !== 30) setWindowMinutes(30)
  }

  return (
    <Paper
      component="section"
      aria-labelledby="rolling-correlation-heading"
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
          <Typography id="rolling-correlation-heading" variant="h2" sx={{ flexGrow: 1 }}>
            Korelasi Pearson bergulir
          </Typography>
          <FormControl size="small" sx={{ minWidth: tokens.size.sidebar }}>
            <InputLabel id={viewLabelId}>Populasi</InputLabel>
            <Select
              labelId={viewLabelId}
              label="Populasi"
              value={view}
              onChange={(event) => setView(event.target.value as RelationshipView)}
            >
              {(Object.keys(viewLabels) as RelationshipView[]).map((value) => (
                <MenuItem key={value} value={value}>{viewLabels[value]}</MenuItem>
              ))}
            </Select>
          </FormControl>
          <FormControl size="small" sx={{ minWidth: tokens.size.sidebarCompact * 2 }}>
            <InputLabel id={windowLabelId}>Jendela</InputLabel>
            <Select
              labelId={windowLabelId}
              label="Jendela"
              value={windowMinutes}
              onChange={(event) => selectWindow(Number(event.target.value) as RollingWindowMinutes)}
            >
              {rollingWindowMinutes.map((value) => (
                <MenuItem key={value} value={value}>{value} menit</MenuItem>
              ))}
            </Select>
          </FormControl>
          <FormControl size="small" sx={{ minWidth: tokens.size.sidebarCompact * 2 }}>
            <InputLabel id={gapLabelId}>Batas gap</InputLabel>
            <Select
              labelId={gapLabelId}
              label="Batas gap"
              value={gapSeconds}
              onChange={(event) => selectGap(Number(event.target.value) as RollingGapSeconds)}
            >
              {rollingGapSeconds.map((value) => (
                <MenuItem key={value} value={value}>{value} detik</MenuItem>
              ))}
            </Select>
          </FormControl>
        </Stack>

        {runId === null ? (
          <EmptyState
            title="Pilih run EDA"
            detail="Korelasi bergulir ditampilkan setelah run EDA dipilih."
          />
        ) : section === undefined ? (
          query.isError ? (
            <ApiErrorPanel error={query.error} onRetry={() => void query.refetch()} />
          ) : (
            <PanelSkeleton label="Memuat korelasi Pearson bergulir" />
          )
        ) : section.status === 'not_eligible' ? (
          <EmptyState title="Korelasi bergulir belum memenuhi syarat" detail={formatEdaReasonDetail(section.reason_code, section.detail)} />
        ) : section.status === 'failed' ? (
          <ApiErrorPanel
            error={new ApiError('problem', section.detail)}
            onRetry={() => void query.refetch()}
          />
        ) : data === undefined ? (
          <EmptyState
            title="Kombinasi sensitivitas tidak tersedia"
            detail="Pilih jendela 30 menit untuk sensitivitas gap atau batas gap 30 detik untuk sensitivitas jendela."
          />
        ) : data.status === 'not_eligible' ? (
          <Stack spacing={1}>
            <Typography variant="body2" sx={technicalTextSx}>
              Jendela {windowMinutes} menit · batas gap {gapSeconds} detik
            </Typography>
            <Typography variant="body2" color="text.secondary">
              0 jendela layak dari {data.totalEndpointCount.toLocaleString('id-ID')} endpoint.
            </Typography>
            <EmptyState
              title="Kombinasi rolling belum memenuhi syarat"
              detail="Tidak ada jendela dengan pasangan finite nonkonstan dan cakupan minimum yang diwajibkan."
            />
          </Stack>
        ) : data.rows.length === 0 ? (
          <EmptyState
            title="Tidak ada koefisien rolling"
            detail="Run selesai tanpa titik korelasi bergulir untuk kombinasi ini."
          />
        ) : (
          <>
            <Typography variant="body2" color="text.secondary">
              Jendela bergulir saling tumpang tindih; koefisien bersebelahan bergantung satu sama lain dan bukan observasi independen. Grafik ini deskriptif, bukan bukti kausal, prediksi, atau deteksi anomali.
            </Typography>
            <Typography variant="body2" sx={technicalTextSx}>
              Jendela {windowMinutes} menit · batas gap {gapSeconds} detik
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
              <Stack spacing={0.5}>
                <Typography variant="caption" color="text.secondary">Jendela layak / endpoint</Typography>
                <Typography variant="h3" sx={technicalTextSx}>
                  {data.eligibleWindowCount.toLocaleString('id-ID')} / {data.totalEndpointCount.toLocaleString('id-ID')}
                </Typography>
              </Stack>
              <Stack spacing={0.5}>
                <Typography variant="caption" color="text.secondary">Minimum / median / maksimum</Typography>
                <Typography variant="h3" sx={technicalTextSx}>
                  {formatCoefficient(data.minimum)} / {formatCoefficient(data.median)} / {formatCoefficient(data.maximum)}
                </Typography>
              </Stack>
              <Stack direction="row" spacing={1} useFlexGap sx={{ alignItems: 'center', flexWrap: 'wrap' }}>
                <Chip size="small" color="success" label="Status: layak" />
                <Typography variant="caption" color="text.secondary">{viewLabels[view]}</Typography>
              </Stack>
            </Box>
            <Box
              role="img"
              aria-label="Grafik korelasi Pearson bergulir"
              aria-description={description}
              sx={{ minWidth: 0 }}
            >
              <LineChart
                id="rolling-correlation-chart"
                title="Korelasi Pearson bergulir"
                desc={description}
                disableKeyboardNavigation
                height={tokens.size.control * 7}
                skipAnimation
                sx={{
                  [`& .${lineClasses.line}[data-series="rolling-zero-reference"]`]: {
                    strokeDasharray: `${tokens.spacing.unit} ${tokens.spacing.unit}`,
                  },
                }}
                xAxis={[{
                  id: 'rolling-time-axis',
                  data: data.rows.map((row) => row.x),
                  label: 'Akhir jendela (UTC)',
                  scaleType: 'time',
                }]}
                yAxis={[{
                  id: 'rolling-coefficient-axis',
                  label: 'Pearson',
                  min: coefficientDomain[0],
                  max: coefficientDomain[1],
                  valueFormatter: formatCoefficient,
                }]}
                series={[
                  {
                    id: 'rolling-pearson',
                    data: data.rows.map((row) => row.correlation),
                    label: 'Pearson bergulir',
                    color: colors.temperature,
                    connectNulls: false,
                    curve: 'linear',
                    showMark: false,
                    valueFormatter: formatCoefficient,
                    xAxisId: 'rolling-time-axis',
                    yAxisId: 'rolling-coefficient-axis',
                  },
                  {
                    id: 'rolling-zero-reference',
                    data: data.rows.map(() => 0),
                    label: 'Referensi nol',
                    color: colors.threshold,
                    curve: 'linear',
                    disableHighlight: true,
                    showMark: false,
                    xAxisId: 'rolling-time-axis',
                    yAxisId: 'rolling-coefficient-axis',
                  },
                ]}
              />
            </Box>
            <Button
              size="small"
              aria-label="Lihat data korelasi bergulir"
              onClick={() => setDialogRunId(runId)}
            >
              Lihat data
            </Button>
            <BoundedDataDialog<RollingCorrelationRow>
              open={dialogRunId !== null && dialogRunId === runId}
              title={`Korelasi bergulir — ${viewLabels[view]}, ${windowMinutes} menit, gap ${gapSeconds} detik`}
              rows={data.rows}
              returnedCount={data.rows.length}
              columns={rollingColumns}
              onClose={() => setDialogRunId(null)}
            />
          </>
        )}
      </Stack>
    </Paper>
  )
}
