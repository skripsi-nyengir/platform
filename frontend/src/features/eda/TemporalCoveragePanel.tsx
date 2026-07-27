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
import { LineChart } from '@mui/x-charts/LineChart'
import type { GridColDef } from '@mui/x-data-grid'
import { useId, useState } from 'react'
import { ApiError } from '../../api/errors'
import {
  buildTemporalCoverageData,
  coverageThresholds,
  formatTemporalPercent,
  temporalResolutions,
  type TemporalCoverageRow,
  type TemporalResolution,
} from '../../components/charts/temporalEdaOptions'
import { getChartColors } from '../../components/charts/muiChartTheme'
import { BoundedDataDialog } from '../../components/data/BoundedDataDialog'
import { ApiErrorPanel } from '../../components/states/ApiErrorPanel'
import { EmptyState } from '../../components/states/EmptyState'
import { PanelSkeleton } from '../../components/states/PanelSkeleton'
import { tokens } from '../../theme/tokens'
import { useEdaSectionQuery } from './queries'
import { formatEdaReasonDetail } from './reasonLabels'

export interface TemporalCoveragePanelProps {
  runId: string | null
}

const resolutionLabels: Record<TemporalResolution, string> = {
  hourly: 'Per jam',
  daily: 'Harian',
  monthly: 'Bulanan',
}

const technicalTextSx = {
  fontFamily: tokens.font.data,
  fontVariantNumeric: 'tabular-nums',
  overflowWrap: 'anywhere',
} as const

const coverageColumns: readonly GridColDef<TemporalCoverageRow>[] = [
  { field: 'start', headerName: 'Mulai (Asia/Jakarta)', flex: 2 },
  { field: 'end', headerName: 'Selesai (Asia/Jakarta)', flex: 2 },
  { field: 'exactPairCount', headerName: 'Pasangan exact', flex: 1 },
  { field: 'screenedPairCount', headerName: 'Lolos screening', flex: 1 },
  { field: 'expectedSlots', headerName: 'Slot harapan', flex: 1 },
  {
    field: 'coverage',
    headerName: 'Cakupan exact',
    flex: 1,
    valueFormatter: (value: number | null) => formatTemporalPercent(value),
  },
  {
    field: 'retention',
    headerName: 'Retensi screening',
    flex: 1,
    valueFormatter: (value: number | null) => formatTemporalPercent(value),
  },
  { field: 'partial', headerName: 'Parsial', type: 'boolean', flex: 1 },
  { field: 'fromCensored', headerName: 'Tersensor awal', type: 'boolean', flex: 1 },
  { field: 'toCensored', headerName: 'Tersensor akhir', type: 'boolean', flex: 1 },
]

