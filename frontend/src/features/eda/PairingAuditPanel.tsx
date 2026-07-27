import { Alert, Box, Paper, Stack, Typography } from '@mui/material'
import { useTheme } from '@mui/material/styles'
import { BarChart } from '@mui/x-charts/BarChart'
import { buildPairingAuditData } from '../../components/charts/edaV3Options'
import { ApiErrorPanel } from '../../components/states/ApiErrorPanel'
import { EmptyState } from '../../components/states/EmptyState'
import { PanelSkeleton } from '../../components/states/PanelSkeleton'
import { tokens } from '../../theme/tokens'
import { useEdaSectionQuery } from './queries'
import { formatEdaReasonDetail } from './reasonLabels'

export interface PairingAuditPanelProps {
  runId: string | null
}

export function PairingAuditPanel({ runId }: PairingAuditPanelProps) {
  const theme = useTheme()
  const query = useEdaSectionQuery(runId, 'quality_overview')
  const response = query.data
  const data = response?.status === 'complete' && response.section === 'quality_overview'
    ? buildPairingAuditData(response.payload, theme)
    : null

  return (
    <Paper component="section" aria-labelledby="pairing-audit-title" variant="outlined" sx={{ minWidth: 0, p: 4 }}>
      <Stack spacing={2} sx={{ minWidth: 0 }}>
        <Typography id="pairing-audit-title" variant="h2">Audit pairing timestamp</Typography>
        {runId === null ? (
          <EmptyState title="Pilih hasil EDA" detail="Audit pairing tersedia setelah satu run dipilih." />
        ) : query.isError ? (
          <ApiErrorPanel error={query.error} onRetry={() => void query.refetch()} />
        ) : response === undefined ? (
          <PanelSkeleton label="Memuat audit pairing" />
        ) : response.status === 'not_eligible' ? (
          <Alert severity="info" role="status">
            <strong>Audit pairing belum memenuhi syarat.</strong><br />{formatEdaReasonDetail(response.reason_code, response.detail)}
          </Alert>
        ) : response.status === 'failed' ? (
          <Alert severity="error" role="alert">
            <strong>Audit pairing gagal dihitung.</strong><br />{response.detail}
          </Alert>
        ) : data === null || data.bars.every((bar) => bar.total === 0) ? (
          <EmptyState title="Data pairing kosong" detail="Run tidak memuat timestamp atau pasangan exact yang dapat diaudit." />
        ) : (
          <>
            <Box
              role="img"
              aria-label="Batang bertumpuk audit timestamp dan pasangan"
              aria-description="Dua batang 100 persen membandingkan komposisi union timestamp dan pasangan exact. Pasangan yang dikecualikan adalah hasil aturan kualitas, bukan anomali."
              sx={{ minWidth: 0 }}
            >
              <BarChart
                id="pairing-audit-chart"
                title="Audit pairing timestamp"
                desc="Komposisi union timestamp dan pasangan exact dalam persen."
                disableKeyboardNavigation
                height={tokens.size.control * 6}
                layout="horizontal"
                skipAnimation
                xAxis={[{
                  id: 'pairing-percent-axis',
                  label: 'Persen dari total bar',
                  min: 0,
                  max: 100,
                }]}
                yAxis={[{
                  id: 'pairing-category-axis',
                  data: data.bars.map((bar) => bar.label),
                  scaleType: 'band',
                }]}
                series={data.bars.flatMap((bar) => bar.segments).map((segment) => ({
                  id: segment.id,
                  label: segment.label,
                  data: data.bars.map((bar) => (
                    bar.segments.find((candidate) => candidate.id === segment.id)?.percent ?? 0
                  )),
                  color: segment.color,
                  stack: 'pairing-audit',
                  valueFormatter: (value: number | null) => value === null ? null : `${value.toFixed(2)}%`,
                  xAxisId: 'pairing-percent-axis',
                  yAxisId: 'pairing-category-axis',
                }))}
              />
            </Box>
            <Box
              sx={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(min(320px, 100%), 1fr))',
                gap: 2,
                minWidth: 0,
              }}
            >
              {data.bars.map((bar) => (
                <Paper key={bar.id} component="article" variant="outlined" sx={{ minWidth: 0, p: 2 }}>
                  <Typography variant="h3">{bar.label}</Typography>
                  <Typography variant="body2" color="text.secondary">
                    Total <Box component="span" sx={{ fontFamily: tokens.font.data }}>{bar.total.toLocaleString('id-ID')}</Box>
                  </Typography>
                  {bar.segments.map((segment) => (
                    <Typography key={segment.id} variant="body2">
                      {segment.label}: <Box component="span" sx={{ fontFamily: tokens.font.data }}>
                        {segment.count.toLocaleString('id-ID')} ({segment.percent.toFixed(2)}%)
                      </Box>
                    </Typography>
                  ))}
                </Paper>
              ))}
            </Box>
            <Alert severity={data.conservationStatus === 'pass' ? 'success' : 'error'} role="status">
              <strong>Konservasi hitungan: {data.conservationStatus.toUpperCase()}</strong>
              <br />Status ini diaudit terpisah dari komposisi batang.
            </Alert>
          </>
        )}
      </Stack>
    </Paper>
  )
}
