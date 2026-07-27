import type { EdaReasonCode } from '../../contracts/eda'

const reasonLabels = {
  no_exact_pairs: 'Pasangan timestamp exact tidak tersedia',
  no_selectable_excerpt: 'Excerpt kualitas yang dapat dipilih tidak tersedia',
  no_positive_deltas: 'Selisih waktu positif tidak tersedia',
  insufficient_representative_cadence: 'Irama sampel representatif belum cukup',
  no_exposed_calendar_bins: 'Bin kalender dengan paparan tidak tersedia',
  insufficient_nonconstant_pairs: 'Pasangan nonkonstan belum cukup',
  insufficient_rolling_windows: 'Jendela bergulir belum cukup',
  insufficient_stationarity_sensitivity_tier: 'Segmen sensitivitas struktur temporal belum cukup',
  insufficient_stationarity_primary_tier: 'Segmen utama struktur temporal belum cukup',
  insufficient_daily_medians: 'Median harian belum cukup',
  insufficient_dense_daily_pairs: 'Pasangan median harian belum cukup',
  block_longer_than_run: 'Blok lebih panjang daripada run',
  source_identity_unavailable: 'Identitas sumber tidak tersedia',
  section_compute_failed: 'Perhitungan bagian tidak berhasil',
  dependency_unavailable: 'Data pendukung tidak tersedia',
  resource_limit_exceeded: 'Batas sumber daya terlampaui',
} satisfies Record<EdaReasonCode, string>

export function edaReasonLabel(reasonCode: string | null): string {
  if (reasonCode === null) return 'Alasan tidak tersedia'
  return reasonLabels[reasonCode as EdaReasonCode] ?? (reasonCode.trim() || 'Alasan tidak tersedia')
}

export function formatEdaReasonDetail(reasonCode: string | null, detail: string): string {
  return `${edaReasonLabel(reasonCode)}. ${detail}`
}
