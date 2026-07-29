import {
  Alert,
  Box,
  Button,
  Card,
  CardActionArea,
  CardContent,
  Chip,
  Grid,
  LinearProgress,
  Paper,
  Stack,
  Typography,
} from '@mui/material'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { getInjectionEvents } from '../api/injection'
import { getSimulationModels, setSimulationActiveModel } from '../api/simulation'
import { ApiErrorPanel } from '../components/states/ApiErrorPanel'
import { EmptyState } from '../components/states/EmptyState'
import { PanelSkeleton } from '../components/states/PanelSkeleton'
import { simDeviceId } from '../contracts/common'
import { ReplayJobRequestSchema } from '../contracts/preview'
import type { SimModel } from '../contracts/simulation'
import { useInferenceResultsQuery } from '../features/inference/queries'
import { useCreateReplayMutation, useReplayJobQuery } from '../features/preview/queries'
import { SimulationCharts } from '../features/simulation/SimulationCharts'
import { useTelemetryHistoryQuery } from '../features/telemetry/queries'
import { randomId } from '../lib/id'
import { tokens } from '../theme/tokens'

export const simulationDemoWindow = Object.freeze({
  from: '2026-04-19T00:49:45',
  to: '2026-04-19T01:49:45',
})

const simulationModelsKey = ['simulation', 'models'] as const
const technicalTextSx = {
  fontFamily: tokens.font.data,
  fontVariantNumeric: 'tabular-nums',
  overflowWrap: 'anywhere',
} as const

function shortHash(value: string): string {
  return `${value.slice(0, 12)}…`
}

