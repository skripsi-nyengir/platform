import {
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
import { alpha, darken, useTheme } from '@mui/material/styles'
import { LineChart, lineClasses } from '@mui/x-charts/LineChart'
import type { GridColDef } from '@mui/x-data-grid'
import { useState } from 'react'
import {
  buildConfusionMatrixChartData,
  buildPrecisionRecallChartData,
  buildRocChartData,
} from '../../components/charts/evaluationOptions'
import { BoundedDataDialog } from '../../components/data/BoundedDataDialog'
import type { ModelEvaluationDetail } from '../../contracts/modelEvaluation'
import { tokens } from '../../theme/tokens'

export interface LabeledMetricsPanelsProps {
  artifact: ModelEvaluationDetail
}

const panelHeight = 320
const maximumMatrixDarkening = 0.85
const matrixDarkeningRange = 0.6

const technicalTextSx = {
  fontFamily: tokens.font.data,
  fontVariantNumeric: 'tabular-nums',
} as const

interface ConfusionMatrixRow {
  id: string
  actualClass: string
  predictedClass: string
  count: number
}

interface RocRow {
  id: string
  falsePositiveRate: number
  truePositiveRate: number
}

interface PrecisionRecallRow {
  id: string
  recall: number
  precision: number
}

const confusionMatrixColumns: readonly GridColDef<ConfusionMatrixRow>[] = [
  { field: 'actualClass', headerName: 'Actual class', flex: 1 },
  { field: 'predictedClass', headerName: 'Predicted class', flex: 1 },
  { field: 'count', headerName: 'Count', flex: 1 },
]

const rocColumns: readonly GridColDef<RocRow>[] = [
  { field: 'falsePositiveRate', headerName: 'False positive rate', flex: 1 },
  { field: 'truePositiveRate', headerName: 'True positive rate', flex: 1 },
]

const precisionRecallColumns: readonly GridColDef<PrecisionRecallRow>[] = [
  { field: 'recall', headerName: 'Recall', flex: 1 },
  { field: 'precision', headerName: 'Precision', flex: 1 },
]

export function LabeledMetricsPanels({ artifact }: LabeledMetricsPanelsProps) {
  const [openDialog, setOpenDialog] = useState<
    'confusion_matrix' | 'roc' | 'precision_recall' | undefined
  >()
  const theme = useTheme()

  if (!artifact.has_labeled_ground_truth) return null

  const confusionMatrixData =
    artifact.confusion_matrix === undefined
      ? undefined
      : buildConfusionMatrixChartData(artifact.confusion_matrix)
  const rocData = artifact.roc === undefined ? undefined : buildRocChartData(artifact.roc)
  const precisionRecallData =
    artifact.precision_recall === undefined
      ? undefined
      : buildPrecisionRecallChartData(artifact.precision_recall)
  const confusionMatrixRows: ConfusionMatrixRow[] =
    confusionMatrixData === undefined
      ? []
      : confusionMatrixData.rows.flatMap((row, actualIndex) =>
          row.counts.map((count, predictedIndex) => ({
            id: `confusion-${actualIndex}-${predictedIndex}`,
            actualClass: row.actual,
            predictedClass: confusionMatrixData.xLabels[predictedIndex] ?? '',
            count,
          })),
        )
  const rocRows: RocRow[] =
    rocData === undefined
      ? []
      : rocData.map((point, index) => ({
          id: `roc-${index}`,
          falsePositiveRate: point.x,
          truePositiveRate: point.y,
        }))
  const precisionRecallRows: PrecisionRecallRow[] =
    precisionRecallData === undefined
      ? []
      : precisionRecallData.map((point, index) => ({
          id: `precision-recall-${index}`,
          recall: point.x,
          precision: point.y,
        }))

  return (
    <Box
      role="group"
      aria-label="Labeled evaluation charts"
      sx={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(min(420px, 100%), 1fr))',
        gap: 4,
        alignItems: 'stretch',
        minWidth: 0,
      }}
    >
      {confusionMatrixData !== undefined &&
      artifact.available_metrics.includes('confusion_matrix') ? (
        <Paper
          component="article"
          aria-label="Confusion matrix"
          variant="outlined"
          sx={{ display: 'flex', minWidth: 0, p: 4 }}
        >
          <Stack spacing={2} sx={{ flex: 1, minWidth: 0 }}>
            <Typography variant="h3">Confusion matrix</Typography>
            <TableContainer
              sx={{
                alignItems: 'center',
                display: 'flex',
                height: panelHeight,
                minWidth: 0,
                overflow: 'auto',
              }}
            >
              <Table size="small" aria-label="Confusion matrix">
                <TableHead>
                  <TableRow>
                    <TableCell align="center" rowSpan={2} scope="col">
                      Actual
                    </TableCell>
                    <TableCell
                      align="center"
                      colSpan={confusionMatrixData.xLabels.length}
                      scope="colgroup"
                    >
                      Predicted
                    </TableCell>
                  </TableRow>
                  <TableRow>
                    {confusionMatrixData.xLabels.map((label) => (
                      <TableCell key={label} align="center" scope="col">
                        {label}
                      </TableCell>
                    ))}
                  </TableRow>
                </TableHead>
                <TableBody>
                  {confusionMatrixData.rows.map((row) => (
                    <TableRow key={row.actual}>
                      <TableCell component="th" scope="row" sx={{ whiteSpace: 'nowrap' }}>
                        {row.actual}
                      </TableCell>
                      {row.counts.map((count, predictedIndex) => {
                        const intensity = count / confusionMatrixData.maxCount
                        const backgroundColor = darken(
                          theme.palette.primary.main,
                          maximumMatrixDarkening - intensity * matrixDarkeningRange,
                        )
                        const predictedLabel =
                          confusionMatrixData.xLabels[predictedIndex] ?? ''

                        return (
                          <TableCell
                            key={`${row.actual}-${predictedLabel}`}
                            align="center"
                            aria-label={`Actual ${row.actual}, predicted ${predictedLabel}: ${count}`}
                            sx={{
                              backgroundColor,
                              color: theme.palette.getContrastText(backgroundColor),
                              ...technicalTextSx,
                            }}
                          >
                            {count}
                          </TableCell>
                        )
                      })}
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
            <Button
              size="small"
              aria-label="Lihat data Confusion matrix"
              onClick={() => setOpenDialog('confusion_matrix')}
              sx={{ mt: 'auto' }}
            >
              Lihat data
            </Button>
            <BoundedDataDialog<ConfusionMatrixRow>
              open={openDialog === 'confusion_matrix'}
              title="Confusion matrix data"
              rows={confusionMatrixRows}
              returnedCount={confusionMatrixRows.length}
              columns={confusionMatrixColumns}
              onClose={() => setOpenDialog(undefined)}
            />
          </Stack>
        </Paper>
      ) : null}
      {artifact.roc !== undefined &&
      rocData !== undefined &&
      artifact.available_metrics.includes('roc') ? (
        <Paper
          component="article"
          aria-label="ROC curve"
          variant="outlined"
          sx={{ display: 'flex', minWidth: 0, p: 4 }}
        >
          <Stack spacing={2} sx={{ flex: 1, minWidth: 0 }}>
            <Typography variant="h3">ROC curve</Typography>
            <Typography variant="body2" color="text.secondary" sx={technicalTextSx}>
              AUC: {artifact.roc.auc}
            </Typography>
            <Box
              role="img"
              aria-label="ROC curve"
              aria-description={`ROC curve with AUC ${artifact.roc.auc}.`}
            >
               <LineChart
                 id="roc-curve-chart"
                 title="ROC curve"
                 desc={`ROC curve with AUC ${artifact.roc.auc}.`}
                 disableKeyboardNavigation
                 height={panelHeight}
                 hideLegend
                 skipAnimation
                 sx={{
                   [`& .${lineClasses.line}[data-series="roc-reference-series"]`]: {
                     strokeDasharray: '5 5',
                   },
                 }}
                 xAxis={[
                  {
                    id: 'roc-x-axis',
                    data: rocData.map((point) => point.x),
                    label: 'False positive rate',
                    scaleType: 'linear',
                    min: 0,
                    max: 1,
                  },
                ]}
                yAxis={[
                  {
                    id: 'roc-y-axis',
                    label: 'True positive rate',
                    scaleType: 'linear',
                    min: 0,
                    max: 1,
                  },
                ]}
                series={[
                  {
                    id: 'roc-series',
                    data: rocData.map((point) => point.y),
                    label: 'ROC',
                    color: theme.palette.primary.main,
                    curve: 'linear',
                    showMark: false,
                    xAxisId: 'roc-x-axis',
                    yAxisId: 'roc-y-axis',
                  },
                  {
                    id: 'roc-reference-series',
                    data: rocData.map((point) => point.x),
                    label: 'Reference diagonal',
                    color: alpha(theme.palette.text.secondary, 0.72),
                    curve: 'linear',
                    disableHighlight: true,
                    showMark: false,
                    xAxisId: 'roc-x-axis',
                    yAxisId: 'roc-y-axis',
                  },
                ]}
              />
            </Box>
            <Button
              size="small"
              aria-label="Lihat data ROC curve"
              onClick={() => setOpenDialog('roc')}
              sx={{ mt: 'auto' }}
            >
              Lihat data
            </Button>
            <BoundedDataDialog<RocRow>
              open={openDialog === 'roc'}
              title={`ROC curve data; AUC ${artifact.roc.auc}`}
              rows={rocRows}
              returnedCount={rocRows.length}
              columns={rocColumns}
              onClose={() => setOpenDialog(undefined)}
            />
          </Stack>
        </Paper>
      ) : null}
      {artifact.precision_recall !== undefined &&
      precisionRecallData !== undefined &&
      artifact.available_metrics.includes('precision_recall') ? (
        <Paper
          component="article"
          aria-label="Precision recall curve"
          variant="outlined"
          sx={{ display: 'flex', minWidth: 0, p: 4 }}
        >
          <Stack spacing={2} sx={{ flex: 1, minWidth: 0 }}>
            <Typography variant="h3">Precision recall curve</Typography>
            <Typography variant="body2" color="text.secondary" sx={technicalTextSx}>
              Average precision: {artifact.precision_recall.average_precision}
            </Typography>
            <Box
              role="img"
              aria-label="Precision-recall curve"
              aria-description={`Precision-recall curve with average precision ${artifact.precision_recall.average_precision}.`}
            >
               <LineChart
                 id="precision-recall-curve-chart"
                 title="Precision-recall curve"
                 desc={`Precision-recall curve with average precision ${artifact.precision_recall.average_precision}.`}
                 disableKeyboardNavigation
                 height={panelHeight}
                hideLegend
                skipAnimation
                xAxis={[
                  {
                    id: 'precision-recall-x-axis',
                    data: precisionRecallData.map((point) => point.x),
                    label: 'Recall',
                    scaleType: 'linear',
                    min: 0,
                    max: 1,
                  },
                ]}
                yAxis={[
                  {
                    id: 'precision-recall-y-axis',
                    label: 'Precision',
                    scaleType: 'linear',
                    min: 0,
                    max: 1,
                  },
                ]}
                series={[
                  {
                    id: 'precision-recall-series',
                    data: precisionRecallData.map((point) => point.y),
                    label: 'Precision-recall',
                    color: theme.palette.primary.main,
                    curve: 'linear',
                    showMark: false,
                    xAxisId: 'precision-recall-x-axis',
                    yAxisId: 'precision-recall-y-axis',
                  },
                ]}
              />
            </Box>
            <Button
              size="small"
              aria-label="Lihat data Precision recall curve"
              onClick={() => setOpenDialog('precision_recall')}
              sx={{ mt: 'auto' }}
            >
              Lihat data
            </Button>
            <BoundedDataDialog<PrecisionRecallRow>
              open={openDialog === 'precision_recall'}
              title={`Precision recall curve data; average precision ${artifact.precision_recall.average_precision}`}
              rows={precisionRecallRows}
              returnedCount={precisionRecallRows.length}
              columns={precisionRecallColumns}
              onClose={() => setOpenDialog(undefined)}
            />
          </Stack>
        </Paper>
      ) : null}
    </Box>
  )
}
