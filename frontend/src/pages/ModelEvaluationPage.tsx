import { Alert, Paper, Stack, Typography } from '@mui/material'
import { ApiErrorPanel } from '../components/states/ApiErrorPanel'
import { PanelSkeleton } from '../components/states/PanelSkeleton'
import { useModelEvaluationsQuery } from '../features/modelEvaluation/queries'
import { ModelRegistryPanel } from '../features/preview/ModelRegistryPanel'
import { ReplayPanel } from '../features/preview/ReplayPanel'

export function ModelEvaluationPage() {
  const pilot = useModelEvaluationsQuery({ page: 1, pageSize: 25 })

  return (
    <Stack spacing={6}>
      <Stack spacing={0.5}>
        <Typography variant="h1">Model Evaluation</Typography>
        <Typography color="text.secondary">Registry preview dan snapshot evaluasi Dandy dipisahkan.</Typography>
      </Stack>

      <ModelRegistryPanel />

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
