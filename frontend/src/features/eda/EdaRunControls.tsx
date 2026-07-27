import {
  Alert,
  Button,
  FormControl,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  Stack,
  TextField,
} from '@mui/material'
import { useQueryClient } from '@tanstack/react-query'
import { useEffect, useId, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { ApiErrorPanel } from '../../components/states/ApiErrorPanel'
import { EmptyState } from '../../components/states/EmptyState'
import { PanelSkeleton } from '../../components/states/PanelSkeleton'
import {
  EdaComputeRequestSchema,
  EdaPrecomputedPeriodKindSchema,
  type EdaPeriodListResponse,
  type EdaRunSummary,
} from '../../contracts/eda'
import {
  parseEdaUrlState,
  updateEdaUrlState,
  type EdaUrlState,
} from '../filters/urlFilters'
import {
  edaQueryKeys,
  useEdaComputeMutation,
  useEdaJobQuery,
  useEdaPeriodsQuery,
  useEdaRunQuery,
} from './queries'

export interface EdaRunControlsProps {
  onRunSelected: (run: EdaRunSummary | null) => void
}

type PeriodKind = EdaUrlState['periodKind']
type CustomRange = Pick<EdaUrlState, 'from' | 'to'>

const periodLabels: Record<PeriodKind, string> = {
  daily: 'Harian',
  weekly: 'Mingguan',
  monthly: 'Bulanan',
}

function initialSelection(
  monthly: EdaPeriodListResponse,
  weekly: EdaPeriodListResponse,
  daily: EdaPeriodListResponse,
): { periodKind: PeriodKind; run: EdaRunSummary } | null {
  if (monthly.items[0] !== undefined) return { periodKind: 'monthly', run: monthly.items[0] }
  if (weekly.items[0] !== undefined) return { periodKind: 'weekly', run: weekly.items[0] }
  if (daily.items[0] !== undefined) return { periodKind: 'daily', run: daily.items[0] }
  return null
}

function periodOptionLabel(run: EdaRunSummary): string {
  return `${run.scope.from} – ${run.scope.to}`
}

function parseCustomRange(range: CustomRange) {
  const normalize = (value: string) => value.length === 16 ? `${value}:00` : value
  return EdaComputeRequestSchema.safeParse({
    device_id: 'b02f3872-39a2-4b6f-a4ec-045a287fde4b',
    time_zone: 'Asia/Jakarta',
    period_kind: 'custom',
    from: normalize(range.from),
    to: normalize(range.to),
  })
}

export function EdaRunControls({ onRunSelected }: EdaRunControlsProps) {
  const modeLabelId = useId()
  const periodKindLabelId = useId()
  const periodLabelId = useId()
  const [params, setParams] = useSearchParams()
  const urlState = parseEdaUrlState(params)
  const queryClient = useQueryClient()
  const initialSelectionDone = useRef(urlState.runId !== undefined || urlState.mode === 'custom')
  const publishedJobId = useRef<string | null>(null)
  const [jobId, setJobId] = useState<string | null>(null)
  const [customRange, setCustomRange] = useState({ from: urlState.from, to: urlState.to })
  const [syncedRange, setSyncedRange] = useState({ from: urlState.from, to: urlState.to })
  const monthly = useEdaPeriodsQuery({ period_kind: 'monthly' })
  const weekly = useEdaPeriodsQuery({ period_kind: 'weekly' })
  const daily = useEdaPeriodsQuery({ period_kind: 'daily' })
  const runQuery = useEdaRunQuery(urlState.runId ?? null)
  const compute = useEdaComputeMutation()
  const jobQuery = useEdaJobQuery(jobId)

  const periodQueries = { daily, weekly, monthly }
  const selectedPeriods = periodQueries[urlState.periodKind]
  const periodListsReady = monthly.isSuccess && weekly.isSuccess && daily.isSuccess
  const periodError = monthly.error ?? weekly.error ?? daily.error
  const selectedRun = runQuery.data?.run
  const job = jobQuery.data?.job
  const jobIsActive = job?.status === 'queued' || job?.status === 'running'
  const submitIsLocked = compute.isPending || (jobId !== null && (job === undefined || jobIsActive))
  const computeRequest = parseCustomRange(customRange)
  const customRangeIsDirty = urlState.mode === 'custom' && (
    customRange.from !== urlState.from ||
    customRange.to !== urlState.to ||
    selectedRun?.scope.period_kind !== 'custom' ||
    selectedRun.scope.from !== urlState.from ||
    selectedRun.scope.to !== urlState.to
  )

  // Render-phase sync, not an effect (cascading renders) and not a `key` remount:
  // `jobId` lives here and a remount would drop it mid-poll.
  if (syncedRange.from !== urlState.from || syncedRange.to !== urlState.to) {
    setSyncedRange({ from: urlState.from, to: urlState.to })
    setCustomRange({ from: urlState.from, to: urlState.to })
  }

  useEffect(() => {
    if (initialSelectionDone.current || urlState.mode !== 'precompute' || !periodListsReady) return
    initialSelectionDone.current = true
    const selection = initialSelection(monthly.data, weekly.data, daily.data)
    if (selection === null) {
      onRunSelected(null)
      setParams(updateEdaUrlState(params, {
        mode: 'precompute',
        periodKind: urlState.periodKind,
        from: urlState.from,
        to: urlState.to,
        runId: undefined,
      }), { replace: true })
      return
    }
    onRunSelected(selection.run)
    setParams(updateEdaUrlState(params, {
      mode: 'precompute',
      periodKind: selection.periodKind,
      from: urlState.from,
      to: urlState.to,
      runId: selection.run.run_id,
    }), { replace: true })
  }, [
    daily.data,
    monthly.data,
    onRunSelected,
    params,
    periodListsReady,
    setParams,
    urlState.mode,
    urlState.from,
    urlState.periodKind,
    urlState.to,
    weekly.data,
  ])

  useEffect(() => {
    if (runQuery.data !== undefined) onRunSelected(runQuery.data.run)
  }, [onRunSelected, runQuery.data])

  useEffect(() => {
    if (
      job?.status !== 'succeeded' ||
      job.run_id === null ||
      publishedJobId.current === job.job_id
    ) return
    publishedJobId.current = job.job_id
    setParams(updateEdaUrlState(params, { mode: 'custom', runId: job.run_id }))
  }, [job, params, setParams])

  const selectRun = (run: EdaRunSummary | undefined, patch: Partial<EdaUrlState>) => {
    initialSelectionDone.current = true
    onRunSelected(run ?? null)
    setParams(updateEdaUrlState(params, {
      ...patch,
      runId: run?.run_id,
    }))
  }

  const handleModeChange = (mode: EdaUrlState['mode']) => {
    if (mode === 'custom') {
      setParams(updateEdaUrlState(params, { mode }))
      return
    }
    selectRun(selectedPeriods.data?.items[0], { mode })
  }

  const handlePeriodKindChange = (value: unknown) => {
    const parsed = EdaPrecomputedPeriodKindSchema.safeParse(value)
    if (!parsed.success) return
    const periods = periodQueries[parsed.data].data
    selectRun(periods?.items[0], { mode: 'precompute', periodKind: parsed.data })
  }

  const updateCustomRange = (field: 'from' | 'to', inputValue: string) => {
    const next = { ...customRange, [field]: inputValue }
    setCustomRange(next)
    const parsed = parseCustomRange(next)
    if (!parsed.success) return
    setParams(updateEdaUrlState(params, {
      from: parsed.data.from,
      to: parsed.data.to,
    }))
  }

  const submitCustomRange = async () => {
    if (!computeRequest.success || submitIsLocked) return
    setJobId(null)
    const response = await compute.mutateAsync(computeRequest.data).catch(() => null)
    if (response === null) return
    if (response.cache_hit) {
      queryClient.setQueryData(edaQueryKeys.run(response.run.run_id), {
        request_id: response.request_id,
        run: response.run,
      })
      onRunSelected(response.run)
      setParams(updateEdaUrlState(params, {
        mode: 'custom',
        runId: response.run.run_id,
      }))
      return
    }
    queryClient.setQueryData(edaQueryKeys.job(response.job.job_id), {
      request_id: response.request_id,
      job: response.job,
    })
    setJobId(response.job.job_id)
  }

  return (
    <Paper variant="outlined" sx={{ p: 3 }}>
      <Stack spacing={2} role="group" aria-label="Kontrol run EDA">
        <Stack direction="row" spacing={2} useFlexGap sx={{ flexWrap: 'wrap' }}>
          <FormControl size="small" sx={{ minWidth: 180 }}>
            <InputLabel id={modeLabelId}>Mode</InputLabel>
            <Select
              labelId={modeLabelId}
              label="Mode"
              value={urlState.mode}
              onChange={(event) => handleModeChange(event.target.value as EdaUrlState['mode'])}
            >
              <MenuItem value="precompute">Precompute</MenuItem>
              <MenuItem value="custom">Rentang kustom</MenuItem>
            </Select>
          </FormControl>

          {urlState.mode === 'precompute' ? (
            <>
              <FormControl size="small" sx={{ minWidth: 180 }} disabled={!periodListsReady}>
                <InputLabel id={periodKindLabelId}>Jenis periode</InputLabel>
                <Select
                  labelId={periodKindLabelId}
                  label="Jenis periode"
                  value={urlState.periodKind}
                  onChange={(event) => handlePeriodKindChange(event.target.value)}
                >
                  {EdaPrecomputedPeriodKindSchema.options.map((kind) => (
                    <MenuItem key={kind} value={kind}>{periodLabels[kind]}</MenuItem>
                  ))}
                </Select>
              </FormControl>
              <FormControl
                size="small"
                sx={{ flexGrow: { xs: 1, sm: 0 }, maxWidth: '100%', minWidth: { xs: 0, sm: 320 } }}
                disabled={!periodListsReady}
              >
                <InputLabel id={periodLabelId}>Periode tersedia</InputLabel>
                <Select
                  labelId={periodLabelId}
                  label="Periode tersedia"
                  value={selectedPeriods.data?.items.some((run) => run.run_id === urlState.runId)
                    ? urlState.runId
                    : ''}
                  onChange={(event) => {
                    const run = selectedPeriods.data?.items.find((item) => item.run_id === event.target.value)
                    selectRun(run, { mode: 'precompute' })
                  }}
                >
                  {selectedPeriods.data?.items.map((run) => (
                    <MenuItem key={run.run_id} value={run.run_id}>{periodOptionLabel(run)}</MenuItem>
                  ))}
                </Select>
              </FormControl>
            </>
          ) : (
            <>
              <TextField
                size="small"
                label="Dari"
                type="datetime-local"
                key={`from-${urlState.from}`}
                defaultValue={urlState.from}
                slotProps={{ htmlInput: { step: 1 } }}
                onChange={(event) => updateCustomRange('from', event.target.value)}
              />
              <TextField
                size="small"
                label="Sampai"
                type="datetime-local"
                key={`to-${urlState.to}`}
                defaultValue={urlState.to}
                slotProps={{ htmlInput: { step: 1 } }}
                onChange={(event) => updateCustomRange('to', event.target.value)}
              />
              <Button
                variant="contained"
                disabled={!computeRequest.success || submitIsLocked}
                onClick={() => void submitCustomRange()}
              >
                Hitung EDA
              </Button>
            </>
          )}
        </Stack>

        {urlState.mode === 'precompute' && !periodListsReady && periodError === null ? (
          <PanelSkeleton label="Memuat periode EDA" />
        ) : null}
        {urlState.mode !== 'precompute' || periodError === null ? null : (
          <ApiErrorPanel
            error={periodError}
            onRetry={() => {
              if (monthly.isError) void monthly.refetch()
              if (weekly.isError) void weekly.refetch()
              if (daily.isError) void daily.refetch()
            }}
          />
        )}
        {urlState.mode === 'precompute' && periodListsReady && urlState.runId === undefined ? (
          <EmptyState
            title="Belum ada hasil EDA precompute"
            detail="Pilih jenis periode lain atau gunakan Rentang kustom lalu tekan Hitung EDA."
          />
        ) : null}
        {urlState.runId !== undefined && runQuery.isPending ? (
          <PanelSkeleton label="Memuat run EDA" />
        ) : null}
        {runQuery.error === null ? null : (
          <ApiErrorPanel error={runQuery.error} onRetry={() => void runQuery.refetch()} />
        )}
        {customRangeIsDirty ? (
          <Alert severity="warning" role="status">Rentang belum dihitung. Hasil yang tampil masih menggunakan run sebelumnya.</Alert>
        ) : null}
        {jobId !== null && job === undefined && !jobQuery.isError ? (
          <PanelSkeleton label="Memeriksa status perhitungan EDA" />
        ) : null}
        {jobIsActive ? (
          <Alert severity="info" role="status">
            Status perhitungan EDA: {job.status === 'queued' ? 'queued' : 'running'}
          </Alert>
        ) : null}
        {job?.status === 'failed' ? (
          <Alert
            severity="error"
            role="alert"
            action={<Button color="inherit" onClick={() => void submitCustomRange()}>Retry</Button>}
          >
            {job.error_detail}
          </Alert>
        ) : null}
        {jobQuery.error === null ? null : (
          <ApiErrorPanel error={jobQuery.error} onRetry={() => void jobQuery.refetch()} />
        )}
        {compute.error === null ? null : (
          <ApiErrorPanel error={compute.error} onRetry={() => void submitCustomRange()} />
        )}
      </Stack>
    </Paper>
  )
}
