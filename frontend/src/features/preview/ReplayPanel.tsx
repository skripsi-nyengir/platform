import {
  Alert,
  Button,
  LinearProgress,
  Link,
  Paper,
  Stack,
  TextField,
  Typography,
} from '@mui/material'
import { Link as RouterLink } from 'react-router-dom'
import { useState } from 'react'
import { randomId } from '../../lib/id'
import { publicDeviceId } from '../../contracts/common'
import { ReplayJobRequestSchema } from '../../contracts/preview'
import { useCreateReplayMutation, useModelsQuery, useReplayJobQuery } from './queries'
import { ProvenanceBadge } from '../../components/data/ProvenanceBadge'

export function ReplayPanel() {
  const models = useModelsQuery(publicDeviceId)
  const createReplay = useCreateReplayMutation()
  const [from, setFrom] = useState<string>('2026-02-01T00:00:00')
  const [to, setTo] = useState<string>('2026-03-01T00:00:00')
  const [commandId, setCommandId] = useState(() => randomId())
  const [jobId, setJobId] = useState<string>()
  const status = useReplayJobQuery(jobId)
  const validation = ReplayJobRequestSchema.safeParse({
    command_id: commandId,
    device_id: publicDeviceId,
    from,
    to,
  })
  const job = status.data?.job ?? createReplay.data?.job
  const terminal = job?.status === 'succeeded' || job?.status === 'failed'

  return (
    <Paper component="section" aria-labelledby="replay-heading" variant="outlined" sx={{ p: 4 }}>
      <Stack spacing={2}>
        <Stack spacing={0.5}>
          <Typography id="replay-heading" variant="h2">Preview replay</Typography>
          <Typography color="text.secondary">
            Interval setengah-terbuka [from,to), maksimum 31 hari · Asia/Jakarta (WIB)
          </Typography>
          <Typography color="text.secondary">
            Snapshot model: {models.data?.active_model_version ?? 'Memuat pilihan…'}
          </Typography>
        </Stack>
        <Stack direction="row" spacing={2} useFlexGap sx={{ flexWrap: 'wrap' }}>
          <TextField label="From (WIB)" value={from} onChange={(event) => {
            setFrom(event.target.value)
            setCommandId(randomId())
          }} />
          <TextField label="To (WIB)" value={to} onChange={(event) => {
            setTo(event.target.value)
            setCommandId(randomId())
          }} />
          <Button
            variant="contained"
            disabled={!validation.success || createReplay.isPending || (job !== undefined && !terminal)}
            onClick={() => {
              if (!validation.success) return
              createReplay.mutate(validation.data, {
                onSuccess: (response) => setJobId(response.job.job_id),
              })
            }}
          >
            Jalankan replay
          </Button>
        </Stack>
        {!validation.success ? (
          <Alert severity="warning">{validation.error.issues[0]?.message}</Alert>
        ) : null}
        {createReplay.isError ? <Alert severity="error">{createReplay.error.message}</Alert> : null}
        {job === undefined ? null : (
          <Stack role="status" aria-label="Replay progress" spacing={1}>
            <Typography>
              {job.status} · {Math.round(job.progress * 100)}% · {job.model_version}
            </Typography>
            <ProvenanceBadge provenance={job.score_provenance} />
            <LinearProgress variant="determinate" value={job.progress * 100} />
            <Typography variant="body2" color="text.secondary">
              {job.processed_count} diproses · {job.result_count} hasil · {job.episode_count} episode
            </Typography>
            {job.status === 'failed' ? (
              <Alert severity="error">{job.error_detail ?? job.error_code ?? 'Replay gagal'}</Alert>
            ) : null}
            {job.status === 'succeeded' ? (
              <Link
                component={RouterLink}
                to={`/sensors/${publicDeviceId}?sensor=${publicDeviceId}&from=${encodeURIComponent(job.from)}&to=${encodeURIComponent(job.to)}&model_version=${encodeURIComponent(job.model_version)}`}
              >
                Lihat hasil replay
              </Link>
            ) : null}
          </Stack>
        )}
      </Stack>
    </Paper>
  )
}
