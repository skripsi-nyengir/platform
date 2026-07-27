import type {
  TemporalCoveragePayload,
  TemporalDistributionPayload,
} from '../../contracts/eda'

export const temporalResolutions = ['hourly', 'daily', 'monthly'] as const
export type TemporalResolution = (typeof temporalResolutions)[number]

export const temporalViews = ['resolved_raw_pairs', 'rule_screened_pairs'] as const
export type TemporalView = (typeof temporalViews)[number]

export const coverageThresholds = ['0.50', '0.80', '0.95'] as const
export type CoverageThreshold = (typeof coverageThresholds)[number]

export const weekdayLabels = [
  'Senin',
  'Selasa',
  'Rabu',
  'Kamis',
  'Jumat',
  'Sabtu',
  'Minggu',
] as const

interface CoverageBinInput {
  start: string
  end: string
  exposure_seconds: number
  full_bin_seconds: number
  expected_slots: number
  exact_pair_count: number
  view_pair_count: number
  coverage: number | null
  retention: number | null
  partial: boolean
  from_censored: boolean
  to_censored: boolean
  eligible: Partial<Record<CoverageThreshold, boolean>>
}

interface DenseRegimeInput {
  start: string
  end: string
  months: number
}

interface CoverageViewInput {
  hourly?: CoverageBinInput[]
  daily?: CoverageBinInput[]
  monthly?: CoverageBinInput[]
  dense_regimes?: Partial<Record<CoverageThreshold, DenseRegimeInput[]>>
}

interface CoveragePayloadInput {
  resolved_raw_pairs?: CoverageViewInput
  rule_screened_pairs?: CoverageViewInput
}

interface ChannelStatisticsInput {
  median: number | null
  q1: number | null
  q3: number | null
  mad: number | null
}

interface DistributionStatisticsInput {
  count: number
  suhu: ChannelStatisticsInput
  rh: ChannelStatisticsInput
}

interface DistributionBinInput {
  start: string
  end: string
  view_pair_count: number
  from_censored: boolean
  to_censored: boolean
  statistics: DistributionStatisticsInput
}

export type DriftDirection = 'increase' | 'decrease' | 'stable' | 'insufficient_data'
export type DriftStatus = 'robust' | 'not_robust' | 'insufficient_data'

export interface DriftConclusion {
  status: DriftStatus
  directions: Partial<Record<CoverageThreshold, DriftDirection>>
}

interface DistributionViewInput {
  hourly?: DistributionBinInput[]
  daily?: DistributionBinInput[]
  monthly?: DistributionBinInput[]
  channels?: {
    suhu?: { name: string; unit: string }
    rh?: { name: string; unit: string }
  }
  drift_conclusions?: {
    suhu?: DriftConclusion
    rh?: DriftConclusion
  }
}

interface DistributionPayloadInput {
  resolved_raw_pairs?: DistributionViewInput
  rule_screened_pairs?: DistributionViewInput
}

export interface TemporalCoverageRow {
  id: string
  start: string
  end: string
  x: Date
  coverage: number | null
  retention: number | null
  expectedSlots: number
  exactPairCount: number
  screenedPairCount: number
  partial: boolean
  fromCensored: boolean
  toCensored: boolean
  eligible: Record<CoverageThreshold, boolean>
}

export interface TemporalCoverageData {
  rows: TemporalCoverageRow[]
  coverage: (number | null)[]
  retention: (number | null)[]
  partialMarkers: (number | null)[]
  censoredMarkers: (number | null)[]
  totals: {
    expectedSlots: number
    exactPairCount: number
    screenedPairCount: number
    coverage: number | null
    retention: number | null
  }
  eligibility: Record<CoverageThreshold, number>
  denseRegimes: Record<CoverageThreshold, DenseRegimeInput[]>
}

export interface WeekdayHourCell {
  id: string
  weekday: number
  weekdayLabel: string
  hour: number
  expectedSlots: number
  exactPairCount: number
  viewPairCount: number
  exposureSeconds: number
  coverage: number | null
  retention: number | null
  partial: boolean
  censored: boolean
}

export interface WeekdayHourMatrixData {
  cells: WeekdayHourCell[]
  localWeeks: number
  hasTwoLocalWeeks: boolean
}

export interface TemporalDistributionPoint {
  x: Date
  median: number | null
  q1: number | null
  q3: number | null
  mad: number | null
  count: number
  censored: boolean
}

