import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
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
import { EdaSectionHeading } from '../features/eda/EdaSectionHeading'
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

const panelGridSx = (desktopColumns: string) => ({
  alignItems: 'start',
  display: 'grid',
  gap: 4,
  gridAutoFlow: 'dense',
  gridTemplateColumns: {
    xs: 'minmax(0, 1fr)',
    md: desktopColumns,
  },
  minWidth: 0,
  '& > *': { minWidth: 0 },
})

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
  const boundaryStatus = fromCensored || toCensored
    ? 'tersensor'
    : fromOpenEnded || toOpenEnded ? 'open-ended' : 'utuh'

  return (
    <Accordion
      component="section"
      aria-labelledby="eda-run-provenance-heading"
      data-testid="eda-run-provenance"
      disableGutters
      slots={{ heading: 'div' }}
      variant="outlined"
      sx={{
        minWidth: 0,
        '&::before': { display: 'none' },
        '&.Mui-expanded': { m: 0 },
      }}
    >
      <AccordionSummary
        aria-controls="eda-run-provenance-detail"
        id="eda-run-provenance-summary"
        sx={{
          minHeight: tokens.size.control,
          px: 3,
          '&.Mui-expanded': { minHeight: tokens.size.control },
          '& .MuiAccordionSummary-content': { my: 1 },
          '& .MuiAccordionSummary-content.Mui-expanded': { my: 1 },
        }}
      >
        <Stack
          direction="row"
          spacing={1.5}
          useFlexGap
          sx={{ alignItems: 'center', flexWrap: 'wrap', minWidth: 0, width: '100%' }}
        >
          <Typography
            component="h2"
            id="eda-run-provenance-heading"
            variant="caption"
            sx={{ fontWeight: 700 }}
          >
            Provenance
          </Typography>
          <ProvenanceBadge
            edaProvenance={run.canonical_release ? 'canonical_release' : 'algorithm_equivalent'}
          />
          <Typography variant="body2" sx={technicalTextSx}>
            Run: {hashPrefix(run.run_id)}
          </Typography>
          <Typography variant="body2" sx={technicalTextSx}>
            {run.scope.from} – {run.scope.to}
          </Typography>
          <Typography variant="body2">Boundary: {boundaryStatus}</Typography>
          <Typography variant="body2" color="primary.main" sx={{ fontWeight: 700, ml: 'auto' }}>
            Detail
          </Typography>
        </Stack>
      </AccordionSummary>

      <AccordionDetails sx={{ px: 3, pb: 3, pt: 0 }}>
        <Stack spacing={2} sx={{ minWidth: 0 }}>
          <Stack direction="row" spacing={1} useFlexGap sx={{ flexWrap: 'wrap' }}>
            <Chip size="small" label="B02" />
            <Chip size="small" label="Suhu (°C)" />
            <Chip size="small" label="RH (%)" />
            <Chip size="small" label="Asia/Jakarta (WIB)" />
          </Stack>

          <Box
            sx={{
              display: 'grid',
              gap: 3,
              gridTemplateColumns: {
                xs: 'minmax(0, 1fr)',
                md: 'repeat(4, minmax(0, 1fr))',
              },
              minWidth: 0,
            }}
          >
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
      </AccordionDetails>
    </Accordion>
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

      <Alert
        severity="info"
        role="note"
        aria-label="Batas metodologi EDA"
        sx={{ '& .MuiAlert-message': { py: 0, width: '100%' } }}
      >
        <Accordion
          disableGutters
          elevation={0}
          slots={{ heading: 'div' }}
          sx={{
            backgroundColor: 'transparent',
            color: 'inherit',
            '&::before': { display: 'none' },
            '&.Mui-expanded': { m: 0 },
          }}
        >
          <AccordionSummary
            aria-controls="eda-methodology-detail"
            id="eda-methodology-summary"
            sx={{
              minHeight: tokens.size.control,
              p: 0,
              '&.Mui-expanded': { minHeight: tokens.size.control },
              '& .MuiAccordionSummary-content': { my: 0 },
              '& .MuiAccordionSummary-content.Mui-expanded': { my: 0 },
            }}
          >
            <Stack
              direction="row"
              spacing={2}
              useFlexGap
              sx={{ alignItems: 'center', flexWrap: 'wrap', width: '100%' }}
            >
              <Typography variant="body2" sx={{ fontWeight: 700 }}>
                Screening kualitas dan analisis deskriptif; bukan ground truth, kausalitas, atau bukti model.
              </Typography>
              <Typography variant="body2" sx={{ fontWeight: 700, ml: 'auto' }}>
                Batas metodologi
              </Typography>
            </Stack>
          </AccordionSummary>
          <AccordionDetails sx={{ p: 0, pt: 1 }}>
            <Stack spacing={0.5}>
              <Typography variant="body2"><strong>Kualitas kandidat saja;</strong> hasil screening bukan ground truth.</Typography>
              <Typography variant="body2">Analisis bersifat deskriptif, bukan kausal.</Typography>
              <Typography variant="body2">Halaman ini tidak memuat bukti model atau deteksi anomali.</Typography>
              <Typography variant="body2">Mentah dan screened adalah populasi terpilih yang berbeda, bukan perbandingan akurasi.</Typography>
            </Stack>
          </AccordionDetails>
        </Accordion>
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
        <EdaSectionHeading
          id="kualitas-data-heading"
          title="Kualitas Data"
          supportingText="Audit pairing, domain, distribusi, dan excerpt sebelum interpretasi."
        />
        <Box data-testid="eda-grid-quality" data-layout="curated-spans" sx={panelGridSx('repeat(12, minmax(0, 1fr))')}>
          <Box sx={{ gridColumn: '1 / -1' }}>
            <PairingAuditPanel runId={runId} />
          </Box>
          <Box sx={{ gridColumn: '1 / -1' }}>
            <JointDensityPanel runId={runId} />
          </Box>
          <Box sx={{ gridColumn: '1 / -1' }}>
            <UnivariateDiagnosticsPanel runId={runId} />
          </Box>
          <Box sx={{ gridColumn: { xs: '1 / -1', md: 'span 6' } }}>
            <QualityExcerptPanel runId={runId} />
          </Box>
          <Box sx={{ gridColumn: { xs: '1 / -1', md: 'span 6' } }}>
            <QualityIntegrityPanel runId={runId} />
          </Box>
        </Box>
      </Stack>

      <Stack component="section" id="pola-temporal" aria-labelledby="pola-temporal-heading" spacing={3} sx={{ minWidth: 0 }}>
        <EdaSectionHeading
          id="pola-temporal-heading"
          title="Pola Temporal"
          supportingText="Cakupan kalender, pola hari-jam, dan distribusi menurut waktu lokal."
        />
        <Box data-testid="eda-grid-temporal" data-layout="curated-spans" sx={panelGridSx('repeat(2, minmax(0, 1fr))')}>
          <Box sx={{ gridColumn: { xs: '1 / -1', md: 'span 1' } }}>
            <TemporalCoveragePanel runId={runId} />
          </Box>
          <Box sx={{ gridColumn: { xs: '1 / -1', md: 'span 1' } }}>
            <WeekdayHourCoveragePanel runId={runId} />
          </Box>
          <Box sx={{ gridColumn: '1 / -1' }}>
            <TemporalDistributionPanel runId={runId} />
          </Box>
        </Box>
      </Stack>

      <Stack component="section" id="hubungan-suhu-rh" aria-labelledby="hubungan-suhu-rh-heading" spacing={3} sx={{ minWidth: 0 }}>
        <EdaSectionHeading
          id="hubungan-suhu-rh-heading"
          title="Hubungan Suhu-RH"
          supportingText="Asosiasi statis, sensitivitas rolling, dan ketidakpastian bootstrap."
        />
        <Box data-testid="eda-grid-relationships" data-layout="curated-spans" sx={panelGridSx('repeat(2, minmax(0, 1fr))')}>
          <Box sx={{ gridColumn: { xs: '1 / -1', md: 'span 1' } }}>
            <AssociationSummaryPanel runId={runId} />
          </Box>
          <Box sx={{ gridColumn: { xs: '1 / -1', md: 'span 1' } }}>
            <RollingCorrelationPanel runId={runId} />
          </Box>
          <Box sx={{ gridColumn: '1 / -1' }}>
            <BootstrapUncertaintyPanel runId={runId} />
          </Box>
        </Box>
      </Stack>

      <Stack component="section" id="struktur-temporal" aria-labelledby="struktur-temporal-heading" spacing={3} sx={{ minWidth: 0 }}>
        <EdaSectionHeading
          id="struktur-temporal-heading"
          title="Struktur Temporal dan Perubahan Rezim"
          supportingText="Kelayakan, dependensi lag, frekuensi, dekomposisi, dan kandidat batas rezim."
        />
        <Box data-testid="eda-grid-structure" data-layout="curated-spans" sx={panelGridSx('repeat(2, minmax(0, 1fr))')}>
          <Box sx={{ gridColumn: '1 / -1' }}>
            <StationarityEligibilityPanel runId={runId} />
          </Box>
          <Box sx={{ gridColumn: { xs: '1 / -1', md: 'span 1' } }}>
            <AutocorrelationPanel runId={runId} />
          </Box>
          <Box sx={{ gridColumn: { xs: '1 / -1', md: 'span 1' } }}>
            <SpectrumPanel runId={runId} />
          </Box>
          <Box sx={{ gridColumn: '1 / -1' }}>
            <StlDecompositionPanel runId={runId} />
          </Box>
          <Box sx={{ gridColumn: '1 / -1' }}>
            <ChangePointPanel runId={runId} />
          </Box>
        </Box>
      </Stack>

      <Stack component="section" id="metadata-audit" aria-labelledby="metadata-audit-heading" spacing={3} sx={{ minWidth: 0 }}>
        <EdaSectionHeading
          id="metadata-audit-heading"
          title="Metadata Audit dan Akses Data"
          supportingText="Identitas dataset, rilis, manifest sumber, seed, dan dependensi komputasi."
        />
        <AuditMetadataPanel runId={runId} />
      </Stack>
    </Stack>
  )
}
