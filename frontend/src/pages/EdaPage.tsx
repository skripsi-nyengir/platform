import {
  Alert,
  Box,
  Chip,
  Link,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableRow,
  Typography,
} from '@mui/material'
import { useState } from 'react'
import { ApiError } from '../api/errors'
import { ProvenanceBadge } from '../components/data/ProvenanceBadge'
import { ApiErrorPanel } from '../components/states/ApiErrorPanel'
import { EmptyState } from '../components/states/EmptyState'
import { PanelSkeleton } from '../components/states/PanelSkeleton'
import type { EdaRunSummary } from '../contracts/eda'
import { AssociationSummaryPanel } from '../features/eda/AssociationSummaryPanel'
import { AutocorrelationPanel } from '../features/eda/AutocorrelationPanel'
import { BootstrapUncertaintyPanel } from '../features/eda/BootstrapUncertaintyPanel'
import { ChangePointPanel } from '../features/eda/ChangePointPanel'
import { EdaRunControls } from '../features/eda/EdaRunControls'
import { JointDensityPanel } from '../features/eda/JointDensityPanel'
import { PairingAuditPanel } from '../features/eda/PairingAuditPanel'
import { QualityExcerptPanel } from '../features/eda/QualityExcerptPanel'
import { QualityIntegrityPanel } from '../features/eda/QualityIntegrityPanel'
import { useEdaSectionQuery } from '../features/eda/queries'
import { formatEdaReasonDetail } from '../features/eda/reasonLabels'
import { RollingCorrelationPanel } from '../features/eda/RollingCorrelationPanel'
import { SpectrumPanel } from '../features/eda/SpectrumPanel'
import { StationarityEligibilityPanel } from '../features/eda/StationarityEligibilityPanel'
import { StlDecompositionPanel } from '../features/eda/StlDecompositionPanel'
import { TemporalCoveragePanel } from '../features/eda/TemporalCoveragePanel'
import { TemporalDistributionPanel } from '../features/eda/TemporalDistributionPanel'
import { UnivariateDiagnosticsPanel } from '../features/eda/UnivariateDiagnosticsPanel'
import { WeekdayHourCoveragePanel } from '../features/eda/WeekdayHourCoveragePanel'
import { tokens } from '../theme/tokens'

const anchors = [
  { id: 'kualitas-data', label: 'Kualitas Data' },
  { id: 'pola-temporal', label: 'Pola Temporal' },
  { id: 'hubungan-suhu-rh', label: 'Hubungan Suhu-RH' },
  { id: 'struktur-temporal', label: 'Struktur Temporal dan Perubahan Rezim' },
  { id: 'metadata-audit', label: 'Metadata Audit dan Akses Data' },
] as const

const panelGridSx = {
  alignItems: 'start',
  display: 'grid',
  gap: 4,
  gridTemplateColumns: 'repeat(auto-fit, minmax(min(320px, 100%), 1fr))',
  minWidth: 0,
  '& > *': { minWidth: 0 },
} as const

const technicalTextSx = {
  fontFamily: tokens.font.data,
  fontVariantNumeric: 'tabular-nums',
  overflowWrap: 'anywhere',
} as const

function hashPrefix(hash: string): string {
  return `${hash.slice(0, 12)}…`
}