export interface TemporalDistributionChannel {
  key: 'suhu' | 'rh'
  name: string
  unit: '°C' | '%'
  points: TemporalDistributionPoint[]
}

export interface TemporalDistributionRow {
  id: string
  start: string
  end: string
  count: number
  censored: boolean
  suhuMedian: number | null
  suhuQ1: number | null
  suhuQ3: number | null
  suhuMad: number | null
  rhMedian: number | null
  rhQ1: number | null
  rhQ3: number | null
  rhMad: number | null
}

export interface TemporalDistributionData {
  channels: readonly [TemporalDistributionChannel, TemporalDistributionChannel]
  rows: TemporalDistributionRow[]
  hasData: boolean
  driftConclusions: {
    suhu?: DriftConclusion
    rh?: DriftConclusion
  }
}

function coverageViews(payload: TemporalCoveragePayload): CoveragePayloadInput {
  return payload.views as unknown as CoveragePayloadInput
}

function distributionViews(payload: TemporalDistributionPayload): DistributionPayloadInput {
  return payload.views as unknown as DistributionPayloadInput
}

function coverageRows(
  payload: TemporalCoveragePayload,
  view: TemporalView,
  resolution: TemporalResolution,
): CoverageBinInput[] {
  const rows = coverageViews(payload)[view]?.[resolution]
  return Array.isArray(rows) ? rows : []
}

function distributionRows(
  payload: TemporalDistributionPayload,
  view: TemporalView,
  resolution: TemporalResolution,
): DistributionBinInput[] {
  const rows = distributionViews(payload)[view]?.[resolution]
  return Array.isArray(rows) ? rows : []
}

export function formatTemporalPercent(value: number | null): string {
  if (value === null || !Number.isFinite(value)) return '—'
  return `${(value * 100).toLocaleString('id-ID', { maximumFractionDigits: 1 })}%`
}

export function buildTemporalCoverageData(
  payload: TemporalCoveragePayload,
  resolution: TemporalResolution,
): TemporalCoverageData {
  const raw = coverageRows(payload, 'resolved_raw_pairs', resolution)
  const screenedByStart = new Map(
    coverageRows(payload, 'rule_screened_pairs', resolution).map((row) => [row.start, row]),
  )
  const rows = raw.map((row): TemporalCoverageRow => {
    const screened = screenedByStart.get(row.start)
    const partial = row.partial || screened?.partial === true
    const fromCensored = row.from_censored || screened?.from_censored === true
    const toCensored = row.to_censored || screened?.to_censored === true
    return {
      id: row.start,
      start: row.start,
      end: row.end,
      x: new Date(row.start),
      coverage: row.coverage,
      retention: screened?.retention ?? null,
      expectedSlots: row.expected_slots,
      exactPairCount: row.exact_pair_count,
      screenedPairCount: screened?.view_pair_count ?? 0,
      partial,
      fromCensored,
      toCensored,
      eligible: Object.fromEntries(
        coverageThresholds.map((threshold) => [threshold, row.eligible[threshold] === true]),
      ) as Record<CoverageThreshold, boolean>,
    }
  })
  const expectedSlots = rows.reduce((total, row) => total + row.expectedSlots, 0)
  const exactPairCount = rows.reduce((total, row) => total + row.exactPairCount, 0)
  const screenedPairCount = rows.reduce((total, row) => total + row.screenedPairCount, 0)
  const sourceDenseRegimes = coverageViews(payload).resolved_raw_pairs?.dense_regimes

  return {
    rows,
    coverage: rows.map((row) => row.coverage),
    retention: rows.map((row) => row.retention),
    partialMarkers: rows.map((row) => row.partial ? row.coverage : null),
    censoredMarkers: rows.map((row) => (
      row.fromCensored || row.toCensored ? row.coverage : null
    )),
    totals: {
      expectedSlots,
      exactPairCount,
      screenedPairCount,
      coverage: expectedSlots > 0 ? exactPairCount / expectedSlots : null,
      retention: exactPairCount > 0 ? screenedPairCount / exactPairCount : null,
    },
    eligibility: Object.fromEntries(
      coverageThresholds.map((threshold) => [
        threshold,
        rows.filter((row) => row.eligible[threshold]).length,
      ]),
    ) as Record<CoverageThreshold, number>,
    denseRegimes: Object.fromEntries(
      coverageThresholds.map((threshold) => [
        threshold,
        sourceDenseRegimes?.[threshold] ?? [],
      ]),
    ) as Record<CoverageThreshold, DenseRegimeInput[]>,
  }
}

