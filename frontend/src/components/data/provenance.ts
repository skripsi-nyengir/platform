import type { ChipProps } from '@mui/material'

export type Provenance = 'simulated_preview' | 'artifact_backed'
export type EdaProvenance = 'canonical_release' | 'algorithm_equivalent'

export const provenancePresentation: Readonly<
  Record<Provenance, { label: string; color: ChipProps['color'] }>
> = Object.freeze({
  simulated_preview: { label: 'Simulasi preview', color: 'warning' },
  artifact_backed: { label: 'Artifact asli', color: 'success' },
})

export const edaProvenancePresentation: Readonly<
  Record<EdaProvenance, { label: string; color: ChipProps['color'] }>
> = Object.freeze({
  canonical_release: { label: 'Rilis v3 terpublikasi (paritas kanonik)', color: 'success' },
  algorithm_equivalent: { label: 'Komputasi rentang setara-algoritme', color: 'info' },
})

export function formatProvenance(provenance: Provenance): string {
  return provenancePresentation[provenance].label
}