function RunProvenance({ run }: { run: EdaRunSummary }) {
  const fromCensored = run.sections.some((section) => section.range_boundary.from_censored)
  const toCensored = run.sections.some((section) => section.range_boundary.to_censored)
  const fromOpenEnded = run.sections.some((section) => section.range_boundary.from_open_ended)
  const toOpenEnded = run.sections.some((section) => section.range_boundary.to_open_ended)

  return (
    <Paper
      component="section"
      aria-labelledby="eda-run-provenance-heading"
      data-testid="eda-run-provenance"
      variant="outlined"
      sx={{ minWidth: 0, p: 4 }}
    >
      <Stack spacing={3} sx={{ minWidth: 0 }}>
        <Stack
          direction="row"
          spacing={2}
          useFlexGap
          sx={{ alignItems: 'center', flexWrap: 'wrap', minWidth: 0 }}
        >
          <Typography id="eda-run-provenance-heading" variant="h2" sx={{ flexGrow: 1 }}>
            Provenance sumber dan algoritme
          </Typography>
          <ProvenanceBadge
            edaProvenance={run.canonical_release ? 'canonical_release' : 'algorithm_equivalent'}
          />
        </Stack>

        <Stack direction="row" spacing={1} useFlexGap sx={{ flexWrap: 'wrap' }}>
          <Chip size="small" label="B02" />
          <Chip size="small" label="Suhu (°C)" />
          <Chip size="small" label="RH (%)" />
          <Chip size="small" label="Asia/Jakarta (WIB)" />
        </Stack>

        <Box sx={panelGridSx}>
          <Stack spacing={0.5} sx={{ minWidth: 0 }}>
            <Typography variant="caption" color="text.secondary">Identitas run</Typography>
            <Typography variant="body2" sx={technicalTextSx}>Run: {run.run_id}</Typography>
            <Typography variant="body2" sx={technicalTextSx}>
              Source SHA-256: {hashPrefix(run.source_sha256)}
            </Typography>
          </Stack>
          <Stack spacing={0.5} sx={{ minWidth: 0 }}>
            <Typography variant="caption" color="text.secondary">Versi komputasi</Typography>
            <Typography variant="body2" sx={technicalTextSx}>
              Algoritme: {run.algorithm_version}
            </Typography>
            <Typography variant="body2" sx={technicalTextSx}>
              Config: {hashPrefix(run.config_hash)}
            </Typography>
          </Stack>
          <Stack spacing={0.5} sx={{ minWidth: 0 }}>
            <Typography variant="caption" color="text.secondary">Rentang tepat, half-open</Typography>
            <Typography variant="body2" sx={technicalTextSx}>
              {run.scope.from} – {run.scope.to}
            </Typography>
            <Typography variant="body2" sx={technicalTextSx}>
              Jenis periode: {run.scope.period_kind}
            </Typography>
          </Stack>
          <Stack spacing={0.5} sx={{ minWidth: 0 }}>
            <Typography variant="caption" color="text.secondary">Status batas rentang</Typography>
            <Typography variant="body2" sx={technicalTextSx}>
              Boundary-censored: {fromCensored || toCensored ? 'ya' : 'tidak'}
            </Typography>
            <Typography variant="body2" sx={technicalTextSx}>
              Awal {fromCensored ? 'tersensor' : fromOpenEnded ? 'open-ended' : 'utuh'} · akhir {toCensored ? 'tersensor' : toOpenEnded ? 'open-ended' : 'utuh'}
            </Typography>
          </Stack>
        </Box>
      </Stack>
    </Paper>
  )
}