function ModelCard({
  model,
  disabled,
  selecting,
  onSelect,
}: {
  model: SimModel
  disabled: boolean
  selecting: boolean
  onSelect: () => void
}) {
  return (
    <Card component="article" variant="outlined" sx={{ height: '100%', minWidth: 0 }}>
      <CardActionArea
        data-active={model.is_active ? 'true' : undefined}
        disabled={disabled || model.is_active}
        onClick={onSelect}
        aria-label={`${model.display_name}${model.is_active ? ', active model' : ', select model'}`}
        sx={{
          height: '100%',
          p: 3,
          alignItems: 'stretch',
          borderLeft: `${tokens.size.activeRule}px solid transparent`,
          '&[data-active="true"]': {
            borderLeftColor: 'primary.main',
            backgroundColor: tokens.color.signalSoft,
          },
        }}
      >
        <CardContent sx={{ p: 0, '&:last-child': { pb: 0 } }}>
          <Stack spacing={2}>
            <Stack direction="row" spacing={1} useFlexGap sx={{ alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap' }}>
              <Typography variant="h3">{model.display_name}</Typography>
              {model.is_active ? <Chip label="Active" color="primary" size="small" /> : null}
              {selecting ? <Chip label="Selecting…" size="small" /> : null}
            </Stack>
            <Box component="dl" sx={{ display: 'grid', gridTemplateColumns: 'auto minmax(0, 1fr)', gap: 1, m: 0 }}>
              <Typography component="dt" variant="caption" color="text.secondary">Threshold</Typography>
              <Typography component="dd" variant="body2" sx={{ ...technicalTextSx, m: 0, textAlign: 'right' }}>
                {String(model.threshold)}
              </Typography>
              <Typography component="dt" variant="caption" color="text.secondary">Score key</Typography>
              <Typography component="dd" variant="body2" sx={{ ...technicalTextSx, m: 0, textAlign: 'right' }}>
                {model.score_key}
              </Typography>
              <Typography component="dt" variant="caption" color="text.secondary">Manifest</Typography>
              <Typography component="dd" variant="body2" title={model.manifest_sha256} sx={{ ...technicalTextSx, m: 0, textAlign: 'right' }}>
                {shortHash(model.manifest_sha256)}
              </Typography>
            </Box>
          </Stack>
        </CardContent>
      </CardActionArea>
    </Card>
  )
}

function SimulationResults({ modelVersion }: { modelVersion: string }) {
  const telemetry = useTelemetryHistoryQuery({
    deviceId: simDeviceId,
    ...simulationDemoWindow,
    bucket: 'raw',
    limit: 2_000,
  })
  const inference = useInferenceResultsQuery({
    deviceId: simDeviceId,
    ...simulationDemoWindow,
    bucket: 'raw',
    limit: 2_000,
    modelVersion,
  })
  const injections = useQuery({
    queryKey: ['simulation', 'injections', simDeviceId],
    queryFn: ({ signal }) => getInjectionEvents(simDeviceId, signal),
    staleTime: Number.POSITIVE_INFINITY,
  })
  const firstError = telemetry.error ?? inference.error ?? injections.error

  if (telemetry.data === undefined || inference.data === undefined || injections.data === undefined) {
    if (firstError !== null) {
      return (
        <ApiErrorPanel
          error={firstError}
          onRetry={() => void Promise.all([
            telemetry.refetch(),
            inference.refetch(),
            injections.refetch(),
          ])}
        />
      )
    }
    return <PanelSkeleton label="Loading simulation results" />
  }

  if (telemetry.data.points.length === 0 || inference.data.points.length === 0) {
    return (
      <EmptyState
        title="Replay returned no chart points"
        detail="Run the injected replay again or inspect the replay status before comparing results."
      />
    )
  }

  return (
    <SimulationCharts
      {...simulationDemoWindow}
      telemetry={telemetry.data.points}
      inference={inference.data.points}
      injections={injections.data.events}
    />
  )
}

export function SimulationPage() {
  const queryClient = useQueryClient()
  const models = useQuery({
    queryKey: simulationModelsKey,
    queryFn: ({ signal }) => getSimulationModels(signal),
  })
  const createReplay = useCreateReplayMutation()
  const [jobId, setJobId] = useState<string>()
  const [completedModelVersion, setCompletedModelVersion] = useState<string>()
  const replayStatus = useReplayJobQuery(jobId)
  const job = replayStatus.data?.job ?? createReplay.data?.job
  const terminal = job?.status === 'succeeded' || job?.status === 'failed'
  const replayRunning = job !== undefined && !terminal
  const activeModel = models.data?.models.find((model) => model.is_active)
  const activation = useMutation({
    mutationFn: (modelVersion: string) => setSimulationActiveModel(modelVersion),
    onSuccess: async () => {
      setJobId(undefined)
      setCompletedModelVersion(undefined)
      createReplay.reset()
      await queryClient.invalidateQueries({ queryKey: simulationModelsKey })
    },
  })

  useEffect(() => {
    if (job?.status === 'succeeded') setCompletedModelVersion(job.model_version)
  }, [job])

  const runReplay = () => {
    if (activeModel === undefined) return
    const request = ReplayJobRequestSchema.parse({
      command_id: randomId(),
      device_id: simDeviceId,
      ...simulationDemoWindow,
    })
    setCompletedModelVersion(undefined)
    createReplay.mutate(request, {
      onSuccess: (response) => setJobId(response.job.job_id),
    })
  }

  return (
    <Stack spacing={6}>
      <Stack spacing={0.5}>
        <Typography variant="h1" sx={{ textWrap: 'balance' }}>Anomaly simulation</Typography>
        <Typography color="text.secondary" sx={{ textWrap: 'pretty' }}>
          Select an artifact model, replay the injected corpus, and compare detections with ground truth.
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={technicalTextSx}>
          Device: {simDeviceId} · Asia/Jakarta (WIB)
        </Typography>
      </Stack>

      <Stack component="section" aria-labelledby="simulation-models-heading" spacing={2}>
        <Stack spacing={0.5}>
          <Typography id="simulation-models-heading" variant="h2">1 · Pick an artifact model</Typography>
          <Typography variant="body2" color="text.secondary">
            Each card exposes the artifact calibration used by the next replay.
          </Typography>
        </Stack>
        {models.data === undefined ? (
          models.isError ? (
            <ApiErrorPanel error={models.error} onRetry={() => void models.refetch()} />
          ) : (
            <PanelSkeleton label="Loading simulation models" />
          )
        ) : (
          <Grid container spacing={2}>
            {models.data.models.map((model) => (
              <Grid key={model.version} size={{ xs: 12, md: 4 }}>
                <ModelCard
                  model={model}
                  disabled={activation.isPending || replayRunning}
                  selecting={activation.isPending && activation.variables === model.version}
                  onSelect={() => activation.mutate(model.version)}
                />
              </Grid>
            ))}
          </Grid>
        )}
        {activation.isError ? <Alert severity="error">{activation.error.message}</Alert> : null}
      </Stack>

      <Paper component="section" aria-labelledby="simulation-replay-heading" variant="outlined" sx={{ p: 4 }}>
        <Stack spacing={2}>
          <Stack spacing={0.5}>
            <Typography id="simulation-replay-heading" variant="h2">2 · Run injected replay</Typography>
            <Typography variant="body2" color="text.secondary">
              Fixed one-hour demo window · {simulationDemoWindow.from} – {simulationDemoWindow.to} WIB
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Active artifact: <Box component="span" sx={technicalTextSx}>{activeModel?.display_name ?? 'Unavailable'}</Box>
            </Typography>
          </Stack>
          <Box>
            <Button
              variant="contained"
              disabled={activeModel === undefined || activation.isPending || createReplay.isPending || replayRunning}
              onClick={runReplay}
            >
              {replayRunning ? 'Replay running…' : 'Run injected replay'}
            </Button>
          </Box>
          {createReplay.isError ? <Alert severity="error">{createReplay.error.message}</Alert> : null}
          {replayStatus.isError ? (
            <ApiErrorPanel error={replayStatus.error} onRetry={() => void replayStatus.refetch()} />
          ) : null}
          {job === undefined ? null : (
            <Stack role="status" aria-label="Simulation replay progress" spacing={1}>
              <Stack direction="row" spacing={1} useFlexGap sx={{ alignItems: 'center', flexWrap: 'wrap' }}>
                <Chip
                  size="small"
                  color={job.status === 'succeeded' ? 'success' : job.status === 'failed' ? 'error' : 'primary'}
                  label={job.status}
                />
                <Typography variant="body2" sx={technicalTextSx}>
                  {Math.round(job.progress * 100)}% · {job.model_version}
                </Typography>
              </Stack>
              <LinearProgress variant="determinate" value={job.progress * 100} />
              <Typography variant="body2" color="text.secondary" sx={technicalTextSx}>
                {job.processed_count.toLocaleString('id-ID')} processed · {job.result_count.toLocaleString('id-ID')} results
              </Typography>
              {job.status === 'failed' ? (
                <Alert severity="error">{job.error_detail ?? job.error_code ?? 'Replay failed'}</Alert>
              ) : null}
            </Stack>
          )}
        </Stack>
      </Paper>

      <Stack component="section" aria-labelledby="simulation-results-heading" spacing={2}>
        <Stack spacing={0.5}>
          <Typography id="simulation-results-heading" variant="h2">3 · Compare detections</Typography>
          <Typography variant="body2" color="text.secondary">
            All time-based panels use the same replay window and time scale.
          </Typography>
        </Stack>
        {completedModelVersion === undefined ? (
          <Paper variant="outlined" sx={{ p: 4 }}>
            <EmptyState
              title="Run a replay to reveal results"
              detail="The charts remain tied to the artifact version recorded by the completed replay."
            />
          </Paper>
        ) : (
          <SimulationResults modelVersion={completedModelVersion} />
        )}
      </Stack>
    </Stack>
  )
}