function localWeekdayAndHour(isoDateTime: string): { weekday: number; hour: number } {
  const date = isoDateTime.slice(0, 10)
  const utcDay = new Date(`${date}T00:00:00Z`).getUTCDay()
  return {
    weekday: (utcDay + 6) % 7,
    hour: Number(isoDateTime.slice(11, 13)),
  }
}

export function buildWeekdayHourMatrix(
  payload: TemporalCoveragePayload,
  view: TemporalView,
): WeekdayHourMatrixData {
  const cells = Array.from({ length: 7 * 24 }, (_, index): WeekdayHourCell => {
    const weekday = Math.floor(index / 24)
    const hour = index % 24
    return {
      id: `${weekday}-${hour}`,
      weekday,
      weekdayLabel: weekdayLabels[weekday],
      hour,
      expectedSlots: 0,
      exactPairCount: 0,
      viewPairCount: 0,
      exposureSeconds: 0,
      coverage: null,
      retention: null,
      partial: false,
      censored: false,
    }
  })

  for (const row of coverageRows(payload, view, 'hourly')) {
    const { weekday, hour } = localWeekdayAndHour(row.start)
    const cell = cells[weekday * 24 + hour]
    cell.expectedSlots += row.expected_slots
    cell.exactPairCount += row.exact_pair_count
    cell.viewPairCount += row.view_pair_count
    cell.exposureSeconds += row.exposure_seconds
    cell.partial ||= row.partial
    cell.censored ||= row.from_censored || row.to_censored
  }

  for (const cell of cells) {
    cell.coverage = cell.expectedSlots > 0 ? cell.exactPairCount / cell.expectedSlots : null
    cell.retention = cell.exactPairCount > 0 ? cell.viewPairCount / cell.exactPairCount : null
  }

  const exposureSeconds = cells.reduce((total, cell) => total + cell.exposureSeconds, 0)
  const localWeeks = exposureSeconds / (7 * 24 * 60 * 60)
  return { cells, localWeeks, hasTwoLocalWeeks: localWeeks >= 2 }
}

function distributionChannel(
  key: 'suhu' | 'rh',
  metadata: { name?: string; unit?: string } | undefined,
  rows: DistributionBinInput[],
): TemporalDistributionChannel {
  const unit = key === 'suhu' ? '°C' : '%'
  return {
    key,
    name: metadata?.name ?? (key === 'suhu' ? 'Suhu' : 'RH'),
    unit,
    points: rows.map((row) => {
      const censored = row.from_censored || row.to_censored
      const statistics = row.statistics[key]
      const missing = censored || row.statistics.count === 0
      return {
        x: new Date(row.start),
        median: missing ? null : statistics.median,
        q1: missing ? null : statistics.q1,
        q3: missing ? null : statistics.q3,
        mad: statistics.mad,
        count: row.statistics.count,
        censored,
      }
    }),
  }
}

export function buildTemporalDistributionData(
  payload: TemporalDistributionPayload,
  view: TemporalView,
  resolution: TemporalResolution,
): TemporalDistributionData {
  const source = distributionViews(payload)[view]
  const rows = distributionRows(payload, view, resolution)
  const channels = [
    distributionChannel('suhu', source?.channels?.suhu, rows),
    distributionChannel('rh', source?.channels?.rh, rows),
  ] as const

  return {
    channels,
    rows: rows.map((row) => ({
      id: row.start,
      start: row.start,
      end: row.end,
      count: row.statistics.count,
      censored: row.from_censored || row.to_censored,
      suhuMedian: row.statistics.suhu.median,
      suhuQ1: row.statistics.suhu.q1,
      suhuQ3: row.statistics.suhu.q3,
      suhuMad: row.statistics.suhu.mad,
      rhMedian: row.statistics.rh.median,
      rhQ1: row.statistics.rh.q1,
      rhQ3: row.statistics.rh.q3,
      rhMad: row.statistics.rh.mad,
    })),
    hasData: rows.some((row) => row.statistics.count > 0),
    driftConclusions: {
      suhu: source?.drift_conclusions?.suhu,
      rh: source?.drift_conclusions?.rh,
    },
  }
}
