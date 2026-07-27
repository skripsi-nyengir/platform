import { Alert, Box, Paper, Stack, Typography } from '@mui/material'
import { useTheme } from '@mui/material/styles'
import { CanvasHeatmap } from '../../components/charts/CanvasHeatmap'
import { buildJointDensityData } from '../../components/charts/edaV3Options'
import { ApiErrorPanel } from '../../components/states/ApiErrorPanel'
import { EmptyState } from '../../components/states/EmptyState'
import { PanelSkeleton } from '../../components/states/PanelSkeleton'
import { tokens } from '../../theme/tokens'
import { useEdaSectionQuery } from './queries'
import { formatEdaReasonDetail } from './reasonLabels'

export interface JointDensityPanelProps {
  runId: string | null
}

export function JointDensityPanel({ runId }: JointDensityPanelProps) {
  const theme = useTheme()
  const query = useEdaSectionQuery(runId, 'joint_density')
  const response = query.data
  const data = response?.status === 'complete' && response.section === 'joint_density'
    ? buildJointDensityData(response.payload, response.sample_counts, theme)
    : null

  return (
    <Paper component="section" aria-labelledby="joint-density-title" variant="outlined" sx={{ minWidth: 0, p: 4 }}>
      <Stack spacing={2} sx={{ minWidth: 0 }}>
        <Typography id="joint-density-title" variant="h2">Kepadatan gabungan Suhu–RH</Typography>
        {runId === null ? (
          <EmptyState title="Pilih hasil EDA" detail="Kepadatan gabungan tersedia setelah satu run dipilih." />
        ) : query.isError ? (
          <ApiErrorPanel error={query.error} onRetry={() => void query.refetch()} />
        ) : response === undefined ? (
          <PanelSkeleton label="Memuat kepadatan gabungan" />
        ) : response.status === 'not_eligible' ? (
          <Alert severity="info" role="status">
            <strong>Kepadatan gabungan belum memenuhi syarat.</strong><br />{formatEdaReasonDetail(response.reason_code, response.detail)}
          </Alert>
        ) : response.status === 'failed' ? (
          <Alert severity="error" role="alert">
            <strong>Kepadatan gabungan gagal dihitung.</strong><br />{response.detail}
          </Alert>
        ) : data === null ? (
          <EmptyState title="Matriks kepadatan kosong" detail="Run tidak memuat sel kepadatan yang dapat ditampilkan." />
        ) : (
          <>
            <Typography variant="body2" color="text.secondary">
              Matriks statis {data.temperatureEdges.length - 1} × {data.humidityEdges.length - 1} bin memakai satu skala warna bersama. Nilai di luar domain tidak di-clipping dan diaudit pada panel integritas.
            </Typography>
            <Box
              role="group"
              aria-label="Kepadatan gabungan raw dan screened"
              sx={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(min(320px, 100%), 1fr))',
                gap: 4,
                minWidth: 0,
              }}
            >
              {data.views.map((view) => (
                <CanvasHeatmap
                  key={view.id}
                  title={`${view.label} — n=${view.pairCount.toLocaleString('id-ID')}`}
                  description={`${view.label}, Suhu pada sumbu horizontal dan RH pada sumbu vertikal. ${data.temperatureEdges.length - 1} × ${data.humidityEdges.length - 1} sel; skala warna logaritmik bersama dengan maksimum ${data.maximumCount.toLocaleString('id-ID')} pasangan per sel.`}
                  temperatureEdges={data.temperatureEdges}
                  humidityEdges={data.humidityEdges}
                  matrix={view.matrix}
                  maximumCount={data.maximumCount}
                  colors={data.colors}
                />
              ))}
            </Box>
            <Alert severity="info" role="note" sx={{ '& code': { fontFamily: tokens.font.data } }}>
              Indikator kandidat kualitas; kepadatan dan pasangan yang dikecualikan bukan label anomali atau bukti kausal.
            </Alert>
          </>
        )}
      </Stack>
    </Paper>
  )
}
