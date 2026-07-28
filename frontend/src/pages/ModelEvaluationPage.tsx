import { Alert, Box, Divider, Paper, Stack, Typography } from '@mui/material'
import { ApiErrorPanel } from '../components/states/ApiErrorPanel'
import { PanelSkeleton } from '../components/states/PanelSkeleton'
import {
  useModelEvaluationsQuery,
  useModelRegistryQuery,
} from '../features/modelEvaluation/queries'
import { ModelRegistryPanel } from '../features/preview/ModelRegistryPanel'
import { ReplayPanel } from '../features/preview/ReplayPanel'
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

export function ModelEvaluationPage() {
  const pilot = useModelEvaluationsQuery({ page: 1, pageSize: 25 })
  const registry = useModelRegistryQuery()

  return (
    <Stack spacing={6}>
      <Stack spacing={0.5}>
        <Typography variant="h1">Model Evaluation</Typography>
        <Typography color="text.secondary">Registry preview dan snapshot evaluasi Dandy dipisahkan.</Typography>
      </Stack>

      <ModelRegistryPanel />

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

      <Stack component="section" aria-labelledby="pilot-heading" spacing={2}>
        <Typography id="pilot-heading" variant="h2">Reported Dandy pilot</Typography>
        <Alert severity="warning">
          Snapshot ini berasal dari satu run; test sudah diamati, bukan evaluasi independen atau hasil
          final. Seluruh model gagal skenario stuck.
        </Alert>
        {pilot.data === undefined ? (
          pilot.isError ? <ApiErrorPanel error={pilot.error} onRetry={() => void pilot.refetch()} />
            : <PanelSkeleton label="Loading Dandy pilot snapshot" />
        ) : (
          <Stack spacing={1}>
            {pilot.data.items.map((item) => (
              <Paper key={item.version} variant="outlined" sx={{ p: 2 }}>
                <Typography variant="h3">{item.model}</Typography>
                <Typography variant="body2" color="text.secondary">
                  {item.label} · stuck: gagal
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Test diamati: {item.test_observed ? 'ya' : 'tidak'} · Evaluasi final independen:{' '}
                  {item.independent_final ? 'ya' : 'tidak'}
                </Typography>
                <Typography variant="caption" color="text.secondary" sx={{ overflowWrap: 'anywhere' }}>
                  Sumber: {item.source_path ?? 'tidak tersedia'} · commit {item.source_commit ?? 'tidak tersedia'}
                </Typography>
              </Paper>
            ))}
          </Stack>
        )}
      </Stack>

      <ReplayPanel />
    </Stack>
  )
}
