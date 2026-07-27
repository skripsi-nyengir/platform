import type { ChangePointsPayload, StationarityPayload } from '../../contracts/eda'

export const AUTOCORRELATION_DOMAIN = [-1, 1] as const
export const STL_PERIOD_HOURS = 24

export type StructureChannelKey = 'suhu' | 'rh'
export type DiagnosticStatus = 'ok' | 'short' | 'constant' | 'nonfinite' | 'error'

const channelMetadata = [
  { key: 'suhu', name: 'Suhu', unit: '°C' },
  { key: 'rh', name: 'RH', unit: '%' },
] as const

type StationaritySegment = StationarityPayload['sensitivity'][number]

interface SelectedStationaritySegment {
  kind: 'sensitivity' | 'primary'
  segment: StationaritySegment
}

function selectedStationaritySegment(
  payload: StationarityPayload,
): SelectedStationaritySegment {
  if (payload.eligibility_tier === 'primary' && payload.primary !== null) {
    return { kind: 'primary', segment: payload.primary }
  }
  const segment = payload.sensitivity[0]
  if (segment === undefined) throw new Error('Stationarity sensitivity segment is required')
  return { kind: 'sensitivity', segment }
}

export interface StationarityEligibilitySegment {
  kind: 'sensitivity' | 'primary'
  start: string
  end: string
  hours: number
}

export interface StationarityEligibilityData {
  tier: 'sensitivity' | 'primary'
  aggregation: 'Median per jam'
  methodNotice: string
  selected: StationarityEligibilitySegment
  primaryEligible: boolean
  sensitivitySegments: StationarityEligibilitySegment[]
}

export function buildStationarityEligibilityData(
  payload: StationarityPayload,
): StationarityEligibilityData {
  const selected = selectedStationaritySegment(payload)
  return {
    tier: payload.eligibility_tier,
    aggregation: 'Median per jam',
    methodNotice: 'ADF dan KPSS mempertahankan hipotesis nol berbeda; keduanya adalah diagnostik, bukan gerbang pembersihan atau pemodelan.',
    selected: {
      kind: selected.kind,
      start: selected.segment.start,
      end: selected.segment.end,
      hours: selected.segment.hours,
    },
    primaryEligible: payload.primary !== null,
    sensitivitySegments: payload.sensitivity.map((segment) => ({
      kind: 'sensitivity',
      start: segment.start,
      end: segment.end,
      hours: segment.hours,
    })),
  }
}

export interface AutocorrelationChannelData {
  key: StructureChannelKey
  name: string
  lags: number[]
  autocorrelation: number[]
  partialAutocorrelation: number[]
  autocorrelationStatus: DiagnosticStatus
  partialAutocorrelationStatus: DiagnosticStatus
  autocorrelationError: string | null
  partialAutocorrelationError: string | null
}

export interface AutocorrelationData {
  segment: StationarityEligibilitySegment
  channels: AutocorrelationChannelData[]
}

export function buildAutocorrelationData(payload: StationarityPayload): AutocorrelationData {
  const selected = selectedStationaritySegment(payload)
  return {
    segment: {
      kind: selected.kind,
      start: selected.segment.start,
      end: selected.segment.end,
      hours: selected.segment.hours,
    },
    channels: channelMetadata.map(({ key, name }) => {
      const source = selected.segment.channels[key]
      const length = Math.max(
        source.autocorrelation.values.length,
        source.partial_autocorrelation.values.length,
      )
      return {
        key,
        name,
        lags: Array.from({ length }, (_, lag) => lag),
        autocorrelation: source.autocorrelation.values,
        partialAutocorrelation: source.partial_autocorrelation.values,
        autocorrelationStatus: source.autocorrelation.status,
        partialAutocorrelationStatus: source.partial_autocorrelation.status,
        autocorrelationError: source.autocorrelation.error,
        partialAutocorrelationError: source.partial_autocorrelation.error,
      }
    }),
  }
}

export interface SpectrumRow {
  id: string
  frequency: number
  power: number | null
  periodHours: number | null
}

export interface SpectrumChannelData {
  key: StructureChannelKey
  name: string
  status: DiagnosticStatus
  error: string | null
  rows: SpectrumRow[]
}

export interface SpectrumData {
  segment: StationarityEligibilitySegment
  channels: SpectrumChannelData[]
}