function AuditMetadataPanel({ runId }: { runId: string | null }) {
  const query = useEdaSectionQuery(runId, 'audit_metadata')
  const section = query.data
  const payload = section?.status === 'complete' && section.section === 'audit_metadata'
    ? section.payload
    : undefined

  return (
    <Paper variant="outlined" sx={{ minWidth: 0, p: 4 }}>
      <Stack spacing={2} sx={{ minWidth: 0 }}>
        {runId === null ? (
          <EmptyState
            title="Pilih run EDA"
            detail="Metadata audit tersedia setelah satu run dipilih."
          />
        ) : query.isError ? (
          <ApiErrorPanel error={query.error} onRetry={() => void query.refetch()} />
        ) : section === undefined ? (
          <PanelSkeleton label="Memuat metadata audit" />
        ) : section.status === 'not_eligible' ? (
          <EmptyState title="Metadata audit belum tersedia" detail={formatEdaReasonDetail(section.reason_code, section.detail)} />
        ) : section.status === 'failed' ? (
          <ApiErrorPanel
            error={new ApiError('problem', section.detail)}
            onRetry={() => void query.refetch()}
          />
        ) : payload === undefined ? (
          <EmptyState
            title="Metadata audit kosong"
            detail="Run selesai tanpa identitas dataset atau rilis yang dapat ditampilkan."
          />
        ) : (
          <>
            <TableContainer
              data-testid="eda-audit-table-scroll"
              sx={{ maxWidth: '100%', overflowX: 'auto' }}
            >
              <Table size="small" aria-label="Metadata audit run EDA" sx={{ minWidth: tokens.size.sidebar * 3 }}>
                <TableBody>
                  {[
                    ['Dataset', payload.dataset_id],
                    ['Rilis', payload.release_id],
                    ['Manifest sumber', hashPrefix(payload.source_manifest_sha256)],
                    ['Seed', payload.seed.toLocaleString('id-ID')],
                    [
                      'Dependensi',
                      Object.entries(payload.dependencies)
                        .map(([name, version]) => `${name} ${version}`)
                        .join(' · '),
                    ],
                  ].map(([label, value]) => (
                    <TableRow key={label}>
                      <TableCell component="th" scope="row">{label}</TableCell>
                      <TableCell sx={technicalTextSx}>{value}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
            <Typography variant="body2" color="text.secondary">
              Data bounded dapat diakses melalui kontrol Lihat data pada panel yang menyediakannya; tabel audit ini tidak menggantikan payload sumber.
            </Typography>
          </>
        )}
      </Stack>
    </Paper>
  )
}

export function EdaPage() {
  const [selectedRun, setSelectedRun] = useState<EdaRunSummary | null>(null)
  const runId = selectedRun?.run_id ?? null

  return (
    <Stack spacing={6} sx={{ fontVariantNumeric: 'tabular-nums', minWidth: 0 }}>
      <Stack spacing={1} sx={{ minWidth: 0 }}>
        <Typography variant="h1">EDA</Typography>
        <Typography color="text.secondary">
          Eksplorasi visual data historis B02 untuk Suhu dan RH dalam kalender Asia/Jakarta.
        </Typography>
      </Stack>

      <EdaRunControls onRunSelected={setSelectedRun} />

      {selectedRun === null ? (
        <Paper variant="outlined" sx={{ minWidth: 0, p: 4 }}>
          <EmptyState
            title="Belum ada run EDA terpilih"
            detail="Pilih periode precompute atau hitung rentang kustom untuk memuat provenance dan panel penelitian."
          />
        </Paper>
      ) : (
        <RunProvenance run={selectedRun} />
      )}

      <Alert severity="info" role="note" aria-label="Batas metodologi EDA">
        <Stack spacing={0.5}>
          <Typography variant="body2"><strong>Kualitas kandidat saja;</strong> hasil screening bukan ground truth.</Typography>
          <Typography variant="body2">Analisis bersifat deskriptif, bukan kausal.</Typography>
          <Typography variant="body2">Halaman ini tidak memuat bukti model atau deteksi anomali.</Typography>
          <Typography variant="body2">Mentah dan screened adalah populasi terpilih yang berbeda, bukan perbandingan akurasi.</Typography>
        </Stack>
      </Alert>

      <Paper component="nav" aria-label="Indeks bagian EDA" variant="outlined" sx={{ minWidth: 0, p: 2 }}>
        <Stack direction="row" spacing={2} useFlexGap sx={{ alignItems: 'center', flexWrap: 'wrap' }}>
          <Typography variant="caption" color="text.secondary">Lompat ke</Typography>
          {anchors.map((anchor) => (
            <Link key={anchor.id} href={`#${anchor.id}`} underline="hover" color="inherit">
              {anchor.label}
            </Link>
          ))}
        </Stack>
      </Paper>

      <Stack component="section" id="kualitas-data" aria-labelledby="kualitas-data-heading" spacing={3} sx={{ minWidth: 0 }}>
        <Stack spacing={0.5}>
          <Typography id="kualitas-data-heading" variant="h2">Kualitas Data</Typography>
          <Typography variant="body2" color="text.secondary">Audit pairing, domain, distribusi, dan excerpt sebelum interpretasi.</Typography>
        </Stack>
        <Box data-testid="eda-grid-quality" data-layout="auto-fit-min-320" sx={panelGridSx}>
          <PairingAuditPanel runId={runId} />
          <JointDensityPanel runId={runId} />
          <UnivariateDiagnosticsPanel runId={runId} />
          <QualityExcerptPanel runId={runId} />
          <QualityIntegrityPanel runId={runId} />
        </Box>
      </Stack>

      <Stack component="section" id="pola-temporal" aria-labelledby="pola-temporal-heading" spacing={3} sx={{ minWidth: 0 }}>
        <Stack spacing={0.5}>
          <Typography id="pola-temporal-heading" variant="h2">Pola Temporal</Typography>
          <Typography variant="body2" color="text.secondary">Cakupan kalender, pola hari-jam, dan distribusi menurut waktu lokal.</Typography>
        </Stack>
        <Box data-testid="eda-grid-temporal" data-layout="auto-fit-min-320" sx={panelGridSx}>
          <TemporalCoveragePanel runId={runId} />
          <WeekdayHourCoveragePanel runId={runId} />
          <TemporalDistributionPanel runId={runId} />
        </Box>
      </Stack>

      <Stack component="section" id="hubungan-suhu-rh" aria-labelledby="hubungan-suhu-rh-heading" spacing={3} sx={{ minWidth: 0 }}>
        <Stack spacing={0.5}>
          <Typography id="hubungan-suhu-rh-heading" variant="h2">Hubungan Suhu-RH</Typography>
          <Typography variant="body2" color="text.secondary">Asosiasi statis, sensitivitas rolling, dan ketidakpastian bootstrap.</Typography>
        </Stack>
        <Box data-testid="eda-grid-relationships" data-layout="auto-fit-min-320" sx={panelGridSx}>
          <AssociationSummaryPanel runId={runId} />
          <RollingCorrelationPanel runId={runId} />
          <BootstrapUncertaintyPanel runId={runId} />
        </Box>
      </Stack>

      <Stack component="section" id="struktur-temporal" aria-labelledby="struktur-temporal-heading" spacing={3} sx={{ minWidth: 0 }}>
        <Stack spacing={0.5}>
          <Typography id="struktur-temporal-heading" variant="h2">Struktur Temporal dan Perubahan Rezim</Typography>
          <Typography variant="body2" color="text.secondary">Kelayakan, dependensi lag, frekuensi, dekomposisi, dan kandidat batas rezim.</Typography>
        </Stack>
        <Box data-testid="eda-grid-structure" data-layout="auto-fit-min-320" sx={panelGridSx}>
          <StationarityEligibilityPanel runId={runId} />
          <AutocorrelationPanel runId={runId} />
          <SpectrumPanel runId={runId} />
          <StlDecompositionPanel runId={runId} />
          <ChangePointPanel runId={runId} />
        </Box>
      </Stack>

      <Stack component="section" id="metadata-audit" aria-labelledby="metadata-audit-heading" spacing={3} sx={{ minWidth: 0 }}>
        <Stack spacing={0.5}>
          <Typography id="metadata-audit-heading" variant="h2">Metadata Audit dan Akses Data</Typography>
          <Typography variant="body2" color="text.secondary">Identitas dataset, rilis, manifest sumber, seed, dan dependensi komputasi.</Typography>
        </Stack>
        <AuditMetadataPanel runId={runId} />
      </Stack>
    </Stack>
  )
}
