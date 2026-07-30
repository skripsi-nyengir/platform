import { Box, Divider, Paper, Stack, Typography } from '@mui/material'
import { ApiErrorPanel } from '../components/states/ApiErrorPanel'
import { PanelSkeleton } from '../components/states/PanelSkeleton'
import {
  useModelRegistryQuery,
  useOfflineEvaluationsQuery,
} from '../features/modelEvaluation/queries'
import { tokens } from '../theme/tokens'

const technicalTextSx = {
  fontFamily: tokens.font.data,
  fontVariantNumeric: 'tabular-nums',
  overflowWrap: 'anywhere',
} as const

function formatArchitecture(architecture: Readonly<Record<string, unknown>>): string {
  return Object.entries(architecture)
    .map(([key, value]) => `${key}: ${typeof value === 'string' ? value : JSON.stringify(value)}`)
    .join(' · ')
}

function shortenHash(hash: string): string {
  return `${hash.slice(0, 12)}…${hash.slice(-8)}`
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

export function ModelEvaluationPage() {
  const registry = useModelRegistryQuery()
  const offlineEvaluations = useOfflineEvaluationsQuery()

  return (
    <Stack spacing={6}>
      <Stack spacing={0.5}>
        <Typography variant="h1">Model Evaluation</Typography>
        <Typography color="text.secondary">
          Metrik training yang dilaporkan dan evaluasi offline berlabel untuk lima model terlatih:
          Conv1D, GRU, LSTM, RNN, dan Transformer.
        </Typography>
      </Stack>

      <Stack component="section" aria-labelledby="reported-registry-heading" spacing={2}>
        <Stack spacing={0.5}>
          <Typography id="reported-registry-heading" variant="h2" sx={{ textWrap: 'balance' }}>
            Model terdaftar (metrik dilaporkan dari training)
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ textWrap: 'pretty' }}>
            Metrik dilaporkan dari training (val MSE); bukan hasil komputasi platform; tanpa threshold
            operasional.
          </Typography>
        </Stack>
        {registry.data === undefined ? (
          registry.isError ? (
            <ApiErrorPanel error={registry.error} onRetry={() => void registry.refetch()} />
          ) : (
            <PanelSkeleton label="Loading reported model registry" />
          )
        ) : (
          <Paper
            variant="outlined"
            sx={{
              borderLeftColor: 'primary.main',
              borderLeftStyle: 'solid',
              borderLeftWidth: tokens.size.activeRule,
              px: 4,
            }}
          >
            <Stack divider={<Divider flexItem />}>
              {registry.data.items.map((item) => {
                const facts = [
                  ['Arsitektur', formatArchitecture(item.architecture), true],
                  ['Parameter', item.param_count.toLocaleString('id-ID'), false],
                  ['Best val MSE', String(item.best_val_mse), false],
                  ['Best epoch', String(item.best_epoch), false],
                  ['Model SHA-256', shortenHash(item.model_sha256), false],
                  ['Dataset', item.dataset_reference, false],
                  ['Window / fitur', `${item.window_size} langkah · ${item.features.join(', ')}`, false],
                ] as const

                return (
                  <Box
                    component="article"
                    aria-labelledby={`${item.id}-heading`}
                    key={item.id}
                    sx={{ py: 3, minWidth: 0 }}
                  >
                    <Stack spacing={2}>
                      <Stack spacing={0.5}>
                        <Typography id={`${item.id}-heading`} variant="h3">
                          {item.display_name}
                        </Typography>
                        <Typography variant="body2" color="primary.main" sx={technicalTextSx}>
                          {item.family}
                        </Typography>
                      </Stack>
                      <Typography variant="body2" color="text.secondary">
                        {item.summary}
                      </Typography>
                      <Box
                        component="dl"
                        sx={{
                          display: 'grid',
                          gridTemplateColumns: { xs: '1fr', md: 'repeat(3, minmax(0, 1fr))' },
                          gap: 2,
                          m: 0,
                          minWidth: 0,
                        }}
                      >
                        {facts.map(([label, value, wide]) => (
                          <Box key={label} sx={{ gridColumn: wide ? '1 / -1' : 'auto', minWidth: 0 }}>
                            <Typography component="dt" variant="caption" color="text.secondary">
                              {label}
                            </Typography>
                            <Typography
                              component="dd"
                              variant="body2"
                              title={label === 'Model SHA-256' ? item.model_sha256 : undefined}
                              sx={{ ...technicalTextSx, m: 0 }}
                            >
                              {value}
                            </Typography>
                          </Box>
                        ))}
                      </Box>
                    </Stack>
                  </Box>
                )
              })}
            </Stack>
          </Paper>
        )}
      </Stack>

      <Stack component="section" aria-labelledby="offline-evaluations-heading" spacing={2}>
        <Stack spacing={0.5}>
          <Typography id="offline-evaluations-heading" variant="h2" sx={{ textWrap: 'balance' }}>
            Evaluasi offline (test-set injected berlabel)
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ textWrap: 'pretty' }}>
            Dihitung offline memakai artifact model pada test-set injected berlabel; forward
            di-reverse-engineer dari state-dict dan tervalidasi terhadap rekonstruksi artifact
            (~7.3e-4); threshold = kuantil p99 skor validasi bersih (α=0.01); bukan inferensi live
            platform.
          </Typography>
        </Stack>
        {offlineEvaluations.data === undefined ? (
          offlineEvaluations.isError ? (
            <ApiErrorPanel
              error={offlineEvaluations.error}
              onRetry={() => void offlineEvaluations.refetch()}
            />
          ) : (
            <PanelSkeleton label="Loading offline evaluations" />
          )
        ) : (
          <Paper
            variant="outlined"
            sx={{
              borderLeftColor: 'info.main',
              borderLeftStyle: 'solid',
              borderLeftWidth: tokens.size.activeRule,
              px: 4,
            }}
          >
            <Stack divider={<Divider flexItem />}>
              {offlineEvaluations.data.items.map((item, index) => {
                const facts: ReadonlyArray<readonly [string, string, string?]> = [
                  ['Window precision', formatFractionAsPercent(item.metrics.window_precision)],
                  ['Window recall', formatFractionAsPercent(item.metrics.window_recall)],
                  ['Window F1', formatFractionAsPercent(item.metrics.window_f1)],
                  ['Event hit rate', formatFractionAsPercent(item.metrics.event_hit_rate)],
                  ['Clean test FPR', formatFractionAsPercent(item.metrics.clean_test_fpr)],
                  ['Composite Fc1', formatFractionAsPercent(item.metrics.composite_fc1)],
                  ['Alert rate', formatAlertRate(item.metrics.alert_rate)],
                  ...Object.entries(item.metrics.event_hit_by_family).map(
                    ([family, value]) =>
                      [
                        `Event hit · ${family.replaceAll('_', ' ')}`,
                        formatFractionAsPercent(value),
                      ] as const,
                  ),
                  ['Threshold', String(item.threshold.value)],
                  [
                    'Threshold policy',
                    `${item.threshold.policy} · α=${item.threshold.alpha} · ${item.threshold.comparison}`,
                  ],
                  ['Test windows', item.n_test_windows.toLocaleString('id-ID')],
                  ['Events', item.n_events.toLocaleString('id-ID')],
                  ['Model SHA-256', shortenHash(item.model_sha256), item.model_sha256],
                  ['Dataset', item.dataset_reference],
                ]
                const headingId = `offline-${item.model_family}-${index}-heading`

                return (
                  <Box
                    component="article"
                    aria-labelledby={headingId}
                    key={item.model_sha256}
                    sx={{ py: 3, minWidth: 0 }}
                  >
                    <Stack spacing={2}>
                      <Stack spacing={0.5}>
                        <Typography id={headingId} variant="h3">
                          {item.model_family.toUpperCase()}
                        </Typography>
                        <Typography variant="body2" color="info.main" sx={technicalTextSx}>
                          Keluarga model: {item.model_family}
                        </Typography>
                      </Stack>
                      <Box
                        component="dl"
                        sx={{
                          display: 'grid',
                          gridTemplateColumns: { xs: '1fr', md: 'repeat(3, minmax(0, 1fr))' },
                          gap: 2,
                          m: 0,
                          minWidth: 0,
                        }}
                      >
                        {facts.map(([label, value, title]) => (
                          <Box key={label} sx={{ minWidth: 0 }}>
                            <Typography component="dt" variant="caption" color="text.secondary">
                              {label}
                            </Typography>
                            <Typography
                              component="dd"
                              variant="body2"
                              title={title}
                              sx={{ ...technicalTextSx, m: 0 }}
                            >
                              {value}
                            </Typography>
                          </Box>
                        ))}
                      </Box>
                    </Stack>
                  </Box>
                )
              })}
            </Stack>
          </Paper>
        )}
      </Stack>

    </Stack>
  )
}