export function buildSpectrumData(payload: StationarityPayload): SpectrumData {
  const selected = selectedStationaritySegment(payload)
  return {
    segment: {
      kind: selected.kind,
      start: selected.segment.start,
      end: selected.segment.end,
      hours: selected.segment.hours,
    },
    channels: channelMetadata.map(({ key, name }) => {
      const spectrum = selected.segment.channels[key].spectrum
      return {
        key,
        name,
        status: spectrum.status,
        error: spectrum.error,
        rows: spectrum.frequencies.map((frequency, index) => ({
          id: `${key}-${index}`,
          frequency,
          power: spectrum.power[index] ?? null,
          periodHours: Number.isFinite(frequency) && frequency !== 0
            ? 1 / frequency
            : null,
        })),
      }
    }),
  }
}

export interface StlRow {
  id: string
  timestamp: Date
  timestampIso: string
  trend: number
  seasonal: number | null
  residual: number | null
}

export interface StlChannelData {
  key: StructureChannelKey
  name: string
  unit: '°C' | '%'
  status: DiagnosticStatus
  error: string | null
  rows: StlRow[]
}

export interface StlData {
  periodHours: 24
  segment: StationarityEligibilitySegment
  channels: StlChannelData[]
}

export function buildStlData(payload: StationarityPayload): StlData {
  const selected = selectedStationaritySegment(payload)
  const start = new Date(selected.segment.start).getTime()
  return {
    periodHours: STL_PERIOD_HOURS,
    segment: {
      kind: selected.kind,
      start: selected.segment.start,
      end: selected.segment.end,
      hours: selected.segment.hours,
    },
    channels: channelMetadata.map(({ key, name, unit }) => {
      const stl = selected.segment.channels[key].stl
      return {
        key,
        name,
        unit,
        status: stl.status,
        error: stl.error,
        rows: stl.trend.map((trend, index) => {
          const timestamp = new Date(start + index * 3_600_000)
          return {
            id: `${key}-${index}`,
            timestamp,
            timestampIso: timestamp.toISOString(),
            trend,
            seasonal: stl.seasonal[index] ?? null,
            residual: stl.residual[index] ?? null,
          }
        }),
      }
    }),
  }
}

const DAY_MS = 86_400_000

function dayDate(day: number): Date {
  return new Date(day * DAY_MS)
}

function dayLabel(day: number): string {
  return dayDate(day).toISOString().slice(0, 10)
}

export interface ChangeCandidateData {
  id: string
  blockIndex: number
  day: number
  date: Date
  dateLabel: string
  stabilityCount: number
  temperatureShift: number
  humidityShift: number
  temperatureMadEffect: number | null
  humidityMadEffect: number | null
}

export interface ChangePointChannelData {
  key: StructureChannelKey
  name: string
  shiftUnit: '°C' | '%'
  effectUnit: 'MAD'
  shifts: number[]
  effects: (number | null)[]
}

export interface ChangeConfirmationSummary {
  id: string
  blockIndex: number
  minimumSegmentDays: 7 | 14 | 28
  status: 'ok' | 'insufficient_data' | 'error'
  requestedBreakpoints: number
  matchedStableChanges: number
}

export interface ChangePointBlockSummary {
  id: string
  blockIndex: number
  status: 'ok' | 'constant' | 'insufficient_data'
  pairCount: number
  startDate: string
  endDate: string
  stableChangeCount: number
  confirmationCount: number
}

export interface ChangePointAuditRow {
  id: string
  blockRange: string
  blockStatus: string
  pairCount: number
  scaleMedianSuhu: number | null
  scaleMedianRh: number | null
  scaleMadSuhu: number | null
  scaleMadRh: number | null
  constantChannels: string
  candidateDate: string | null
  stabilityCount: number | null
  penaltyFactors: string
  observedDays: string
  confirmations: string
}

export interface ChangePointData {
  candidates: ChangeCandidateData[]
  channels: ChangePointChannelData[]
  confirmationSummary: ChangeConfirmationSummary[]
  blockSummaries: ChangePointBlockSummary[]
  auditRows: ChangePointAuditRow[]
}

