import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
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
import { useMemo, useState } from 'react'
import { getChartColors } from '../components/charts/muiChartTheme'
import { ApiErrorPanel } from '../components/states/ApiErrorPanel'
import { PanelSkeleton } from '../components/states/PanelSkeleton'
import type { ModelRegistryItem } from '../contracts/modelRegistry'
import type {
  OfflineEvaluationContext,
  OfflineEvaluationItem,
  OfflineEvaluationModelFamily,
} from '../contracts/offlineEvaluations'
import {
  useModelRegistryQuery,
  useOfflineEvaluationsQuery,
} from '../features/modelEvaluation/queries'
import { tokens } from '../theme/tokens'

const MODEL_ORDER: readonly OfflineEvaluationModelFamily[] = [
  'conv1d',
  'gru',
  'lstm',
  'rnn',
  'transformer',
]

const MODEL_LABELS: Record<OfflineEvaluationModelFamily, string> = {
  conv1d: 'Conv1D',
  gru: 'GRU',
  lstm: 'LSTM',
  rnn: 'RNN',
  transformer: 'Transformer',
}

const SCOPE_ROWS = [
  {
    key: 'timestamp',
    label: 'Timestamp',
    description: 'Skor rekonstruksi per timestamp',
  },
  {
    key: 'overlapping_model_windows',
    label: 'Overlapping model windows',
    description: 'Window model panjang 10 yang saling overlap',
  },
  {
    key: 'non_overlapping_evaluation_bins',
    label: 'Non-overlapping evaluation bins (utama)',
    description: 'Bin evaluasi 51 titik tanpa overlap',
  },
] as const

const technicalTextSx = {
  fontFamily: tokens.font.data,
  fontVariantNumeric: 'tabular-nums',
  overflowWrap: 'anywhere',
} as const

const numericTextSx = {
  ...technicalTextSx,
  overflowWrap: 'normal',
  whiteSpace: 'nowrap',
} as const

const registryGridSx = {
  display: 'grid',
  gap: 2,
  gridTemplateColumns: {
    xs: 'minmax(0, 1fr)',
    sm: 'repeat(2, minmax(0, 1fr))',
    lg: 'repeat(5, minmax(0, 1fr))',
  },
  minWidth: 0,
  '& > *': { minWidth: 0 },
} as const

const detailGridSx = {
  ...registryGridSx,
  gridTemplateColumns: {
    xs: 'minmax(0, 1fr)',
    sm: 'repeat(2, minmax(0, 1fr))',
    lg: 'repeat(4, minmax(0, 1fr))',
  },
} as const

function formatArchitecture(architecture: Readonly<Record<string, unknown>>): string {
  return Object.entries(architecture)
    .map(
      ([key, value]) =>
        `${key}: ${typeof value === 'string' ? value : JSON.stringify(value)}`,
    )
    .join(' · ')
}

function summarizeArchitecture(item: ModelRegistryItem): string {
  const architecture = item.architecture

  switch (item.family) {
    case 'conv1d':
      return `${String(architecture.latent_channels)} latent channels`
    case 'gru':
    case 'lstm':
    case 'rnn':
      return `${String(architecture.hidden_size)} hidden · ${String(architecture.latent_size)} latent · ${String(architecture.layers)} layers`
    case 'transformer':
      return `d_model ${String(architecture.d_model)} · ${String(architecture.n_heads)} heads · ${String(architecture.encoder_layers)} + ${String(architecture.decoder_layers)} layers`
  }
}

