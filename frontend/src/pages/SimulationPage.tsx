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
import { useEffect, useMemo, useState } from 'react'
import { ApiError } from '../api/errors'
import { getInjectionEvents } from '../api/injection'
import { getSimulationModels, setSimulationActiveModel } from '../api/simulation'
import { ApiErrorPanel } from '../components/states/ApiErrorPanel'
import { EmptyState } from '../components/states/EmptyState'
import { PanelSkeleton } from '../components/states/PanelSkeleton'
import {
  HistoricalDateTimeSchema,
  compareHistoricalDateTimes,
  simDeviceId,
  type HistoricalDateTime,
} from '../contracts/common'
import type { SimInjectionEvent } from '../contracts/injection'
import { ReplayJobRequestSchema } from '../contracts/preview'
import {
  simModelWindowSizes,
  type SimModel,
} from '../contracts/simulation'
import { useInferenceResultsQuery } from '../features/inference/queries'
import { useCreateReplayMutation, useReplayJobQuery } from '../features/preview/queries'
import { InjectionEventNavigator } from '../features/simulation/InjectionEventNavigator'
import { SimulationCharts } from '../features/simulation/SimulationCharts'
import { SimulationMetricsPanels } from '../features/simulation/SimulationMetricsPanels'
import { useSimulationMetricsQuery } from '../features/simulation/queries'
import { useTelemetryHistoryQuery } from '../features/telemetry/queries'
import { randomId } from '../lib/id'
import { tokens } from '../theme/tokens'

const simulationModelsKey = ['simulation', 'models'] as const
const technicalTextSx = {
  fontFamily: tokens.font.data,
  fontVariantNumeric: 'tabular-nums',
  overflowWrap: 'anywhere',
} as const

interface SimulationWindow {
  from: HistoricalDateTime
  to: HistoricalDateTime
}

function shortHash(value: string): string {
  return `${value.slice(0, 12)}…`
}

function isReplayOverlapError(error: unknown): error is ApiError {
  return error instanceof ApiError &&
    error.status === 409 &&
    error.message.includes('Replay interval overlaps existing job')
}

function fullInjectionWindow(events: readonly SimInjectionEvent[]): SimulationWindow | undefined {
  const first = events[0]
  const last = events.at(-1)
  return first === undefined || last === undefined
    ? undefined
    : { from: first.start_ts, to: last.end_ts }
}

function shiftHistoricalDateTime(value: HistoricalDateTime, minutes: number): HistoricalDateTime {
  const shifted = new Date(Date.parse(`${value}Z`) + minutes * 60_000)
  return HistoricalDateTimeSchema.parse(shifted.toISOString().slice(0, 19))
}

