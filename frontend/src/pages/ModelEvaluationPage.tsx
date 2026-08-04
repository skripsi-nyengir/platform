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
  LinearProgress,
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
import type { OfflineEvaluationItem } from '../contracts/offlineEvaluations'
import {
  useModelRegistryQuery,
  useOfflineEvaluationsQuery,
} from '../features/modelEvaluation/queries'
import { tokens } from '../theme/tokens'

const MODEL_ORDER = ['conv1d', 'gru', 'lstm', 'rnn', 'transformer'] as const
type ModelFamily = (typeof MODEL_ORDER)[number]

const MODEL_LABELS: Record<ModelFamily, string> = {
  conv1d: 'Conv1D',
  gru: 'GRU',
  lstm: 'LSTM',
  rnn: 'RNN',
  transformer: 'Transformer',
}

const technicalTextSx = {
  fontFamily: tokens.font.data,
  fontVariantNumeric: 'tabular-nums',
  overflowWrap: 'anywhere',
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
    .map(([key, value]) => `${key}: ${typeof value === 'string' ? value : JSON.stringify(value)}`)
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

function formatAlertRate(value: number): string {
  return `${value.toLocaleString('id-ID', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })} /hari`
}

function RegistryDetailDialog({ item, onClose }: {
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
                  <Typography component="dd" variant="body2" sx={{ ...technicalTextSx, m: 0 }}>
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

function ExactEvaluationDialog({ items, open, onClose }: {
  items: readonly OfflineEvaluationItem[]
  open: boolean
  onClose: () => void
}) {
  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="md">
      <DialogTitle>Data eksak evaluasi offline</DialogTitle>
      <DialogContent>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          Nilai mentah pecahan yang digunakan pada chart. Persentase pada chart adalah nilai ini × 100.
        </Typography>
        <TableContainer sx={{ maxWidth: '100%', overflowX: 'auto' }}>
          <Table size="small" aria-label="Data eksak precision recall dan F1">
            <TableHead>
              <TableRow>
                <TableCell>Model</TableCell>
                <TableCell align="right">Precision</TableCell>
                <TableCell align="right">Recall</TableCell>
                <TableCell align="right">F1</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {items.map((item) => (
                <TableRow key={item.model_family}>
                  <TableCell>{MODEL_LABELS[item.model_family]}</TableCell>
                  <TableCell align="right" sx={technicalTextSx}>{String(item.metrics.window_precision)}</TableCell>
                  <TableCell align="right" sx={technicalTextSx}>{String(item.metrics.window_recall)}</TableCell>
                  <TableCell align="right" sx={technicalTextSx}>{String(item.metrics.window_f1)}</TableCell>
                </TableRow>
              ))}
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

function TechnicalEvaluationDetails({ item }: { item: OfflineEvaluationItem }) {
  const facts = [
    ['Threshold', String(item.threshold.value)],
    ['Threshold policy', `${item.threshold.policy} · α=${item.threshold.alpha} · ${item.threshold.comparison}`],
    ['Window validasi', item.n_val_windows.toLocaleString('id-ID')],
    ['Window test', item.n_test_windows.toLocaleString('id-ID')],
    ['Event', item.n_events.toLocaleString('id-ID')],
    ['Window positif', item.n_positive_windows.toLocaleString('id-ID')],
    ['Model SHA-256', item.model_sha256],
    ['Dataset evaluasi', item.dataset_reference],
    ['Forward validation', `${item.forward_validation.passed ? 'Lulus' : 'Tidak lulus'} · recon max abs diff ${item.forward_validation.recon_max_abs_diff} · score rel error ${item.forward_validation.score_rel_error}`],
    ['Forward provenance', item.provenance.forward],
    ['Torch', item.provenance.torch_version],
    ['Computed at (UTC)', item.provenance.computed_at],
  ] as const

  return (
    <Accordion
      disableGutters
      variant="outlined"
      slots={{ heading: 'div' }}
      sx={{ minWidth: 0, '&::before': { display: 'none' }, '&.Mui-expanded': { m: 0 } }}
    >
      <AccordionSummary
        aria-controls="offline-technical-details"
        id="offline-technical-summary"
        sx={{ minHeight: tokens.size.control, '&.Mui-expanded': { minHeight: tokens.size.control } }}
      >
        <Typography sx={{ fontWeight: 700 }}>Detail teknis evaluasi {MODEL_LABELS[item.model_family]}</Typography>
      </AccordionSummary>
      <AccordionDetails id="offline-technical-details">
        <Box component="dl" sx={{ ...detailGridSx, m: 0 }}>
          {facts.map(([label, value]) => (
            <Box key={label} sx={{ minWidth: 0 }}>
              <Typography component="dt" variant="caption" color="text.secondary">{label}</Typography>
              <Typography component="dd" variant="body2" sx={{ ...technicalTextSx, m: 0 }}>{value}</Typography>
            </Box>
          ))}
        </Box>
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
  const [selectedFamily, setSelectedFamily] = useState<ModelFamily>('conv1d')
  const [exactDataOpen, setExactDataOpen] = useState(false)
  const orderedEvaluations = useMemo(
    () => MODEL_ORDER.flatMap((family) =>
      offlineEvaluations.data?.items.filter((item) => item.model_family === family) ?? [],
    ),
    [offlineEvaluations.data],
  )
  const selectedEvaluation = orderedEvaluations.find((item) => item.model_family === selectedFamily)

  return (
    <Stack spacing={6} sx={{ minWidth: 0 }}>
      <Stack spacing={0.5}>
        <Typography variant="h1">Model Evaluation</Typography>
        <Typography color="text.secondary">
          Bandingkan bukti training yang dilaporkan dengan evaluasi offline berlabel tanpa menggabungkan provenance keduanya.
        </Typography>
      </Stack>

      <Stack component="section" aria-labelledby="reported-registry-heading" spacing={2} sx={{ minWidth: 0 }}>
        <Stack spacing={0.5}>
          <Typography id="reported-registry-heading" variant="h2" sx={{ textWrap: 'balance' }}>
            Model terdaftar (metrik dilaporkan dari training)
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Registry melaporkan best validation MSE dari proses training; bukan hasil evaluasi offline platform.
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
              <Paper component="article" variant="outlined" key={item.id} sx={{ p: 3, minWidth: 0 }}>
                <Stack spacing={2} sx={{ height: '100%', minWidth: 0 }}>
                  <Stack spacing={0.5}>
                    <Typography variant="h3">{item.display_name}</Typography>
                    <Typography variant="body2" color="primary.main" sx={technicalTextSx}>{item.family}</Typography>
                  </Stack>
                  <Typography variant="body2" color="text.secondary">{item.summary}</Typography>
                  <Box component="dl" sx={{ display: 'grid', gap: 1.5, m: 0, minWidth: 0 }}>
                    {[
                      ['Best val MSE', String(item.best_val_mse)],
                      ['Parameter', item.param_count.toLocaleString('id-ID')],
                      ['Epoch', String(item.best_epoch)],
                      ['Ringkasan arsitektur', summarizeArchitecture(item)],
                    ].map(([label, value]) => (
                      <Box key={label} sx={{ minWidth: 0 }}>
                        <Typography component="dt" variant="caption" color="text.secondary">{label}</Typography>
                        <Typography component="dd" variant="body2" sx={{ ...technicalTextSx, m: 0 }}>{value}</Typography>
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

      <Stack component="section" aria-labelledby="offline-evaluations-heading" spacing={3} sx={{ minWidth: 0 }}>
        <Stack spacing={0.5}>
          <Typography id="offline-evaluations-heading" variant="h2" sx={{ textWrap: 'balance' }}>
            Evaluasi offline (test-set injected berlabel)
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Perbandingan netral pada artifact model yang diuji terhadap test-set injected berlabel; bukan inferensi live.
          </Typography>
        </Stack>
        {offlineEvaluations.data === undefined ? (
          offlineEvaluations.isError ? (
            <ApiErrorPanel error={offlineEvaluations.error} onRetry={() => void offlineEvaluations.refetch()} />
          ) : (
            <PanelSkeleton label="Loading offline evaluations" />
          )
        ) : (
          <Stack spacing={3} sx={{ minWidth: 0 }}>
            <Paper variant="outlined" sx={{ p: { xs: 2, sm: 3 }, minWidth: 0, overflow: 'hidden' }}>
              <Stack spacing={2} sx={{ minWidth: 0 }}>
                <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2} sx={{ justifyContent: 'space-between', alignItems: { sm: 'center' } }}>
                  <Stack spacing={0.5}>
                    <Typography variant="h3">Precision, recall, dan F1 per model</Typography>
                    <Typography id="offline-chart-description" variant="body2" color="text.secondary">
                      Chart batang horizontal berkelompok, dalam urutan Conv1D, GRU, LSTM, RNN, Transformer, dengan skala tetap 0–100% dari baseline nol.
                    </Typography>
                  </Stack>
                  <Button variant="outlined" onClick={() => setExactDataOpen(true)} sx={{ minHeight: tokens.size.control, flexShrink: 0 }}>
                    Lihat data eksak
                  </Button>
                </Stack>
                <Box
                  role="img"
                  aria-label="Perbandingan precision recall dan F1 lima model"
                  aria-describedby="offline-chart-description"
                  sx={{ width: '100%', minWidth: 0, overflow: 'hidden' }}
                >
                  <BarChart
                    id="offline-model-comparison-chart"
                    title="Perbandingan metrik evaluasi offline"
                    desc="Precision, recall, dan F1 untuk Conv1D, GRU, LSTM, RNN, dan Transformer pada domain nol sampai seratus persen."
                    layout="horizontal"
                    height={360}
                    margin={{ left: 8, right: 16 }}
                    skipAnimation
                    xAxis={[{ id: 'percent-axis', min: 0, max: 100, label: 'Persen' }]}
                    yAxis={[{
                      id: 'model-axis',
                      data: orderedEvaluations.map((item) => MODEL_LABELS[item.model_family]),
                      scaleType: 'band',
                      width: 'auto',
                      tickLabelStyle: { fontFamily: 'sans-serif', fontSize: 12 },
                    }]}
                    series={[
                      { id: 'precision', label: 'Precision', color: chartColors.temperature, data: orderedEvaluations.map((item) => item.metrics.window_precision * 100) },
                      { id: 'recall', label: 'Recall', color: chartColors.humidity, data: orderedEvaluations.map((item) => item.metrics.window_recall * 100) },
                      { id: 'f1', label: 'F1', color: chartColors.anomalyScore, data: orderedEvaluations.map((item) => item.metrics.window_f1 * 100) },
                    ].map((series) => ({ ...series, xAxisId: 'percent-axis', yAxisId: 'model-axis', valueFormatter: (value: number | null) => value === null ? null : `${value.toFixed(2)}%` }))}
                  />
                </Box>
              </Stack>
            </Paper>

            <Stack spacing={1}>
              <Typography variant="h3">Pilih model untuk rincian offline</Typography>
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
                <Box aria-live="polite" sx={detailGridSx}>
                  {[
                    ['Composite Fc1', formatFractionAsPercent(selectedEvaluation.metrics.composite_fc1)],
                    ['Event hit rate', formatFractionAsPercent(selectedEvaluation.metrics.event_hit_rate)],
                    ['Clean-test FPR', formatFractionAsPercent(selectedEvaluation.metrics.clean_test_fpr)],
                    ['Alert rate', formatAlertRate(selectedEvaluation.metrics.alert_rate)],
                  ].map(([label, value]) => (
                    <Paper variant="outlined" key={label} sx={{ p: 3 }}>
                      <Typography variant="caption" color="text.secondary">{label}</Typography>
                      <Typography variant="h3" sx={technicalTextSx}>{value}</Typography>
                    </Paper>
                  ))}
                </Box>

                <Paper component="section" aria-labelledby="event-family-heading" variant="outlined" sx={{ p: 3, minWidth: 0 }}>
                  <Stack spacing={2}>
                    <Stack spacing={0.5}>
                      <Typography id="event-family-heading" variant="h3">Event-family hit rate · {MODEL_LABELS[selectedEvaluation.model_family]}</Typography>
                      <Typography variant="body2" color="text.secondary">Persentase event family yang terdeteksi; jumlah hit tidak ditampilkan karena denominator per family tidak tersedia.</Typography>
                    </Stack>
                    {Object.entries(selectedEvaluation.metrics.event_hit_by_family).map(([family, value]) => (
                      <Stack key={family} spacing={0.5}>
                        <Stack direction="row" spacing={2} sx={{ justifyContent: 'space-between', minWidth: 0 }}>
                          <Typography variant="body2" sx={{ overflowWrap: 'anywhere' }}>{family.replaceAll('_', ' ')}</Typography>
                          <Typography variant="body2" sx={technicalTextSx}>{formatFractionAsPercent(value)}</Typography>
                        </Stack>
                        <LinearProgress variant="determinate" value={value * 100} aria-label={`Event hit ${family.replaceAll('_', ' ')}`} />
                      </Stack>
                    ))}
                  </Stack>
                </Paper>

                <TechnicalEvaluationDetails item={selectedEvaluation} />
              </Stack>
            ) : null}
          </Stack>
        )}
      </Stack>

      <RegistryDetailDialog item={registryDetail} onClose={() => setRegistryDetail(null)} />
      <ExactEvaluationDialog items={orderedEvaluations} open={exactDataOpen} onClose={() => setExactDataOpen(false)} />
    </Stack>
  )
}