function formatFractionAsPercent(value: number): string {
  return value.toLocaleString('id-ID', {
    style: 'percent',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
}

function RegistryDetailDialog({
  item,
  onClose,
}: {
  item: ModelRegistryItem | null
  onClose: () => void
}) {
  return (
    <Dialog open={item !== null} onClose={onClose} fullWidth maxWidth="sm">
      {item !== null ? (
        <>
          <DialogTitle>Detail teknis registry · {item.display_name}</DialogTitle>
          <DialogContent>
            <Stack component="dl" spacing={2} sx={{ m: 0, minWidth: 0 }}>
              {[
                ['Dataset', item.dataset_reference],
                ['Window', `${item.window_size} langkah`],
                ['Fitur', item.features.join(', ')],
                ['Model SHA-256', item.model_sha256],
                ['Score semantics', item.score_semantics],
                ['Report source', item.report_source],
                ['Arsitektur lengkap', formatArchitecture(item.architecture)],
              ].map(([label, value]) => (
                <Box key={label} sx={{ minWidth: 0 }}>
                  <Typography component="dt" variant="caption" color="text.secondary">
                    {label}
                  </Typography>
                  <Typography
                    component="dd"
                    variant="body2"
                    sx={{ ...technicalTextSx, m: 0 }}
                  >
                    {value}
                  </Typography>
                </Box>
              ))}
            </Stack>
          </DialogContent>
          <DialogActions>
            <Button onClick={onClose}>Tutup</Button>
          </DialogActions>
        </>
      ) : null}
    </Dialog>
  )
}

function ExactEvaluationDialog({
  items,
  open,
  onClose,
}: {
  items: readonly OfflineEvaluationItem[]
  open: boolean
  onClose: () => void
}) {
  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="lg">
      <DialogTitle>Data eksak evaluasi Step 7</DialogTitle>
      <DialogContent>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          Nilai mentah scope utama non-overlapping evaluation bins dari output notebook
          Step 7. Persentase pada chart adalah nilai pecahan × 100.
        </Typography>
        <TableContainer sx={{ maxWidth: '100%', overflowX: 'auto' }}>
          <Table
            size="small"
            aria-label="Data eksak precision recall F1 dan confusion matrix"
            sx={{ minWidth: 760 }}
          >
            <TableHead>
              <TableRow>
                <TableCell>Model</TableCell>
                <TableCell align="right">Precision</TableCell>
                <TableCell align="right">Recall</TableCell>
                <TableCell align="right">F1</TableCell>
                <TableCell align="right">TN</TableCell>
                <TableCell align="right">FP</TableCell>
                <TableCell align="right">FN</TableCell>
                <TableCell align="right">TP</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {items.map((item) => {
                const metrics = item.scopes.non_overlapping_evaluation_bins
                return (
                  <TableRow key={item.model_family}>
                    <TableCell>{MODEL_LABELS[item.model_family]}</TableCell>
                    {[
                      metrics.precision,
                      metrics.recall,
                      metrics.f1,
                      metrics.tn,
                      metrics.fp,
                      metrics.fn,
                      metrics.tp,
                    ].map((value, index) => (
                      <TableCell key={index} align="right" sx={numericTextSx}>
                        {String(value)}
                      </TableCell>
                    ))}
                  </TableRow>
                )
              })}
            </TableBody>
          </Table>
        </TableContainer>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Tutup</Button>
      </DialogActions>
    </Dialog>
  )
}

function ScopeMetricsTable({ item }: { item: OfflineEvaluationItem }) {
  return (
    <Paper
      component="section"
      aria-labelledby="evaluation-scopes-heading"
      variant="outlined"
      sx={{ p: { xs: 2, sm: 3 }, minWidth: 0 }}
    >
      <Stack spacing={2}>
        <Stack spacing={0.5}>
          <Typography id="evaluation-scopes-heading" variant="h3">
            Tiga scope evaluasi · {MODEL_LABELS[item.model_family]}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Angka berasal dari satu threshold p99.5 yang sama. Scope bin tanpa overlap
            menjadi dasar chart utama.
          </Typography>
        </Stack>
        <TableContainer sx={{ maxWidth: '100%', overflowX: 'auto' }}>
          <Table
            size="small"
            aria-label={`Metrik tiga scope ${MODEL_LABELS[item.model_family]}`}
            sx={{ minWidth: 1_040 }}
          >
            <TableHead>
              <TableRow>
                <TableCell>Scope</TableCell>
                <TableCell align="right">n</TableCell>
                <TableCell align="right">Accuracy</TableCell>
                <TableCell align="right">Precision</TableCell>
                <TableCell align="right">Recall</TableCell>
                <TableCell align="right">F1</TableCell>
                <TableCell align="right">TN</TableCell>
                <TableCell align="right">FP</TableCell>
                <TableCell align="right">FN</TableCell>
                <TableCell align="right">TP</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {SCOPE_ROWS.map((scope) => {
                const metrics = item.scopes[scope.key]
                return (
                  <TableRow key={scope.key}>
                    <TableCell sx={{ minWidth: 220 }}>
                      <Typography variant="body2" sx={{ fontWeight: 700 }}>
                        {scope.label}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        {scope.description}
                      </Typography>
                    </TableCell>
                    <TableCell align="right" sx={numericTextSx}>
                      {metrics.n_evaluated.toLocaleString('id-ID')}
                    </TableCell>
                    {[metrics.accuracy, metrics.precision, metrics.recall, metrics.f1].map(
                      (value, index) => (
                        <TableCell key={index} align="right" sx={numericTextSx}>
                          {formatFractionAsPercent(value)}
                        </TableCell>
                      ),
                    )}
                    {[metrics.tn, metrics.fp, metrics.fn, metrics.tp].map((value, index) => (
                      <TableCell key={index} align="right" sx={numericTextSx}>
                        {value.toLocaleString('id-ID')}
                      </TableCell>
                    ))}
                  </TableRow>
                )
              })}
            </TableBody>
          </Table>
        </TableContainer>
      </Stack>
    </Paper>
  )
}

function TechnicalEvaluationDetails({
  item,
  evaluation,
}: {
  item: OfflineEvaluationItem
  evaluation: OfflineEvaluationContext
}) {
  const facts = [
    ['Threshold', String(item.threshold.value)],
    [
      'Threshold policy',
      `clean validation p${item.threshold.percentile} · ${item.threshold.comparison} · tanpa label anomali`,
    ],
    ['Dataset evaluasi', evaluation.dataset_reference],
    ['Split evaluasi', evaluation.evaluation_split],
    ['Final test set', evaluation.test_consumed ? 'Digunakan' : 'Tidak digunakan'],
    ['Scope utama', evaluation.primary_scope],
    ['Metrik utama', evaluation.primary_metric],
    ['Titik total', evaluation.n_points_total.toLocaleString('id-ID')],
    ['Titik dievaluasi', evaluation.n_points_evaluated.toLocaleString('id-ID')],
    ['Model windows', evaluation.n_model_windows.toLocaleString('id-ID')],
    ['Window positif', evaluation.n_positive_windows.toLocaleString('id-ID')],
    ['Event', evaluation.n_events.toLocaleString('id-ID')],
    ['Ukuran bin evaluasi', `${evaluation.evaluation_bin_size_points} titik`],
    ['Bin dievaluasi', evaluation.n_evaluation_bins.toLocaleString('id-ID')],
    ['Bin dilewati', evaluation.n_skipped_bins.toLocaleString('id-ID')],
    ['Model SHA-256', item.model_sha256],
    ['Score semantics', 'window_mean_squared_reconstruction_error pada unit timestamp'],
    ['Metric authority', item.provenance.metric_authority],
    ['Notebook Step 5', item.provenance.step5_notebook.filename],
    ['SHA-256 Step 5', item.provenance.step5_notebook.sha256],
    ['Notebook Step 7', item.provenance.step7_notebook.filename],
    ['SHA-256 Step 7', item.provenance.step7_notebook.sha256],
  ] as const

  return (
    <Accordion
      disableGutters
      variant="outlined"
      slots={{ heading: 'div' }}
      sx={{
        minWidth: 0,
        '&::before': { display: 'none' },
        '&.Mui-expanded': { m: 0 },
      }}
    >
      <AccordionSummary
        aria-controls="offline-technical-details"
        id="offline-technical-summary"
        sx={{
          minHeight: tokens.size.control,
          '&.Mui-expanded': { minHeight: tokens.size.control },
        }}
      >
        <Typography sx={{ fontWeight: 700 }}>
          Detail teknis evaluasi {MODEL_LABELS[item.model_family]}
        </Typography>
      </AccordionSummary>
      <AccordionDetails id="offline-technical-details">
        <Stack spacing={3}>
          <Box component="dl" sx={{ ...detailGridSx, m: 0 }}>
            {facts.map(([label, value]) => (
              <Box key={label} sx={{ minWidth: 0 }}>
                <Typography component="dt" variant="caption" color="text.secondary">
                  {label}
                </Typography>
                <Typography
                  component="dd"
                  variant="body2"
                  sx={{ ...technicalTextSx, m: 0 }}
                >
                  {value}
                </Typography>
              </Box>
            ))}
          </Box>

          <Stack spacing={1}>
            <Typography variant="h4">Pemeriksaan artefak ZIP</Typography>
            {item.provenance.artifact_checks.length === 0 ? (
              <Typography variant="body2" color="text.secondary">
                Tidak ada arsip tambahan yang diberikan untuk model ini.
              </Typography>
            ) : (
              item.provenance.artifact_checks.map((check) => (
                <Paper
                  key={`${check.filename}-${check.role}`}
                  variant="outlined"
                  sx={{ p: 2, minWidth: 0 }}
                >
                  <Stack spacing={0.5}>
                    <Typography variant="body2" sx={{ fontWeight: 700 }}>
                      {check.consistency === 'conflict' ? 'Konflik dikarantina' : 'Cocok'} ·{' '}
                      {check.filename}
                    </Typography>
                    <Typography variant="caption" sx={technicalTextSx}>
                      {check.sha256}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      {check.note}
                    </Typography>
                  </Stack>
                </Paper>
              ))
            )}
          </Stack>
        </Stack>
      </AccordionDetails>
    </Accordion>
  )
}

export function ModelEvaluationPage() {
  const theme = useTheme()
  const chartColors = getChartColors(theme)
  const registry = useModelRegistryQuery()
  const offlineEvaluations = useOfflineEvaluationsQuery()
  const [registryDetail, setRegistryDetail] = useState<ModelRegistryItem | null>(null)
  const [selectedFamily, setSelectedFamily] =
    useState<OfflineEvaluationModelFamily>('conv1d')
  const [exactDataOpen, setExactDataOpen] = useState(false)
  const orderedEvaluations = useMemo(
    () =>
      MODEL_ORDER.flatMap(
        (family) =>
          offlineEvaluations.data?.items.filter(
            (item) => item.model_family === family,
          ) ?? [],
      ),
    [offlineEvaluations.data],
  )
  const selectedEvaluation = orderedEvaluations.find(
    (item) => item.model_family === selectedFamily,
  )

  return (
    <Stack spacing={6} sx={{ minWidth: 0 }}>
      <Stack spacing={0.5}>
        <Typography variant="h1">Model Evaluation</Typography>
        <Typography color="text.secondary">
          Bandingkan bukti training dengan evaluasi Step 7 berlabel tanpa mencampur
          provenance atau mengklaim hasil inferensi live.
        </Typography>
      </Stack>

      <Stack
        component="section"
        aria-labelledby="reported-registry-heading"
        spacing={2}
        sx={{ minWidth: 0 }}
      >
        <Stack spacing={0.5}>
          <Typography
            id="reported-registry-heading"
            variant="h2"
            sx={{ textWrap: 'balance' }}
          >
            Model terdaftar (metrik dilaporkan dari training)
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Registry melaporkan best validation MSE dari proses training; bukan hasil
            evaluasi Step 7.
          </Typography>
        </Stack>
        {registry.data === undefined ? (
          registry.isError ? (
            <ApiErrorPanel error={registry.error} onRetry={() => void registry.refetch()} />
          ) : (
            <PanelSkeleton label="Loading reported model registry" />
          )
        ) : (
          <Box data-testid="model-registry-grid" sx={registryGridSx}>
            {registry.data.items.map((item) => (
              <Paper
                component="article"
                variant="outlined"
                key={item.id}
                sx={{ p: 3, minWidth: 0 }}
              >
                <Stack spacing={2} sx={{ height: '100%', minWidth: 0 }}>
                  <Stack spacing={0.5}>
                    <Typography variant="h3">{item.display_name}</Typography>
                    <Typography variant="body2" color="primary.main" sx={technicalTextSx}>
                      {item.family}
                    </Typography>
                  </Stack>
                  <Typography variant="body2" color="text.secondary">
                    {item.summary}
                  </Typography>
                  <Box
                    component="dl"
                    sx={{ display: 'grid', gap: 1.5, m: 0, minWidth: 0 }}
                  >
                    {[
                      ['Best val MSE', String(item.best_val_mse)],
                      ['Parameter', item.param_count.toLocaleString('id-ID')],
                      ['Epoch', String(item.best_epoch)],
                      ['Ringkasan arsitektur', summarizeArchitecture(item)],
                    ].map(([label, value]) => (
                      <Box key={label} sx={{ minWidth: 0 }}>
                        <Typography component="dt" variant="caption" color="text.secondary">
                          {label}
                        </Typography>
                        <Typography
                          component="dd"
                          variant="body2"
                          sx={{ ...technicalTextSx, m: 0 }}
                        >
                          {value}
                        </Typography>
                      </Box>
                    ))}
                  </Box>
                  <Button
                    aria-label={`Detail teknis ${item.display_name}`}
                    variant="outlined"
                    sx={{ mt: 'auto', minHeight: tokens.size.control }}
                    onClick={() => setRegistryDetail(item)}
                  >
                    Detail teknis
                  </Button>
                </Stack>
              </Paper>
            ))}
          </Box>
        )}
      </Stack>

      <Stack
        component="section"
        aria-labelledby="offline-evaluations-heading"
        spacing={3}
        sx={{ minWidth: 0 }}
      >
        <Stack spacing={0.5}>
          <Typography
            id="offline-evaluations-heading"
            variant="h2"
            sx={{ textWrap: 'balance' }}
          >
            Evaluasi Step 7 (validation-injected berlabel)
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Output notebook Step 7 pada split val_injected. Threshold p99.5 dikalibrasi
            dari clean validation tanpa label anomali; final test set tidak dikonsumsi.
          </Typography>
        </Stack>
        {offlineEvaluations.data === undefined ? (
          offlineEvaluations.isError ? (
            <ApiErrorPanel
              error={offlineEvaluations.error}
              onRetry={() => void offlineEvaluations.refetch()}
            />
          ) : (
            <PanelSkeleton label="Loading Step 7 evaluations" />
          )
        ) : (
          <Stack spacing={3} sx={{ minWidth: 0 }}>
            <Paper
              variant="outlined"
              sx={{ p: { xs: 2, sm: 3 }, minWidth: 0, overflow: 'hidden' }}
            >
              <Stack spacing={2} sx={{ minWidth: 0 }}>
                <Stack
                  direction={{ xs: 'column', sm: 'row' }}
                  spacing={2}
                  sx={{
                    justifyContent: 'space-between',
                    alignItems: { sm: 'center' },
                  }}
                >
                  <Stack spacing={0.5}>
                    <Typography variant="h3">
                      Precision, recall, dan F1 · non-overlapping evaluation bins
                    </Typography>
                    <Typography
                      id="offline-chart-description"
                      variant="body2"
                      color="text.secondary"
                    >
                      Scope utama output Step 7, dalam urutan Conv1D, GRU, LSTM, RNN,
                      Transformer, dengan skala tetap 0–100% dari baseline nol.
                    </Typography>
                  </Stack>
                  <Button
                    variant="outlined"
                    onClick={() => setExactDataOpen(true)}
                    sx={{ minHeight: tokens.size.control, flexShrink: 0 }}
                  >
                    Lihat data eksak
                  </Button>
                </Stack>
                <Box
                  role="img"
                  aria-label="Perbandingan precision recall dan F1 lima model pada bin evaluasi"
                  aria-describedby="offline-chart-description"
                  sx={{ width: '100%', minWidth: 0, overflow: 'hidden' }}
                >
                  <BarChart
                    id="offline-model-comparison-chart"
                    title="Perbandingan metrik evaluasi Step 7"
                    desc="Precision, recall, dan F1 scope non-overlapping evaluation bins untuk lima model pada domain nol sampai seratus persen."
                    layout="horizontal"
                    height={360}
                    margin={{ left: 8, right: 16 }}
                    skipAnimation
                    xAxis={[
                      { id: 'percent-axis', min: 0, max: 100, label: 'Persen' },
                    ]}
                    yAxis={[
                      {
                        id: 'model-axis',
                        data: orderedEvaluations.map(
                          (item) => MODEL_LABELS[item.model_family],
                        ),
                        scaleType: 'band',
                        width: 'auto',
                        tickLabelStyle: { fontFamily: 'sans-serif', fontSize: 12 },
                      },
                    ]}
                    series={[
                      {
                        id: 'precision',
                        label: 'Precision',
                        color: chartColors.temperature,
                        data: orderedEvaluations.map(
                          (item) =>
                            item.scopes.non_overlapping_evaluation_bins.precision * 100,
                        ),
                      },
                      {
                        id: 'recall',
                        label: 'Recall',
                        color: chartColors.humidity,
                        data: orderedEvaluations.map(
                          (item) =>
                            item.scopes.non_overlapping_evaluation_bins.recall * 100,
                        ),
                      },
                      {
                        id: 'f1',
                        label: 'F1',
                        color: chartColors.anomalyScore,
                        data: orderedEvaluations.map(
                          (item) => item.scopes.non_overlapping_evaluation_bins.f1 * 100,
                        ),
                      },
                    ].map((series) => ({
                      ...series,
                      xAxisId: 'percent-axis',
                      yAxisId: 'model-axis',
                      valueFormatter: (value: number | null) =>
                        value === null ? null : `${value.toFixed(2)}%`,
                    }))}
                  />
                </Box>
              </Stack>
            </Paper>

            <Stack spacing={1}>
              <Typography variant="h3">Pilih model untuk rincian Step 7</Typography>
              <Stack direction="row" spacing={1} useFlexGap sx={{ flexWrap: 'wrap' }}>
                {MODEL_ORDER.map((family) => (
                  <Button
                    key={family}
                    aria-pressed={selectedFamily === family}
                    variant={selectedFamily === family ? 'contained' : 'outlined'}
                    onClick={() => setSelectedFamily(family)}
                    sx={{ minHeight: tokens.size.control, minWidth: tokens.size.control }}
                  >
                    {MODEL_LABELS[family]}
                  </Button>
                ))}
              </Stack>
            </Stack>

            {selectedEvaluation !== undefined ? (
              <Stack spacing={3}>
                <Box
                  component="section"
                  aria-label={`Ringkasan Step 7 ${MODEL_LABELS[selectedEvaluation.model_family]}`}
                  aria-live="polite"
                  sx={detailGridSx}
                >
                  {[
                    ['Threshold p99.5', String(selectedEvaluation.threshold.value)],
                    [
                      'Clean-validation alert rate',
                      formatFractionAsPercent(selectedEvaluation.threshold.clean_alert_rate),
                    ],
                    [
                      'Point ROC AUC',
                      formatFractionAsPercent(selectedEvaluation.point_auc.roc),
                    ],
                    [
                      'Point PR AUC (trapezoidal)',
                      formatFractionAsPercent(selectedEvaluation.point_auc.pr_trapezoidal),
                    ],
                  ].map(([label, value]) => (
                    <Paper variant="outlined" key={label} sx={{ p: 3 }}>
                      <Typography variant="caption" color="text.secondary">
                        {label}
                      </Typography>
                      <Typography variant="h3" sx={technicalTextSx}>
                        {value}
                      </Typography>
                    </Paper>
                  ))}
                </Box>

                <ScopeMetricsTable item={selectedEvaluation} />

                <TechnicalEvaluationDetails
                  key={selectedEvaluation.model_family}
                  item={selectedEvaluation}
                  evaluation={offlineEvaluations.data.evaluation}
                />
              </Stack>
            ) : null}
          </Stack>
        )}
      </Stack>

      <RegistryDetailDialog
        item={registryDetail}
        onClose={() => setRegistryDetail(null)}
      />
      <ExactEvaluationDialog
        items={orderedEvaluations}
        open={exactDataOpen}
        onClose={() => setExactDataOpen(false)}
      />
    </Stack>
  )
}