function eventDetailWindow(
  event: SimInjectionEvent,
  corpus: SimulationWindow,
): SimulationWindow {
  const paddedFrom = shiftHistoricalDateTime(event.start_ts, -10)
  const paddedTo = shiftHistoricalDateTime(event.end_ts, 10)
  return {
    from: compareHistoricalDateTimes(paddedFrom, corpus.from) < 0 ? corpus.from : paddedFrom,
    to: compareHistoricalDateTimes(paddedTo, corpus.to) > 0 ? corpus.to : paddedTo,
  }
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
            <Typography variant="caption" color="text.secondary" sx={technicalTextSx}>{model.version}</Typography>
            <Box component="dl" sx={{ display: 'grid', gridTemplateColumns: 'auto minmax(0, 1fr)', gap: 1, m: 0 }}>
              <Typography component="dt" variant="caption" color="text.secondary">Threshold</Typography>
              <Typography component="dd" variant="body2" sx={{ ...technicalTextSx, m: 0, textAlign: 'right' }}>
                {String(model.threshold)}
              </Typography>
              <Typography component="dt" variant="caption" color="text.secondary">Window size</Typography>
              <Typography component="dd" variant="body2" sx={{ ...technicalTextSx, m: 0, textAlign: 'right' }}>
                {simModelWindowSizes[model.version]}
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

function ReplayVisualization({
  model,
  injections,
  corpusWindow,
}: {
  model: SimModel
  injections: readonly SimInjectionEvent[]
  corpusWindow: SimulationWindow
}) {
  const [selectedIndex, setSelectedIndex] = useState(0)
  const selectedEvent = injections[selectedIndex] ?? injections[0]
  const window = useMemo(
    () => selectedEvent === undefined ? corpusWindow : eventDetailWindow(selectedEvent, corpusWindow),
    [corpusWindow, selectedEvent],
  )
  const telemetry = useTelemetryHistoryQuery({
    deviceId: simDeviceId,
    ...window,
    bucket: 'raw',
    limit: 5_000,
  })
  const inference = useInferenceResultsQuery({
    deviceId: simDeviceId,
    ...window,
    bucket: 'raw',
    limit: 5_000,
    modelVersion: model.version,
  })
  const firstError = telemetry.error ?? inference.error

  if (selectedEvent === undefined) {
    return <EmptyState title="No injection events" detail="The simulation corpus has no injected events to inspect." />
  }

  return (
    <Stack spacing={3}>
      <InjectionEventNavigator
        events={injections}
        selectedIndex={selectedIndex}
        onSelect={setSelectedIndex}
      />
      {telemetry.data === undefined || inference.data === undefined ? (
        firstError === null ? (
          <PanelSkeleton label="Loading selected event telemetry" />
        ) : (
          <ApiErrorPanel
            error={firstError}
            onRetry={() => void Promise.all([telemetry.refetch(), inference.refetch()])}
          />
        )
      ) : telemetry.data.points.length === 0 || inference.data.points.length === 0 ? (
        <Paper variant="outlined" sx={{ p: 4 }}>
          <EmptyState
            title="No chart detail for this event"
            detail="The model has metrics, but raw telemetry or inference points are unavailable in this event window."
          />
        </Paper>
      ) : (
        <SimulationCharts
          {...window}
          telemetry={telemetry.data.points}
          inference={inference.data.points}
          model={model}
        />
      )}
    </Stack>
  )
}

export function SimulationPage() {
  const queryClient = useQueryClient()
  const models = useQuery({
    queryKey: simulationModelsKey,
    queryFn: ({ signal }) => getSimulationModels(signal),
  })
  const injections = useQuery({
    queryKey: ['simulation', 'injections', simDeviceId],
    queryFn: ({ signal }) => getInjectionEvents(simDeviceId, signal),
    staleTime: Number.POSITIVE_INFINITY,
  })
  const activeModel = models.data?.models.find((model) => model.is_active)
  const metrics = useSimulationMetricsQuery(activeModel?.version)
  const corpusWindow = useMemo(
    () => fullInjectionWindow(injections.data?.events ?? []),
    [injections.data?.events],
  )
  const createReplay = useCreateReplayMutation()
  const [jobId, setJobId] = useState<string>()
  const replayStatus = useReplayJobQuery(jobId)
  const job = replayStatus.data?.job ?? createReplay.data?.job
  const terminal = job?.status === 'succeeded' || job?.status === 'failed'
  const replayRunning = job !== undefined && !terminal
  const activation = useMutation({
    mutationFn: (modelVersion: string) => setSimulationActiveModel(modelVersion),
    onSuccess: async () => {
      setJobId(undefined)
      createReplay.reset()
      await queryClient.invalidateQueries({ queryKey: simulationModelsKey })
    },
  })

  useEffect(() => {
    if (job?.status !== 'succeeded') return
    void queryClient.invalidateQueries({ queryKey: ['simulation', 'metrics', job.model_version] })
    void queryClient.invalidateQueries({ queryKey: ['inference', 'results', simDeviceId] })
  }, [job?.job_id, job?.model_version, job?.status, queryClient])

  const missingReplay = metrics.error instanceof ApiError && metrics.error.status === 404
  const replayConflict = isReplayOverlapError(createReplay.error)

  const runReplay = () => {
    if (activeModel === undefined || corpusWindow === undefined) return
    const request = ReplayJobRequestSchema.parse({
      command_id: randomId(),
      device_id: simDeviceId,
      ...corpusWindow,
    })
    createReplay.reset()
    createReplay.mutate(request, {
      onSuccess: (response) => setJobId(response.job.job_id),
      onError: (error) => {
        if (isReplayOverlapError(error)) void metrics.refetch()
      },
    })
  }

  return (
    <Stack spacing={6}>
      <Stack spacing={0.5}>
        <Typography variant="h1" sx={{ textWrap: 'balance' }}>Anomaly simulation</Typography>
        <Typography color="text.secondary" sx={{ textWrap: 'pretty' }}>
          Select an artifact model, replay the complete injected corpus, and inspect server-evaluated detections.
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={technicalTextSx}>
          Device: {simDeviceId} · Asia/Jakarta (WIB)
        </Typography>
      </Stack>

      <Stack component="section" aria-labelledby="simulation-models-heading" spacing={2}>
        <Stack spacing={0.5}>
          <Typography id="simulation-models-heading" variant="h2">1 · Pick an artifact model</Typography>
          <Typography variant="body2" color="text.secondary">
            Artifact calibration and manifest identity are shown exactly as registered.
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
              <Grid key={model.version} size={{ sm: 6, lg: 4 }}>
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
            <Typography id="simulation-replay-heading" variant="h2">2 · Populate replay data</Typography>
            <Typography variant="body2" color="text.secondary" sx={technicalTextSx}>
              {corpusWindow === undefined
                ? 'Loading injected corpus range…'
                : `${corpusWindow.from} – ${corpusWindow.to} WIB · ${injections.data?.events.length.toLocaleString('id-ID')} injected events`}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Active artifact: <Box component="span" sx={technicalTextSx}>{activeModel?.display_name ?? 'Unavailable'}</Box>
            </Typography>
          </Stack>
          {injections.isError ? (
            <ApiErrorPanel error={injections.error} onRetry={() => void injections.refetch()} />
          ) : null}
          {replayConflict ? (
            <Alert severity="info">A replay already exists for this model; showing stored results.</Alert>
          ) : metrics.data !== undefined ? (
            <Alert severity="info">Replay already computed — showing stored results.</Alert>
          ) : missingReplay ? (
            <Box>
              <Button
                variant="contained"
                disabled={activeModel === undefined || corpusWindow === undefined || activation.isPending || createReplay.isPending || replayRunning}
                onClick={runReplay}
              >
                {replayRunning ? 'Replay running…' : 'Run injected replay'}
              </Button>
            </Box>
          ) : null}
          {createReplay.isError && !replayConflict ? <Alert severity="error">{createReplay.error.message}</Alert> : null}
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
          <Typography id="simulation-results-heading" variant="h2">3 · Research and operations</Typography>
          <Typography variant="body2" color="text.secondary">
            Server-owned evaluation metrics stay separate from the raw telemetry diagnostic below.
          </Typography>
        </Stack>
        {activeModel === undefined ? (
          <PanelSkeleton label="Loading selected model" />
        ) : metrics.data === undefined ? (
          metrics.isError ? (
            missingReplay ? (
              <Paper variant="outlined" sx={{ p: 4 }}>
                <EmptyState
                  title="No replay data for this model yet"
                  detail={`${activeModel.display_name} has no inference results on the simulation device. Run the full-corpus replay to generate them.`}
                />
              </Paper>
            ) : (
              <ApiErrorPanel error={metrics.error} onRetry={() => void metrics.refetch()} />
            )
          ) : (
            <PanelSkeleton label="Loading server detection metrics" />
          )
        ) : (
          <Stack spacing={3}>
            <SimulationMetricsPanels metrics={metrics.data} />
            {injections.data === undefined || corpusWindow === undefined ? (
              injections.isError ? (
                <ApiErrorPanel error={injections.error} onRetry={() => void injections.refetch()} />
              ) : (
                <PanelSkeleton label="Loading full injection corpus" />
              )
            ) : injections.data.events.length === 0 ? (
              <Paper variant="outlined" sx={{ p: 4 }}>
                <EmptyState title="No injection events" detail="The simulation corpus returned no ground-truth events." />
              </Paper>
            ) : (
              <ReplayVisualization
                model={activeModel}
                injections={injections.data.events}
                corpusWindow={corpusWindow}
              />
            )}
          </Stack>
        )}
      </Stack>
    </Stack>
  )
}