export function buildChangePointData(payload: ChangePointsPayload): ChangePointData {
  const candidates = payload.blocks.flatMap((block, blockIndex) => (
    block.stable_changes.map((candidate): ChangeCandidateData => ({
      id: `${blockIndex}-${candidate.representative_day}-${candidate.representative_boundary_index}`,
      blockIndex,
      day: candidate.representative_day,
      date: dayDate(candidate.representative_day),
      dateLabel: dayLabel(candidate.representative_day),
      stabilityCount: candidate.penalty_factors.length,
      temperatureShift: candidate.temperature_shift,
      humidityShift: candidate.humidity_shift,
      temperatureMadEffect: candidate.temperature_mad_effect,
      humidityMadEffect: candidate.humidity_mad_effect,
    }))
  )).sort((left, right) => left.day - right.day || left.blockIndex - right.blockIndex)

  const confirmationSummary = payload.blocks.flatMap((block, blockIndex) => (
    block.confirmations.map((confirmation): ChangeConfirmationSummary => ({
      id: `${blockIndex}-${confirmation.minimum_segment_days}`,
      blockIndex,
      minimumSegmentDays: confirmation.minimum_segment_days,
      status: confirmation.status,
      requestedBreakpoints: confirmation.requested_breakpoints,
      matchedStableChanges: confirmation.matched_stable_changes,
    }))
  )).sort((left, right) => (
    left.minimumSegmentDays - right.minimumSegmentDays || left.blockIndex - right.blockIndex
  ))

  const auditRows = payload.blocks.flatMap((block, blockIndex): ChangePointAuditRow[] => {
    const constants = block.constant_channels
      .map((channel) => channel === 0 ? 'Suhu' : 'RH')
      .join(', ')
    const confirmations = [...block.confirmations]
      .sort((left, right) => left.minimum_segment_days - right.minimum_segment_days)
      .map((confirmation) => (
        `${confirmation.minimum_segment_days} hari: ${confirmation.status}; ` +
        `${confirmation.matched_stable_changes}/${confirmation.requested_breakpoints} cocok; ` +
        `batas ${confirmation.boundary_days.map(dayLabel).join(', ') || '—'}`
      ))
      .join(' | ')
    const sortedCandidates = [...block.stable_changes]
      .sort((left, right) => left.representative_day - right.representative_day)
    const rows = sortedCandidates.length > 0 ? sortedCandidates : [null]
    return rows.map((candidate, candidateIndex) => ({
      id: `${blockIndex}-${candidate?.representative_day ?? `block-${candidateIndex}`}`,
      blockRange: `${dayLabel(block.start_day)} – ${dayLabel(block.end_day)}`,
      blockStatus: block.status,
      pairCount: block.pair_count,
      scaleMedianSuhu: block.scale_median?.[0] ?? null,
      scaleMedianRh: block.scale_median?.[1] ?? null,
      scaleMadSuhu: block.scale_mad?.[0] ?? null,
      scaleMadRh: block.scale_mad?.[1] ?? null,
      constantChannels: constants || '—',
      candidateDate: candidate === null ? null : dayLabel(candidate.representative_day),
      stabilityCount: candidate?.penalty_factors.length ?? null,
      penaltyFactors: candidate?.penalty_factors.join(', ') ?? '—',
      observedDays: candidate?.observed_days.map(dayLabel).join(', ') ?? '—',
      confirmations: confirmations || '—',
    }))
  })

  return {
    candidates,
    channels: [
      {
        key: 'suhu',
        name: 'Suhu',
        shiftUnit: '°C',
        effectUnit: 'MAD',
        shifts: candidates.map((candidate) => candidate.temperatureShift),
        effects: candidates.map((candidate) => candidate.temperatureMadEffect),
      },
      {
        key: 'rh',
        name: 'RH',
        shiftUnit: '%',
        effectUnit: 'MAD',
        shifts: candidates.map((candidate) => candidate.humidityShift),
        effects: candidates.map((candidate) => candidate.humidityMadEffect),
      },
    ],
    confirmationSummary,
    blockSummaries: payload.blocks.map((block, blockIndex) => ({
      id: String(blockIndex),
      blockIndex,
      status: block.status,
      pairCount: block.pair_count,
      startDate: dayLabel(block.start_day),
      endDate: dayLabel(block.end_day),
      stableChangeCount: block.stable_changes.length,
      confirmationCount: block.confirmations.length,
    })),
    auditRows,
  }
}