export function TemporalCoveragePanel({ runId }: TemporalCoveragePanelProps) {
  const resolutionLabelId = useId()
  const [resolution, setResolution] = useState<TemporalResolution>('monthly')
  const [dialogRunId, setDialogRunId] = useState<string | null>(null)
  const query = useEdaSectionQuery(runId, 'temporal_coverage')
  const theme = useTheme()
  const colors = getChartColors(theme)
  const section = query.data
  const data = section?.status === 'complete' && section.section === 'temporal_coverage'
    ? buildTemporalCoverageData(section.payload, resolution)
    : undefined
  const chartDescription = data === undefined
    ? undefined
    : `Cakupan pasangan exact tanpa batas atas dan retensi setelah screening untuk ${data.rows.length} bin ${resolutionLabels[resolution].toLowerCase()}. Bin nol tetap ditampilkan; penanda menunjukkan bin parsial dan tersensor.`

  return (
    <Paper
      component="section"
      aria-labelledby="temporal-coverage-heading"
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
          <Typography id="temporal-coverage-heading" variant="h2" sx={{ flexGrow: 1 }}>
            Cakupan kalender temporal
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
        </Stack>

        {runId === null ? (
          <EmptyState
            title="Pilih run EDA"
            detail="Cakupan kalender ditampilkan setelah run EDA dipilih."
          />
        ) : section === undefined ? (
          query.isError ? (
            <ApiErrorPanel error={query.error} onRetry={() => void query.refetch()} />
          ) : (
            <PanelSkeleton label="Memuat cakupan kalender temporal" />
          )
        ) : section.status === 'not_eligible' ? (
          <EmptyState title="Cakupan temporal belum memenuhi syarat" detail={formatEdaReasonDetail(section.reason_code, section.detail)} />
        ) : section.status === 'failed' ? (
          <ApiErrorPanel
            error={new ApiError('problem', section.detail)}
            onRetry={() => void query.refetch()}
          />
        ) : data === undefined || data.rows.length === 0 ? (
          <EmptyState
            title="Tidak ada bin cakupan temporal"
            detail="Run selesai tanpa bin kalender pada resolusi ini."
          />
        ) : (
          <>
            <Typography variant="body2" color="text.secondary">
              Cakupan adalah pasangan exact ÷ slot harapan dan tidak dibatasi 100%. Retensi adalah pasangan yang lolos screening ÷ pasangan exact.
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
                <Typography variant="caption" color="text.secondary">Pasangan exact / slot harapan</Typography>
                <Typography variant="h3" sx={technicalTextSx}>
                  {data.totals.exactPairCount.toLocaleString('id-ID')} / {data.totals.expectedSlots.toLocaleString('id-ID')}
                </Typography>
                <Typography variant="body2" sx={technicalTextSx}>
                  {formatTemporalPercent(data.totals.coverage)} cakupan berbobot
                </Typography>
              </Stack>
              <Stack spacing={0.5}>
                <Typography variant="caption" color="text.secondary">Lolos screening / pasangan exact</Typography>
                <Typography variant="h3" sx={technicalTextSx}>
                  {data.totals.screenedPairCount.toLocaleString('id-ID')} / {data.totals.exactPairCount.toLocaleString('id-ID')}
                </Typography>
                <Typography variant="body2" sx={technicalTextSx}>
                  {formatTemporalPercent(data.totals.retention)} retensi berbobot
                </Typography>
              </Stack>
            </Box>
            <Stack direction="row" spacing={1} useFlexGap sx={{ flexWrap: 'wrap' }}>
              {coverageThresholds.map((threshold) => (
                <Chip
                  key={threshold}
                  size="small"
                  color={data.eligibility[threshold] > 0 ? 'success' : 'default'}
                  label={`≥ ${formatTemporalPercent(Number(threshold))}: ${data.eligibility[threshold]}/${data.rows.length} bin layak`}
                />
              ))}
              {resolution === 'monthly' ? coverageThresholds.flatMap((threshold) => {
                const regimes = data.denseRegimes[threshold]
                return regimes.length === 0 ? [] : [
                  <Chip
                    key={`dense-${threshold}`}
                    size="small"
                    color="info"
                    label={`${regimes.length} rentang padat pada ambang ${formatTemporalPercent(Number(threshold))}`}
                  />,
                ]
              }) : null}
            </Stack>
            <Box
              role="img"
              aria-label={`Grafik cakupan temporal ${resolutionLabels[resolution]}`}
              aria-description={chartDescription}
              sx={{ minWidth: 0 }}
            >
              <LineChart
                id={`temporal-coverage-${resolution}`}
                title={`Cakupan temporal ${resolutionLabels[resolution]}`}
                desc={chartDescription}
                disableKeyboardNavigation
                height={tokens.size.control * 7}
                skipAnimation
                xAxis={[{
                  id: 'temporal-coverage-x',
                  data: data.rows.map((row) => row.x),
                  label: 'Waktu Asia/Jakarta',
                  scaleType: 'time',
                }]}
                yAxis={[{
                  id: 'temporal-coverage-y',
                  label: 'Rasio (%)',
                  valueFormatter: (value: number) => formatTemporalPercent(value),
                }]}
                series={[
                  {
                    id: 'exact-coverage',
                    data: data.coverage,
                    label: 'Cakupan pasangan exact',
                    color: colors.temperature,
                    connectNulls: false,
                    curve: 'linear',
                    showMark: false,
                    valueFormatter: (value: number | null) => formatTemporalPercent(value),
                    xAxisId: 'temporal-coverage-x',
                    yAxisId: 'temporal-coverage-y',
                  },
                  {
                    id: 'screened-retention',
                    data: data.retention,
                    label: 'Retensi screened',
                    color: colors.humidity,
                    connectNulls: false,
                    curve: 'linear',
                    showMark: false,
                    valueFormatter: (value: number | null) => formatTemporalPercent(value),
                    xAxisId: 'temporal-coverage-x',
                    yAxisId: 'temporal-coverage-y',
                  },
                  {
                    id: 'partial-bins',
                    data: data.partialMarkers,
                    label: 'Bin parsial',
                    color: colors.anomalyScore,
                    connectNulls: false,
                    curve: 'linear',
                    shape: 'circle',
                    showMark: true,
                    valueFormatter: (value: number | null) => formatTemporalPercent(value),
                    xAxisId: 'temporal-coverage-x',
                    yAxisId: 'temporal-coverage-y',
                  },
                  {
                    id: 'censored-bins',
                    data: data.censoredMarkers,
                    label: 'Bin tersensor',
                    color: colors.outlier,
                    connectNulls: false,
                    curve: 'linear',
                    shape: 'diamond',
                    showMark: true,
                    valueFormatter: (value: number | null) => formatTemporalPercent(value),
                    xAxisId: 'temporal-coverage-x',
                    yAxisId: 'temporal-coverage-y',
                  },
                ]}
              />
            </Box>
            <Button size="small" onClick={() => setDialogRunId(runId)}>Lihat data</Button>
            <BoundedDataDialog<TemporalCoverageRow>
              open={dialogRunId !== null && dialogRunId === runId}
              title={`Cakupan temporal ${resolutionLabels[resolution]}`}
              rows={data.rows}
              returnedCount={data.rows.length}
              columns={coverageColumns}
              onClose={() => setDialogRunId(null)}
            />
          </>
        )}
      </Stack>
    </Paper>
  )
}
