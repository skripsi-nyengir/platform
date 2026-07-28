import { Box, Button, Chip, Paper, Stack, Typography } from '@mui/material'
import { useTheme } from '@mui/material/styles'
import { LineChart, lineClasses } from '@mui/x-charts/LineChart'
import type { GridColDef } from '@mui/x-data-grid'
import { useState } from 'react'
import { ApiError } from '../../api/errors'
import {
  buildAssociationSummaryData,
  coefficientDomain,
  formatCoefficient,
  type RelationshipStatistic,
} from '../../components/charts/relationshipEdaOptions'
import { getChartColors } from '../../components/charts/muiChartTheme'
import { BoundedDataDialog } from '../../components/data/BoundedDataDialog'
import { ApiErrorPanel } from '../../components/states/ApiErrorPanel'
import { EmptyState } from '../../components/states/EmptyState'
import { PanelSkeleton } from '../../components/states/PanelSkeleton'
import { tokens } from '../../theme/tokens'
import { useEdaSectionQuery } from './queries'
import { formatEdaReasonDetail } from './reasonLabels'

export interface AssociationSummaryPanelProps {
  runId: string | null
}

interface AssociationDialogRow {
  id: string
  statistic: string
  population: string
  coefficient: number
  pairCount: number
  status: string
}

const statisticLabels: Record<RelationshipStatistic, string> = {
  pearson: 'Pearson (linear)',
  spearman: 'Spearman (monotonik)',
}

const technicalTextSx = {
  fontFamily: tokens.font.data,
  fontVariantNumeric: 'tabular-nums',
  overflowWrap: 'anywhere',
} as const

const associationColumns: readonly GridColDef<AssociationDialogRow>[] = [
  { field: 'statistic', headerName: 'Koefisien', flex: 1.5 },
  { field: 'population', headerName: 'Populasi', flex: 1.5 },
  {
    field: 'coefficient',
    headerName: 'Nilai',
    flex: 1,
    valueFormatter: (value: number) => formatCoefficient(value),
  },
  { field: 'pairCount', headerName: 'Jumlah pasangan', flex: 1 },
  { field: 'status', headerName: 'Status', flex: 1 },
]

