import {
  Alert,
  Box,
  Chip,
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
import {
  buildDomainFateData,
  buildQualityIntegrityData,
  DOMAIN_LABELS,
  formatFinitePercent,
  type DomainKey,
} from '../../components/charts/edaV3Options'
import { ApiErrorPanel } from '../../components/states/ApiErrorPanel'
import { EmptyState } from '../../components/states/EmptyState'
import { PanelSkeleton } from '../../components/states/PanelSkeleton'
import { tokens } from '../../theme/tokens'
import { useEdaSectionQuery } from './queries'
import { formatEdaReasonDetail } from './reasonLabels'

const domainKeys: readonly DomainKey[] = ['underflow', 'in_domain', 'overflow']

export interface QualityIntegrityPanelProps {
  runId: string | null
}

export function QualityIntegrityPanel({ runId }: QualityIntegrityPanelProps) {
  const theme = useTheme()
  const query = useEdaSectionQuery(runId, 'quality_overview')
  const response = query.data
  const payload = response?.status === 'complete' && response.section === 'quality_overview'
    ? response.payload
    : null
  const domainTables = payload === null ? [] : buildDomainFateData(payload, theme)
  const integrity = payload === null ? null : buildQualityIntegrityData(payload)

  return (
    <Paper component="section" aria-labelledby="quality-integrity-title" variant="outlined" sx={{ minWidth: 0, p: 4 }}>
      <Stack spacing={2} sx={{ minWidth: 0 }}>
        <Typography id="quality-integrity-title" variant="h2">Integritas kualitas</Typography>
        {runId === null ? (
          <EmptyState title="Pilih hasil EDA" detail="Audit domain, duplikat, dan cadence tersedia setelah satu run dipilih." />
        ) : query.isError ? (
          <ApiErrorPanel error={query.error} onRetry={() => void query.refetch()} />
        ) : response === undefined ? (
          <PanelSkeleton label="Memuat integritas kualitas" />
        ) : response.status === 'not_eligible' ? (
          <Alert severity="info" role="status">
            <strong>Integritas kualitas belum memenuhi syarat.</strong><br />{formatEdaReasonDetail(response.reason_code, response.detail)}
          </Alert>
        ) : response.status === 'failed' ? (
          <Alert severity="error" role="alert">
            <strong>Integritas kualitas gagal dihitung.</strong><br />{response.detail}
          </Alert>
        ) : domainTables.length === 0 || integrity === null ? (
          <EmptyState title="Audit integritas kosong" detail="Matriks domain atau hitungan audit tidak tersedia pada run ini." />
        ) : (
          <>
            <Box
              role="group"
              aria-label="Matriks fate domain raw dan screened"
              sx={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(min(320px, 100%), 1fr))',
                gap: 4,
                minWidth: 0,
              }}
            >
              {domainTables.map((table) => (
                <Paper key={table.id} component="article" variant="outlined" sx={{ minWidth: 0, p: 2 }}>
                  <Stack spacing={1} sx={{ minWidth: 0 }}>
                    <Typography variant="h3">Fate domain — {table.label}</Typography>
                    <Typography variant="body2" color="text.secondary">
                      Total {table.totalPairs.toLocaleString('id-ID')}; non-finite {table.nonFinitePairs.toLocaleString('id-ID')}; excluded {table.excludedPairs.toLocaleString('id-ID')} pasangan.
                    </Typography>
                    <TableContainer>
                      <Table size="small" aria-label={`Fate domain ${table.label}`}>
                        <TableHead>
                          <TableRow>
                            <TableCell rowSpan={2} scope="col">Status Suhu</TableCell>
                            <TableCell colSpan={3} scope="colgroup" align="center">Status RH</TableCell>
                          </TableRow>
                          <TableRow>
                            {domainKeys.map((key) => <TableCell key={key} scope="col" align="center">{DOMAIN_LABELS[key]}</TableCell>)}
                          </TableRow>
                        </TableHead>
                        <TableBody>
                          {table.cells.map((row, rowIndex) => (
                            <TableRow key={domainKeys[rowIndex]}>
                              <TableCell component="th" scope="row">{DOMAIN_LABELS[domainKeys[rowIndex]]}</TableCell>
                              {row.map((cell) => (
                                <TableCell
                                  key={`${cell.temperature}-${cell.humidity}`}
                                  align="center"
                                  aria-label={`Suhu ${DOMAIN_LABELS[cell.temperature]}, RH ${DOMAIN_LABELS[cell.humidity]}: ${cell.count}`}
                                  sx={{
                                    backgroundColor: cell.backgroundColor,
                                    color: cell.textColor,
                                    fontFamily: tokens.font.data,
                                    fontVariantNumeric: 'tabular-nums',
                                  }}
                                >
                                  {cell.count.toLocaleString('id-ID')}
                                </TableCell>
                              ))}
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </TableContainer>
                  </Stack>
                </Paper>
              ))}
            </Box>
            <Box
              role="group"
              aria-label="KPI duplikat dengan penyebut terpisah"
              sx={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(min(320px, 100%), 1fr))',
                gap: 4,
                minWidth: 0,
              }}
            >
              {([
                { title: 'Grup duplikat', metric: integrity.duplicateGroups },
                { title: 'Pasangan duplikat konflik', metric: integrity.conflictingPairs },
              ] as const).map(({ title, metric }) => (
                <Paper key={title} component="article" variant="outlined" sx={{ minWidth: 0, p: 4 }}>
                  <Typography variant="h3">{title}</Typography>
                  <Typography variant="h2" sx={{ fontFamily: tokens.font.data, mt: 1 }}>
                    {metric.count.toLocaleString('id-ID')}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    {formatFinitePercent(metric.count, metric.denominator)} dari {metric.denominator.toLocaleString('id-ID')} {metric.denominatorLabel}.
                  </Typography>
                </Paper>
              ))}
            </Box>
            <Paper component="article" variant="outlined" sx={{ minWidth: 0, p: 4 }}>
              <Stack spacing={2} sx={{ minWidth: 0 }}>
                <Stack direction="row" spacing={1} useFlexGap sx={{ alignItems: 'center', flexWrap: 'wrap' }}>
                  <Typography variant="h3" sx={{ flexGrow: 1 }}>Cadence pasangan</Typography>
                  <Chip
                    size="small"
                    color={integrity.cadence.status === 'pass' ? 'success' : 'error'}
                    label={`Gate ${integrity.cadence.status.toUpperCase()}`}
                  />
                </Stack>
                <Box
                  role="img"
                  aria-label={`Cadence median ${integrity.cadence.observedMedianSeconds} detik; referensi 6 detik; interval diterima 5 sampai 7 detik`}
                  sx={{ minWidth: 0 }}
                >
                  <Box sx={{ bgcolor: 'divider', height: tokens.spacing.unit * 4, position: 'relative' }}>
                    <Box
                      aria-hidden="true"
                      sx={{
                        bgcolor: 'success.main',
                        height: '100%',
                        left: `${integrity.cadence.acceptanceLeftPercent}%`,
                        opacity: 0.35,
                        position: 'absolute',
                        width: `${integrity.cadence.acceptanceWidthPercent}%`,
                      }}
                    />
                    <Box
                      aria-hidden="true"
                      sx={{
                        bgcolor: 'text.primary',
                        height: tokens.size.control,
                        left: `${integrity.cadence.expectedPositionPercent}%`,
                        position: 'absolute',
                        top: '50%',
                        transform: 'translate(-50%, -50%)',
                        width: tokens.size.rule,
                      }}
                    />
                    <Box
                      aria-hidden="true"
                      sx={{
                        bgcolor: integrity.cadence.status === 'pass' ? 'success.main' : 'error.main',
                        borderRadius: '50%',
                        height: tokens.spacing.unit * 3,
                        left: `${integrity.cadence.observedPositionPercent}%`,
                        position: 'absolute',
                        top: '50%',
                        transform: 'translate(-50%, -50%)',
                        width: tokens.spacing.unit * 3,
                      }}
                    />
                  </Box>
                  <Stack direction="row" sx={{ justifyContent: 'space-between' }}>
                    <Typography variant="caption">0 dtk</Typography>
                    <Typography variant="caption">Diterima 5–7 dtk · referensi 6 dtk</Typography>
                    <Typography variant="caption">{integrity.cadence.displayMaximumSeconds} dtk</Typography>
                  </Stack>
                </Box>
                <Typography variant="body2" color="text.secondary">
                  Median teramati <Box component="span" sx={{ fontFamily: tokens.font.data }}>{integrity.cadence.observedMedianSeconds} dtk</Box>. Gap di atas {integrity.cadence.primaryGapSeconds} detik: <Box component="span" sx={{ fontFamily: tokens.font.data }}>{integrity.cadence.gapCount.toLocaleString('id-ID')}</Box>.
                </Typography>
              </Stack>
            </Paper>
          </>
        )}
      </Stack>
    </Paper>
  )
}
