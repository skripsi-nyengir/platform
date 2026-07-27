import { Box, Button, Chip, Paper, Stack, Typography } from '@mui/material'
import type { GridColDef } from '@mui/x-data-grid'
import { useState } from 'react'
import { ApiError } from '../../api/errors'
import {
  buildStationarityEligibilityData,
  type StationarityEligibilitySegment,
} from '../../components/charts/structureEdaOptions'
import { BoundedDataDialog } from '../../components/data/BoundedDataDialog'
import { ApiErrorPanel } from '../../components/states/ApiErrorPanel'
import { EmptyState } from '../../components/states/EmptyState'
import { PanelSkeleton } from '../../components/states/PanelSkeleton'
import { tokens } from '../../theme/tokens'
import { useEdaSectionQuery } from './queries'
import { formatEdaReasonDetail } from './reasonLabels'

export interface StationarityEligibilityPanelProps {
  runId: string | null
}

interface EligibilityRow extends StationarityEligibilitySegment {
  id: string
  selected: boolean
}

const columns: readonly GridColDef<EligibilityRow>[] = [
  { field: 'kind', headerName: 'Tier', flex: 1 },
  { field: 'start', headerName: 'Mulai segmen', flex: 2 },
  { field: 'end', headerName: 'Selesai segmen', flex: 2 },
  { field: 'hours', headerName: 'Median per jam', flex: 1 },
  { field: 'selected', headerName: 'Dipakai chart', type: 'boolean', flex: 1 },
]

const technicalTextSx = {
  fontFamily: tokens.font.data,
  fontVariantNumeric: 'tabular-nums',
  overflowWrap: 'anywhere',
} as const

const METHOD_NOTICE = 'ADF dan KPSS mempertahankan hipotesis nol berbeda; keduanya adalah diagnostik, bukan gerbang pembersihan atau pemodelan.'

function AdmissionSummary({
  sensitivityEligible = false,
  primaryEligible = false,
}: {
  sensitivityEligible?: boolean
  primaryEligible?: boolean
}) {
  return (
    <Stack direction="row" spacing={1} useFlexGap sx={{ flexWrap: 'wrap' }}>
      <Chip
        size="small"
        color={sensitivityEligible ? 'success' : 'default'}
        label="SENSITIVITY ≥ 336 jam"
      />
      <Chip
        size="small"
        color={primaryEligible ? 'success' : 'default'}
        label="PRIMARY ≥ 720 jam"
      />
    </Stack>
  )
}

export function StationarityEligibilityPanel(props: StationarityEligibilityPanelProps) {
  return <StationarityEligibilityPanelContent key={props.runId ?? 'no-run'} {...props} />
}

function StationarityEligibilityPanelContent({ runId }: StationarityEligibilityPanelProps) {
  const [dialogRunId, setDialogRunId] = useState<string | null>(null)
  const query = useEdaSectionQuery(runId, 'stationarity')
  const section = query.data
  const data = section?.status === 'complete' && section.section === 'stationarity'
    ? buildStationarityEligibilityData(section.payload)
    : undefined
  const rows: EligibilityRow[] = data === undefined
    ? []
    : [
        ...(data.selected.kind === 'primary' ? [data.selected] : []),
        ...data.sensitivitySegments,
      ].map((segment, index) => ({
        ...segment,
        id: `${segment.kind}-${index}-${segment.start}`,
        selected: segment.kind === data.selected.kind && segment.start === data.selected.start,
      }))

  return (
    <Paper
      component="section"
      aria-labelledby="stationarity-eligibility-heading"
      variant="outlined"
      sx={{ minWidth: 0, p: 4 }}
    >
      <Stack spacing={2} sx={{ minWidth: 0 }}>
        <Typography id="stationarity-eligibility-heading" variant="h2">
          Kelayakan struktur temporal
        </Typography>
        {runId === null ? (
          <EmptyState
            title="Pilih run EDA"
            detail="Kelayakan struktur temporal ditampilkan setelah run EDA dipilih."
          />
        ) : query.isError ? (
          <ApiErrorPanel error={query.error} onRetry={() => void query.refetch()} />
        ) : section === undefined ? (
          <PanelSkeleton label="Memuat kelayakan struktur temporal" />
        ) : section.status === 'not_eligible' ? (
          <>
            <EmptyState title="Struktur temporal belum memenuhi syarat" detail={formatEdaReasonDetail(section.reason_code, section.detail)} />
            <Typography variant="body2" color="text.secondary">
              Agregasi: <Box component="span" sx={technicalTextSx}>Median per jam</Box>
            </Typography>
            <AdmissionSummary />
            <Typography variant="caption" color="text.secondary">{METHOD_NOTICE}</Typography>
          </>
        ) : section.status === 'failed' ? (
          <ApiErrorPanel
            error={new ApiError('problem', section.detail)}
            onRetry={() => void query.refetch()}
          />
        ) : data === undefined ? (
          <EmptyState
            title="Metadata kelayakan kosong"
            detail="Run selesai tanpa segmen median per jam yang dapat ditampilkan."
          />
        ) : (
          <>
            <Stack direction="row" spacing={1} useFlexGap sx={{ alignItems: 'center', flexWrap: 'wrap' }}>
              <Chip
                size="small"
                color={data.tier === 'primary' ? 'success' : 'warning'}
                label={data.tier.toUpperCase()}
              />
              <Typography variant="body2" color="text.secondary">
                Tier yang dipakai oleh ACF/PACF, spektrum, dan STL.
              </Typography>
            </Stack>
            <Box
              sx={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(min(320px,100%),1fr))',
                gap: 2,
                minWidth: 0,
                '& > *': { minWidth: 0 },
              }}
            >
              <Stack spacing={0.5}>
                <Typography variant="caption" color="text.secondary">Mulai segmen</Typography>
                <Typography variant="body2" sx={technicalTextSx}>{data.selected.start}</Typography>
              </Stack>
              <Stack spacing={0.5}>
                <Typography variant="caption" color="text.secondary">Selesai segmen</Typography>
                <Typography variant="body2" sx={technicalTextSx}>{data.selected.end}</Typography>
              </Stack>
              <Stack spacing={0.5}>
                <Typography variant="caption" color="text.secondary">Panjang segmen</Typography>
                <Typography variant="h3" sx={technicalTextSx}>{data.selected.hours} jam</Typography>
              </Stack>
              <Stack spacing={0.5}>
                <Typography variant="caption" color="text.secondary">Agregasi analisis</Typography>
                <Typography variant="h3">{data.aggregation}</Typography>
              </Stack>
            </Box>
            <AdmissionSummary sensitivityEligible primaryEligible={data.primaryEligible} />
            <Typography variant="body2" color="text.secondary">{data.methodNotice}</Typography>
            <Typography variant="caption" color="text.secondary">
              Panel ini melaporkan kelayakan metode; tidak menyatukan hasil ADF/KPSS menjadi badge stasioner atau tidak stasioner.
            </Typography>
                <Button
                  aria-haspopup="dialog"
                  aria-label="Lihat data kelayakan struktur temporal"
                  size="small"
                  onClick={() => setDialogRunId(runId)}
                >
                  Lihat data
                </Button>
            <BoundedDataDialog<EligibilityRow>
              open={dialogRunId !== null && dialogRunId === runId}
              title="Segmen kelayakan struktur temporal"
              rows={rows}
              returnedCount={rows.length}
              columns={columns}
              onClose={() => setDialogRunId(null)}
            />
          </>
        )}
      </Stack>
    </Paper>
  )
}