export function AssociationSummaryPanel({ runId }: AssociationSummaryPanelProps) {
  const [dialogRunId, setDialogRunId] = useState<string | null>(null)
  const query = useEdaSectionQuery(runId, 'relationships')
  const theme = useTheme()
  const colors = getChartColors(theme)
  const section = query.data
  const data = section?.status === 'complete' && section.section === 'relationships'
    ? buildAssociationSummaryData(section.payload)
    : undefined
  const rows: AssociationDialogRow[] = data?.flatMap((item) => [
    {
      id: `${item.id}-raw`,
      statistic: statisticLabels[item.statistic],
      population: 'Pasangan exact mentah',
      coefficient: item.raw,
      pairCount: item.rawPairCount,
      status: 'Layak',
    },
    {
      id: `${item.id}-screened`,
      statistic: statisticLabels[item.statistic],
      population: 'Lolos screening aturan',
      coefficient: item.screened,
      pairCount: item.screenedPairCount,
      status: 'Layak',
    },
  ]) ?? []
  const description = data === undefined
    ? undefined
    : `Perbandingan deskriptif Pearson dan Spearman pada populasi pasangan exact mentah dan pasangan yang lolos screening. Domain koefisien tetap dari minus satu sampai satu; garis nol menunjukkan tidak ada asosiasi bertanda.`

  return (
    <Paper
      component="section"
      aria-labelledby="association-summary-heading"
      variant="outlined"
      sx={{ minWidth: 0, p: 4 }}
    >
      <Stack spacing={2} sx={{ minWidth: 0 }}>
        <Typography id="association-summary-heading" variant="h2">
          Ringkasan asosiasi Suhu–RH
        </Typography>
        {runId === null ? (
          <EmptyState
            title="Pilih run EDA"
            detail="Ringkasan asosiasi ditampilkan setelah run EDA dipilih."
          />
        ) : section === undefined ? (
          query.isError ? (
            <ApiErrorPanel error={query.error} onRetry={() => void query.refetch()} />
          ) : (
            <PanelSkeleton label="Memuat ringkasan asosiasi" />
          )
        ) : section.status === 'not_eligible' ? (
          <EmptyState title="Ringkasan asosiasi belum memenuhi syarat" detail={formatEdaReasonDetail(section.reason_code, section.detail)} />
        ) : section.status === 'failed' ? (
          <ApiErrorPanel
            error={new ApiError('problem', section.detail)}
            onRetry={() => void query.refetch()}
          />
        ) : data === undefined || data.length === 0 ? (
          <EmptyState
            title="Tidak ada koefisien asosiasi"
            detail="Run selesai tanpa koefisien Pearson atau Spearman yang dapat ditampilkan."
          />
        ) : (
          <>
            <Typography variant="body2" color="text.secondary">
              Pearson mengukur hubungan linear; Spearman mengukur hubungan monotonik berbasis peringkat. Keduanya bersifat deskriptif dan tidak menyatakan sebab-akibat.
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Mentah dan screened adalah populasi terpilih yang berbeda, bukan perbandingan akurasi. Perubahan koefisien hanya menggambarkan sensitivitas terhadap screening aturan.
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
              {data.map((item) => (
                <Box component="article" key={item.id} sx={{ backgroundColor: theme.palette.background.default, minWidth: 0, p: 2 }}>
                  <Stack spacing={1}>
                    <Stack direction="row" spacing={1} useFlexGap sx={{ alignItems: 'center', flexWrap: 'wrap' }}>
                      <Typography variant="subtitle2">{statisticLabels[item.statistic]}</Typography>
                      <Chip size="small" color="success" label="Status: layak" />
                    </Stack>
                    <Typography variant="body2" sx={technicalTextSx}>
                      Mentah {formatCoefficient(item.raw)} · {item.rawPairCount.toLocaleString('id-ID')} pasangan
                    </Typography>
                    <Typography variant="body2" sx={technicalTextSx}>
                      Screened {formatCoefficient(item.screened)} · {item.screenedPairCount.toLocaleString('id-ID')} pasangan
                    </Typography>
                  </Stack>
                </Box>
              ))}
            </Box>
            <Box
              role="img"
              aria-label="Grafik perbandingan asosiasi mentah dan screened"
              aria-description={description}
              sx={{ minWidth: 0 }}
            >
              <LineChart
                id="association-summary-chart"
                title="Perbandingan koefisien mentah dan screened"
                desc={description}
                disableKeyboardNavigation
                height={tokens.size.control * 7}
                margin={{ right: tokens.spacing.unit * 8 }}
                skipAnimation
                sx={{
                  [`& .${lineClasses.line}[data-series="association-zero-reference"]`]: {
                    strokeDasharray: `${tokens.spacing.unit} ${tokens.spacing.unit}`,
                  },
                }}
                xAxis={[{
                  id: 'association-population-axis',
                  data: ['Mentah', 'Screened'],
                  scaleType: 'point',
                }]}
                yAxis={[{
                  id: 'association-coefficient-axis',
                  label: 'Koefisien asosiasi',
                  min: coefficientDomain[0],
                  max: coefficientDomain[1],
                  valueFormatter: formatCoefficient,
                }]}
                series={[
                  {
                    id: 'association-pearson',
                    data: [data[0]!.raw, data[0]!.screened],
                    label: 'Pearson (linear)',
                    color: colors.temperature,
                    curve: 'linear',
                    showMark: true,
                    xAxisId: 'association-population-axis',
                    yAxisId: 'association-coefficient-axis',
                  },
                  {
                    id: 'association-spearman',
                    data: [data[1]!.raw, data[1]!.screened],
                    label: 'Spearman (monotonik)',
                    color: colors.humidity,
                    curve: 'linear',
                    showMark: true,
                    xAxisId: 'association-population-axis',
                    yAxisId: 'association-coefficient-axis',
                  },
                  {
                    id: 'association-zero-reference',
                    data: [0, 0],
                    label: 'Referensi nol',
                    color: colors.threshold,
                    curve: 'linear',
                    disableHighlight: true,
                    showMark: false,
                    xAxisId: 'association-population-axis',
                    yAxisId: 'association-coefficient-axis',
                  },
                ]}
              />
            </Box>
            <Button
              size="small"
              aria-label="Lihat data ringkasan asosiasi"
              onClick={() => setDialogRunId(runId)}
            >
              Lihat data
            </Button>
            <BoundedDataDialog<AssociationDialogRow>
              open={dialogRunId !== null && dialogRunId === runId}
              title="Data ringkasan asosiasi Suhu–RH"
              rows={rows}
              returnedCount={rows.length}
              columns={associationColumns}
              onClose={() => setDialogRunId(null)}
            />
          </>
        )}
      </Stack>
    </Paper>
  )
}
