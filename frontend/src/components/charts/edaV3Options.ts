import { darken, type Theme } from '@mui/material/styles'
import type {
  JointDensityPayload,
  QualityExcerptPayload,
  QualityOverviewPayload,
  UnivariatePayload,
} from '../../contracts/eda'
import { getChartColors } from './muiChartTheme'

const VIEW_IDS = ['resolved_raw_pairs', 'rule_screened_pairs'] as const
const DOMAIN_KEYS = ['underflow', 'in_domain', 'overflow'] as const
const EXCERPT_FLAGS = [
  'non_finite',
  'disconnected',
  'zero',
  'range',
  'duplicate',
  'conflicting_duplicate',
  'stale',
  'rule_screened',
] as const

export type EdaV3ViewId = (typeof VIEW_IDS)[number]
export type DomainKey = (typeof DOMAIN_KEYS)[number]
export type ExcerptFlag = (typeof EXCERPT_FLAGS)[number]

export const EDA_V3_VIEW_LABELS: Record<EdaV3ViewId, string> = {
  resolved_raw_pairs: 'Resolved raw',
  rule_screened_pairs: 'Rule-screened',
}

export const DOMAIN_LABELS: Record<DomainKey, string> = {
  underflow: 'Di bawah domain',
  in_domain: 'Dalam domain',
  overflow: 'Di atas domain',
}

export const EXCERPT_FLAG_LABELS: Record<ExcerptFlag, string> = {
  non_finite: 'Non-finite',
  disconnected: 'Terputus',
  zero: 'Nol',
  range: 'Di luar rentang',
  duplicate: 'Duplikat',
  conflicting_duplicate: 'Duplikat konflik',
  stale: 'Stale',
  rule_screened: 'Dipertahankan',
}

interface JsonRecord {
  [key: string]: unknown
}

function asRecord(value: unknown): JsonRecord | null {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
    ? value as JsonRecord
    : null
}

function asCount(value: unknown): number | null {
  return typeof value === 'number' && Number.isInteger(value) && value >= 0 ? value : null
}

