import { Box, Button, Paper, Stack, TextField, Typography } from '@mui/material'
import { useTheme } from '@mui/material/styles'
import { BarChart } from '@mui/x-charts/BarChart'
import type { GridColDef } from '@mui/x-data-grid'
import { useState } from 'react'
import { BoundedDataDialog } from '../../components/data/BoundedDataDialog'
import { buildHistogramChartData } from '../../components/charts/edaOptions'
import { getChartColors } from '../../components/charts/muiChartTheme'
import { ApiErrorPanel } from '../../components/states/ApiErrorPanel'
import { EmptyState } from '../../components/states/EmptyState'
import { PanelSkeleton } from '../../components/states/PanelSkeleton'
import type { EdaField } from '../../contracts/eda'
import { tokens } from '../../theme/tokens'
import type { UrlFilters } from '../filters/urlFilters'
import { useEdaDistributionsQuery } from './queries'

interface HistogramRow {
  id: string
  start: number
  end: number
  count: number
}

const histogramColumns: readonly GridColDef<HistogramRow>[] = [
  { field: 'start', headerName: 'Bin start', flex: 1 },
  { field: 'end', headerName: 'Bin end', flex: 1 },
  { field: 'count', headerName: 'Count', flex: 1 },
]

const labels: Record<EdaField, string> = {
  temperature_c: 'Temperature',
  relative_humidity_pct: 'Relative humidity',
  score: 'Anomaly score',
}

const technicalTextSx = {
  fontFamily: tokens.font.data,
  fontVariantNumeric: 'tabular-nums',
  overflowWrap: 'anywhere',
} as const

function boundedBins(value: string): number | undefined {
  const parsed = Number(value)
  if (!Number.isFinite(parsed)) return undefined
  return Math.min(100, Math.max(5, Math.trunc(parsed)))
}

