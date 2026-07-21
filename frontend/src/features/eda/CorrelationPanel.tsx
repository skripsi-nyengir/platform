import { Box, Button, Paper, Stack, Typography } from '@mui/material'
import { useTheme } from '@mui/material/styles'
import {
  ScatterChart,
  ScatterMarker,
  type ScatterMarkerProps,
} from '@mui/x-charts/ScatterChart'
import type { GridColDef } from '@mui/x-data-grid'
import { useState } from 'react'
import { buildScatterChartData } from '../../components/charts/edaOptions'
import { getChartColors } from '../../components/charts/muiChartTheme'
import { BoundedDataDialog } from '../../components/data/BoundedDataDialog'
import { ApiErrorPanel } from '../../components/states/ApiErrorPanel'
import { EmptyState } from '../../components/states/EmptyState'
import { PanelSkeleton } from '../../components/states/PanelSkeleton'
import type { EdaField } from '../../contracts/eda'
import { tokens } from '../../theme/tokens'
import type { UrlFilters } from '../filters/urlFilters'
import { useEdaCorrelationQuery } from './queries'

const technicalTextSx = {
  fontFamily: tokens.font.data,
  fontVariantNumeric: 'tabular-nums',
  overflowWrap: 'anywhere',
} as const

const observationSeriesId = 'scatter-observation-series'
const candidateSeriesId = 'scatter-candidate-series'

function CorrelationMarker(props: ScatterMarkerProps) {
  if (props.seriesId !== candidateSeriesId) return <ScatterMarker {...props} />

  const markerSize = (props.isHighlighted ? 1.2 : 1) * props.size
  return (
    <rect
      x={-markerSize}
      y={-markerSize}
      width={markerSize * 2}
      height={markerSize * 2}
      transform={`translate(${props.x}, ${props.y}) rotate(45)`}
      fill={props.color}
      opacity={props.isFaded ? 0.3 : 1}
      cursor={props.onClick === undefined ? 'unset' : 'pointer'}
      onClick={props.onClick}
    />
  )
}

interface ScatterRow {
  id: string
  timestamp: string
  sensor: string
  x: number
  y: number
  score: number | null
  candidate: string
}

const scatterColumns: readonly GridColDef<ScatterRow>[] = [
  { field: 'timestamp', headerName: 'Timestamp', flex: 2 },
  { field: 'sensor', headerName: 'Sensor', flex: 1 },
  { field: 'x', headerName: 'X', flex: 1 },
  { field: 'y', headerName: 'Y', flex: 1 },
  { field: 'score', headerName: 'Score', flex: 1 },
  { field: 'candidate', headerName: 'Candidate outlier', flex: 1 },
]

export function CorrelationPanel({
  filters,
  sampleSize,
  xField,
  yField,
}: {
  filters: Pick<UrlFilters, 'sensor' | 'from' | 'to'>
  sampleSize: number
  xField: EdaField
  yField: EdaField
}) {
  const [dialogOpen, setDialogOpen] = useState(false)
  const theme = useTheme()
  const query = useEdaCorrelationQuery({
    deviceId: filters.sensor,
    from: filters.from,
    to: filters.to,
    xField,
    yField,
    maxPoints: sampleSize,
  })
  const response = query.data
  const pointCount = response?.points.length ?? 0
  const sampleLabel = response?.sample_count === 1 ? 'sample' : 'samples'
  const chartData = response === undefined ? [] : buildScatterChartData(response)
  const observations = chartData
    .filter((point) => !point.anomalous)
    .map(({ id, x, y }) => ({ id, x, y }))
  const candidates = chartData
    .filter((point) => point.anomalous)
    .map(({ id, x, y }) => ({ id, x, y }))
  const chartColors = getChartColors(theme)
  const chartDescription = response === undefined
    ? undefined
    : `${pointCount} displayed points from ${response.sample_count} total bounded samples. ${candidates.length} candidate outlier${candidates.length === 1 ? '' : 's'} shown as diamond marks; observations use circular marks. ${response.correlation === null ? 'Correlation unavailable.' : `Correlation ${response.correlation}.`}`

  return (
    <Paper
      component="section"
      aria-labelledby="correlation-scatter"
      variant="outlined"
      sx={{ minWidth: 0, p: 4 }}
    >
      <Stack spacing={2} sx={{ minWidth: 0 }}>
        <Typography id="correlation-scatter" variant="h2">Correlation and scatter</Typography>
        {response === undefined ? (
          query.isError ? (
            <ApiErrorPanel error={query.error} onRetry={() => void query.refetch()} />
          ) : (
            <PanelSkeleton label="Loading correlation and scatter" />
          )
        ) : (
          <>
            <Typography variant="body2">
              <Box component="span" sx={technicalTextSx}>{pointCount}</Box> scatter point{pointCount === 1 ? '' : 's'} returned from <Box component="span" sx={technicalTextSx}>{response.sample_count}</Box> bounded {sampleLabel}
            </Typography>
            {response.points.length === 0 ? (
              <EmptyState
                title="No scatter points returned"
                detail="Adjust the selected time range, sensor, or fields."
              />
            ) : (
              <>
                <Typography
                  variant="body2"
                  color="text.secondary"
                >
                  {response.correlation === null
                    ? 'Correlation unavailable for the returned sample.'
                    : <>Correlation coefficient: <Box component="span" sx={technicalTextSx}>{response.correlation}</Box>.</>}
                </Typography>
                <Box
                  role="img"
                  aria-label={`${response.x_field} by ${response.y_field} scatter`}
                  aria-description={chartDescription}
                  sx={{ minWidth: 0 }}
                >
                   <ScatterChart
                     id="correlation-scatter-chart"
                     title={`${response.x_field} by ${response.y_field} scatter`}
                     desc={chartDescription}
                     disableKeyboardNavigation
                     height={tokens.size.control * 7}
                    skipAnimation
                    xAxis={[
                      { id: 'scatter-x-axis', label: response.x_field, scaleType: 'linear' },
                    ]}
                    yAxis={[
                      { id: 'scatter-y-axis', label: response.y_field, scaleType: 'linear' },
                    ]}
                    series={[
                      {
                        id: observationSeriesId,
                        data: observations,
                        label: 'Observations',
                        color: chartColors.normalPoint,
                        xAxisId: 'scatter-x-axis',
                        yAxisId: 'scatter-y-axis',
                      },
                      {
                        id: candidateSeriesId,
                        data: candidates,
                        label: 'Candidate outliers (diamond)',
                        color: chartColors.outlier,
                        xAxisId: 'scatter-x-axis',
                        yAxisId: 'scatter-y-axis',
                      },
                    ]}
                    slots={{ marker: CorrelationMarker }}
                  />
                </Box>
                <Button size="small" onClick={() => setDialogOpen(true)}>Lihat data</Button>
                <BoundedDataDialog<ScatterRow>
                  open={dialogOpen}
                  title={`${response.x_field} by ${response.y_field} scatter data`}
                  rows={response.points.map((point, index) => ({
                    id: `${point.device_id}-${point.ts}-${index}`,
                    timestamp: point.ts,
                    sensor: point.device_id,
                    x: point.x,
                    y: point.y,
                    score: point.score ?? null,
                    candidate: point.is_candidate_outlier ? 'Yes' : 'No',
                  }))}
                  returnedCount={pointCount}
                  columns={scatterColumns}
                  onClose={() => setDialogOpen(false)}
                />
              </>
            )}
          </>
        )}
      </Stack>
    </Paper>
  )
}