function asFiniteNumber(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

function fraction(count: number, total: number): number {
  return total === 0 ? 0 : count / total
}

export interface PairingAuditSegment {
  id: 'intersection' | 'missing_suhu' | 'missing_rh' | 'screened' | 'excluded'
  label: string
  count: number
  percent: number
  color: string
}

export interface PairingAuditBar {
  id: 'timestamps' | 'pairs'
  label: string
  total: number
  segments: PairingAuditSegment[]
}

export interface PairingAuditData {
  bars: [PairingAuditBar, PairingAuditBar]
  conservationStatus: string
}

export function buildPairingAuditData(
  payload: QualityOverviewPayload,
  theme: Theme,
): PairingAuditData | null {
  const audit = asRecord(payload.source_audit)
  const conservation = asRecord(payload.count_conservation)
  if (audit === null || conservation === null) return null

  const union = asCount(audit.union_timestamps)
  const intersection = asCount(audit.intersection_timestamps)
  const missingSuhu = asCount(audit.missing_idx0_timestamps)
  const missingRh = asCount(audit.missing_idx1_timestamps)
  const exact = asCount(audit.exact_pair_count)
  const screened = asCount(audit.rule_screened_pair_count)
  const conservationStatus = typeof conservation.status === 'string' ? conservation.status : null
  if (
    union === null || intersection === null || missingSuhu === null || missingRh === null ||
    exact === null || screened === null || conservationStatus === null || screened > exact
  ) return null

  const colors = getChartColors(theme)
  const excluded = exact - screened
  return {
    conservationStatus,
    bars: [
      {
        id: 'timestamps',
        label: 'Union timestamp',
        total: union,
        segments: [
          {
            id: 'intersection',
            label: 'Intersection',
            count: intersection,
            percent: fraction(intersection, union) * 100,
            color: colors.temperature,
          },
          {
            id: 'missing_suhu',
            label: 'Tanpa Suhu',
            count: missingSuhu,
            percent: fraction(missingSuhu, union) * 100,
            color: colors.anomalyScore,
          },
          {
            id: 'missing_rh',
            label: 'Tanpa RH',
            count: missingRh,
            percent: fraction(missingRh, union) * 100,
            color: colors.normalPoint,
          },
        ],
      },
      {
        id: 'pairs',
        label: 'Pasangan exact',
        total: exact,
        segments: [
          {
            id: 'screened',
            label: 'Rule-screened',
            count: screened,
            percent: fraction(screened, exact) * 100,
            color: colors.humidity,
          },
          {
            id: 'excluded',
            label: 'Dikecualikan aturan kualitas',
            count: excluded,
            percent: fraction(excluded, exact) * 100,
            color: theme.palette.text.secondary,
          },
        ],
      },
    ],
  }
}

export interface JointDensityViewData {
  id: EdaV3ViewId
  label: string
  matrix: number[][]
  pairCount: number
}

export interface JointDensityData {
  temperatureEdges: number[]
  humidityEdges: number[]
  views: [JointDensityViewData, JointDensityViewData]
  maximumCount: number
  colors: readonly string[]
}

export function buildJointDensityData(
  payload: JointDensityPayload,
  pairCounts: { exact_pairs: number; screened_pairs: number },
  theme: Theme,
): JointDensityData | null {
  const raw = payload.views.resolved_raw_pairs.histogram
  const screened = payload.views.rule_screened_pairs.histogram
  if (raw.length === 0 || screened.length === 0) return null
  const maximumCount = Math.max(0, ...raw.flat(), ...screened.flat())
  const chartColors = getChartColors(theme)
  return {
    temperatureEdges: payload.edges.temperature_c,
    humidityEdges: payload.edges.relative_humidity_pct,
    maximumCount,
    colors: [
      theme.palette.background.default,
      chartColors.normalPoint,
      chartColors.temperature,
      chartColors.humidity,
    ],
    views: [
      {
        id: 'resolved_raw_pairs',
        label: EDA_V3_VIEW_LABELS.resolved_raw_pairs,
        matrix: raw,
        pairCount: pairCounts.exact_pairs,
      },
      {
        id: 'rule_screened_pairs',
        label: EDA_V3_VIEW_LABELS.rule_screened_pairs,
        matrix: screened,
        pairCount: pairCounts.screened_pairs,
      },
    ],
  }
}

export function jointDensityColor(
  count: number,
  maximumCount: number,
  colors: readonly string[],
): string {
  if (colors.length === 0) return 'transparent'
  if (count <= 0 || maximumCount <= 0) return colors[0]
  const scaled = Math.log1p(count) / Math.log1p(maximumCount)
  const index = Math.min(colors.length - 1, Math.max(1, Math.ceil(scaled * (colors.length - 1))))
  return colors[index]
}

interface AxisAudit {
  total: number
  finite: number
  nonFinite: number
  underflow: number
  inDomain: number
  overflow: number
  excludedFinite: number
}

function axisAudit(value: unknown): AxisAudit | null {
  const audit = asRecord(value)
  if (audit === null) return null
  const values = [
    asCount(audit.total),
    asCount(audit.finite),
    asCount(audit.non_finite),
    asCount(audit.underflow),
    asCount(audit.in_domain),
    asCount(audit.overflow),
    asCount(audit.excluded_finite),
  ]
  if (values.some((item) => item === null)) return null
  const [total, finite, nonFinite, underflow, inDomain, overflow, excludedFinite] = values as number[]
  return { total, finite, nonFinite, underflow, inDomain, overflow, excludedFinite }
}

export interface UnivariateViewData extends AxisAudit {
  id: EdaV3ViewId
  label: string
  color: string
  histogram: number[]
  ecdfCount: number[]
  ecdfFraction: number[]
  ecdfDenominator: number
}

export interface UnivariateChannelData {
  id: 'Suhu' | 'RH'
  label: string
  unit: '°C' | '%'
  edges: number[]
  centers: number[]
  ecdfX: number[]
  views: [UnivariateViewData, UnivariateViewData]
}

export function buildUnivariateData(
  payload: UnivariatePayload,
  overview: QualityOverviewPayload,
  theme: Theme,
): UnivariateChannelData[] {
  const conservation = asRecord(overview.count_conservation)
  const auditRoot = asRecord(conservation?.univariate)
  if (auditRoot === null) return []
  const colors = getChartColors(theme)

  return (['Suhu', 'RH'] as const).flatMap((channelId) => {
    const channel = payload.channels[channelId]
    const channelAudits = asRecord(auditRoot[channelId])
    if (channelAudits === null) return []
    const centers = channel.edges.slice(0, -1).map((edge, index) => (
      edge + ((channel.edges[index + 1] ?? edge) - edge) / 2
    ))
    const views = VIEW_IDS.map((viewId, index) => {
      const audit = axisAudit(channelAudits[viewId])
      if (audit === null) return null
      const view = channel.views[viewId]
      return {
        ...audit,
        id: viewId,
        label: EDA_V3_VIEW_LABELS[viewId],
        color: index === 0 ? colors.temperature : colors.humidity,
        histogram: view.histogram,
        ecdfCount: view.ecdf_count,
        ecdfFraction: view.ecdf_fraction,
        ecdfDenominator: view.ecdf_count.at(-1) ?? 0,
      }
    })
    if (views.some((view) => view === null)) return []
    return [{
      id: channelId,
      label: channelId === 'Suhu' ? 'Suhu' : 'Kelembapan relatif',
      unit: channel.unit,
      edges: channel.edges,
      centers,
      ecdfX: channel.edges.slice(1),
      views: views as [UnivariateViewData, UnivariateViewData],
    }]
  })
}

export interface DomainFateCell {
  temperature: DomainKey
  humidity: DomainKey
  count: number
  backgroundColor: string
  textColor: string
}

export interface DomainFateTable {
  id: EdaV3ViewId
  label: string
  totalPairs: number
  nonFinitePairs: number
  excludedPairs: number
  cells: DomainFateCell[][]
}

function countMatrix(value: unknown): number[][] | null {
  if (!Array.isArray(value) || value.length !== 3) return null
  const matrix = value.map((row) => (
    Array.isArray(row) && row.length === 3 ? row.map(asCount) : []
  ))
  return matrix.every((row) => row.length === 3 && row.every((item) => item !== null))
    ? matrix as number[][]
    : null
}

export function buildDomainFateData(
  payload: QualityOverviewPayload,
  theme: Theme,
): DomainFateTable[] {
  const conservation = asRecord(payload.count_conservation)
  const joint = asRecord(conservation?.joint)
  if (joint === null) return []

  return VIEW_IDS.flatMap((viewId, viewIndex) => {
    const audit = asRecord(joint[viewId])
    const matrix = countMatrix(audit?.axis_status_matrix)
    const totalPairs = asCount(audit?.total_pairs)
    const nonFinitePairs = asCount(audit?.non_finite_pairs)
    const excludedPairs = asCount(audit?.excluded_pairs)
    if (matrix === null || totalPairs === null || nonFinitePairs === null || excludedPairs === null) return []
    const maximum = Math.max(0, ...matrix.flat())
    const baseColor = viewIndex === 0 ? theme.palette.primary.main : theme.palette.success.main
    return [{
      id: viewId,
      label: EDA_V3_VIEW_LABELS[viewId],
      totalPairs,
      nonFinitePairs,
      excludedPairs,
      cells: matrix.map((row, temperatureIndex) => row.map((count, humidityIndex) => {
        const intensity = maximum === 0 ? 0 : count / maximum
        const backgroundColor = darken(baseColor, 0.85 - intensity * 0.6)
        return {
          temperature: DOMAIN_KEYS[temperatureIndex],
          humidity: DOMAIN_KEYS[humidityIndex],
          count,
          backgroundColor,
          textColor: theme.palette.getContrastText(backgroundColor),
        }
      })),
    }]
  })
}

export interface QualityIntegrityData {
  duplicateGroups: { count: number; denominator: number; denominatorLabel: string }
  conflictingPairs: { count: number; denominator: number; denominatorLabel: string }
  cadence: {
    observedMedianSeconds: number
    expectedSeconds: 6
    acceptanceMinimumSeconds: 5
    acceptanceMaximumSeconds: 7
    primaryGapSeconds: 30
    gapCount: number
    status: string
    displayMaximumSeconds: number
    acceptanceLeftPercent: number
    acceptanceWidthPercent: number
    expectedPositionPercent: number
    observedPositionPercent: number
  }
}

export function buildQualityIntegrityData(
  payload: QualityOverviewPayload,
): QualityIntegrityData | null {
  const audit = asRecord(payload.source_audit)
  if (audit === null) return null
  const duplicateGroups = asCount(audit.duplicate_group_count)
  const conflictingPairs = asCount(audit.conflicting_duplicate_pair_count)
  const rawRows = asCount(audit.row_count)
  const exactPairs = asCount(audit.exact_pair_count)
  const observedMedian = asFiniteNumber(audit.observed_median_positive_delta_at_most_gap)
  const gapCount = asCount(audit.gap_above_primary_count)
  const status = typeof audit.cadence_gate === 'string' ? audit.cadence_gate : null
  if (
    duplicateGroups === null || conflictingPairs === null || rawRows === null ||
    exactPairs === null || observedMedian === null || gapCount === null || status === null
  ) return null
  const expectedSeconds = 6 as const
  const acceptanceMinimumSeconds = 5 as const
  const acceptanceMaximumSeconds = 7 as const
  const displayMaximumSeconds = Math.max(expectedSeconds * 2, Math.ceil(observedMedian))
  return {
    duplicateGroups: {
      count: duplicateGroups,
      denominator: rawRows,
      denominatorLabel: 'baris sumber mentah',
    },
    conflictingPairs: {
      count: conflictingPairs,
      denominator: exactPairs,
      denominatorLabel: 'pasangan exact',
    },
    cadence: {
      observedMedianSeconds: observedMedian,
      expectedSeconds,
      acceptanceMinimumSeconds,
      acceptanceMaximumSeconds,
      primaryGapSeconds: 30,
      gapCount,
      status,
      displayMaximumSeconds,
      acceptanceLeftPercent: (acceptanceMinimumSeconds / displayMaximumSeconds) * 100,
      acceptanceWidthPercent: ((acceptanceMaximumSeconds - acceptanceMinimumSeconds) / displayMaximumSeconds) * 100,
      expectedPositionPercent: (expectedSeconds / displayMaximumSeconds) * 100,
      observedPositionPercent: Math.min(100, (observedMedian / displayMaximumSeconds) * 100),
    },
  }
}

export interface ExcerptRecordData {
  id: string
  timestampEpochSeconds: number
  timestamp: Date
  positionPercent: number
  suhu: number | null
  rh: number | null
  flags: Record<ExcerptFlag, boolean>
  activeFlags: ExcerptFlag[]
}

export interface ExcerptLinePoint {
  timestamp: Date
  value: number | null
}

export interface ExcerptFlagStyle {
  id: ExcerptFlag
  label: string
  color: string
}

export interface QualityExcerptData {
  selectionKind: string
  from: Date
  to: Date
  records: ExcerptRecordData[]
  temperature: ExcerptLinePoint[]
  humidity: ExcerptLinePoint[]
  flagStyles: ExcerptFlagStyle[]
}

function excerptRecord(value: unknown, index: number): ExcerptRecordData | null {
  const record = asRecord(value)
  const timestamp = asCount(record?.timestamp_epoch_s)
  if (record === null || timestamp === null) return null
  const flags = Object.fromEntries(EXCERPT_FLAGS.map((flag) => [flag, record[flag] === true])) as Record<ExcerptFlag, boolean>
  const activeFlags = EXCERPT_FLAGS.filter((flag) => flags[flag])
  const suhu = record.suhu === null ? null : asFiniteNumber(record.suhu)
  const rh = record.rh === null ? null : asFiniteNumber(record.rh)
  if ((record.suhu !== null && suhu === null) || (record.rh !== null && rh === null)) return null
  return {
    id: `excerpt-${timestamp}-${index}`,
    timestampEpochSeconds: timestamp,
    timestamp: new Date(timestamp * 1_000),
    positionPercent: 0,
    suhu,
    rh,
    flags,
    activeFlags,
  }
}

function gapAwarePoints(
  records: readonly ExcerptRecordData[],
  field: 'suhu' | 'rh',
): ExcerptLinePoint[] {
  const points: ExcerptLinePoint[] = []
  records.forEach((record, index) => {
    const previous = records[index - 1]
    if (previous !== undefined && record.timestampEpochSeconds - previous.timestampEpochSeconds > 30) {
      points.push({ timestamp: record.timestamp, value: null })
    }
    points.push({ timestamp: record.timestamp, value: record[field] })
  })
  return points
}

export function buildQualityExcerptData(
  payload: QualityExcerptPayload,
  theme: Theme,
): QualityExcerptData | null {
  const records = payload.records.map(excerptRecord)
  if (records.some((record) => record === null)) return null
  const validRecords = records as ExcerptRecordData[]
  const firstTimestamp = validRecords[0]?.timestampEpochSeconds ?? 0
  const lastTimestamp = validRecords.at(-1)?.timestampEpochSeconds ?? firstTimestamp
  const duration = lastTimestamp - firstTimestamp
  const positionedRecords = validRecords.map((record) => ({
    ...record,
    positionPercent: duration === 0
      ? 0
      : ((record.timestampEpochSeconds - firstTimestamp) / duration) * 100,
  }))
  const chartColors = getChartColors(theme)
  const flagColors: Record<ExcerptFlag, string> = {
    non_finite: theme.palette.text.primary,
    disconnected: theme.palette.text.secondary,
    zero: theme.palette.info.main,
    range: theme.palette.warning.main,
    duplicate: theme.palette.primary.main,
    conflicting_duplicate: theme.palette.error.main,
    stale: theme.palette.warning.dark,
    rule_screened: theme.palette.success.main,
  }
  return {
    selectionKind: payload.selection_kind,
    from: new Date(`${payload.from}+07:00`),
    to: new Date(`${payload.to}+07:00`),
    records: positionedRecords,
    temperature: gapAwarePoints(positionedRecords, 'suhu'),
    humidity: gapAwarePoints(positionedRecords, 'rh'),
    flagStyles: EXCERPT_FLAGS.map((id) => ({
      id,
      label: EXCERPT_FLAG_LABELS[id],
      color: id === 'rule_screened' ? chartColors.humidity : flagColors[id],
    })),
  }
}

export function formatFinitePercent(count: number, denominator: number): string {
  return denominator > 0 && Number.isFinite(count) && Number.isFinite(denominator)
    ? `${((count / denominator) * 100).toFixed(2)}%`
    : '—'
}