export function DistributionPanel({
  filters,
}: {
  filters: Pick<UrlFilters, 'sensor' | 'from' | 'to'>
}) {
  const [bins, setBins] = useState(20)
  const [openField, setOpenField] = useState<EdaField>()
  const theme = useTheme()
  const temperature = useEdaDistributionsQuery({
    deviceId: filters.sensor,
    from: filters.from,
    to: filters.to,
    field: 'temperature_c',
    bins,
  })
  const humidity = useEdaDistributionsQuery({
    deviceId: filters.sensor,
    from: filters.from,
    to: filters.to,
    field: 'relative_humidity_pct',
    bins,
  })
  const score = useEdaDistributionsQuery({
    deviceId: filters.sensor,
    from: filters.from,
    to: filters.to,
    field: 'score',
    bins,
  })
  const cards = [
    { field: 'temperature_c', query: temperature },
    { field: 'relative_humidity_pct', query: humidity },
    { field: 'score', query: score },
  ] satisfies readonly { field: EdaField; query: typeof temperature }[]
  const chartColors = getChartColors(theme)
  const histogramColors: Record<EdaField, string> = {
    temperature_c: chartColors.temperature,
    relative_humidity_pct: chartColors.humidity,
    score: chartColors.anomalyScore,
  }

  return (
    <Paper
      component="section"
      aria-labelledby="distributions"
      variant="outlined"
      sx={{ minWidth: 0, p: 4 }}
    >
      <Stack spacing={2} sx={{ minWidth: 0 }}>
        <Stack
          direction="row"
          spacing={2}
          useFlexGap
          sx={{ minWidth: 0, alignItems: 'center', flexWrap: 'wrap' }}
        >
          <Typography id="distributions" variant="h2" sx={{ flexGrow: 1 }}>Distributions</Typography>
          <TextField
            size="small"
            label="Bins"
            type="number"
            value={bins}
            slotProps={{ htmlInput: { min: 5, max: 100 } }}
            onChange={(event) => {
              const nextBins = boundedBins(event.target.value)
              if (nextBins !== undefined) setBins(nextBins)
            }}
          />
        </Stack>
        <Box
          role="group"
          aria-label="Distribution panels"
          sx={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(min(320px, 100%), 1fr))',
            gap: 4,
            minWidth: 0,
          }}
        >
          {cards.map(({ field, query }) => {
            const chartData = query.data === undefined
              ? { labels: [], counts: [] }
              : buildHistogramChartData(query.data)
            const chartDescription = query.data === undefined
              ? undefined
              : `${labels[field]} histogram with ${query.data.bins.length} bins in API order using [start, end) labels and ${query.data.sample_count} bounded samples returned.`

            return (
              <Paper
                component="article"
                aria-label={`${labels[field]} distribution`}
                key={field}
                variant="outlined"
                sx={{ minWidth: 0, p: 4 }}
              >
                <Stack spacing={1} useFlexGap sx={{ minWidth: 0, height: '100%' }}>
                  <Typography variant="h3">{labels[field]}</Typography>
                  {query.data === undefined ? (
                    query.isError ? (
                      <ApiErrorPanel error={query.error} onRetry={() => void query.refetch()} />
                    ) : (
                      <PanelSkeleton label={`Loading ${labels[field]} distribution`} />
                    )
                  ) : (
                    <>
                      <Typography variant="body2">
                        <Box component="span" sx={technicalTextSx}>{query.data.sample_count}</Box> bounded samples returned
                      </Typography>
                      {query.data.sample_count === 0 ? (
                        <EmptyState
                          title={`No ${labels[field].toLowerCase()} samples returned`}
                          detail="Adjust the selected range or sensor scope."
                        />
                      ) : (
                        <>
                          <Typography variant="body2" color="text.secondary">
                            Mean <Box component="span" sx={technicalTextSx}>{query.data.summary.mean}</Box>; median <Box component="span" sx={technicalTextSx}>{query.data.summary.median}</Box>; p05–p95 <Box component="span" sx={technicalTextSx}>{query.data.summary.p05}</Box>–<Box component="span" sx={technicalTextSx}>{query.data.summary.p95}</Box>
                          </Typography>
                          <Box
                            role="img"
                            aria-label={`${field} distribution`}
                            aria-description={chartDescription}
                            sx={{ minWidth: 0 }}
                          >
                             <BarChart
                               id={`${field}-histogram-chart`}
                               title={`${labels[field]} distribution`}
                               desc={chartDescription}
                               disableKeyboardNavigation
                               height={tokens.size.control * 6}
                              hideLegend
                              skipAnimation
                              xAxis={[
                                {
                                  id: `${field}-histogram-x-axis`,
                                  data: chartData.labels,
                                  label: 'Bin range',
                                  scaleType: 'band',
                                  categoryGapRatio: 0,
                                  barGapRatio: 0,
                                },
                              ]}
                              yAxis={[{ id: `${field}-histogram-y-axis`, label: 'Count' }]}
                              series={[
                                {
                                  id: `${field}-histogram-count-series`,
                                  data: chartData.counts,
                                  label: 'Count',
                                  color: histogramColors[field],
                                  xAxisId: `${field}-histogram-x-axis`,
                                  yAxisId: `${field}-histogram-y-axis`,
                                },
                              ]}
                            />
                          </Box>
                          <Button
                            size="small"
                            onClick={() => setOpenField(field)}
                            sx={{ mt: 'auto' }}
                          >
                            Lihat data
                          </Button>
                          <BoundedDataDialog<HistogramRow>
                            open={openField === field}
                            title={`${labels[field]} histogram bins`}
                            rows={query.data.bins.map((bin, index) => ({
                              id: `${field}-${index}`,
                              start: bin.start,
                              end: bin.end,
                              count: bin.count,
                            }))}
                            returnedCount={query.data.bins.length}
                            columns={histogramColumns}
                            onClose={() => setOpenField(undefined)}
                          />
                        </>
                      )}
                    </>
                  )}
                </Stack>
              </Paper>
            )
          })}
        </Box>
      </Stack>
    </Paper>
  )
}
