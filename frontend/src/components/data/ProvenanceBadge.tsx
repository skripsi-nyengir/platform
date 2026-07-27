import { Chip } from '@mui/material'
import {
  edaProvenancePresentation,
  provenancePresentation,
  type EdaProvenance,
  type Provenance,
} from './provenance'

type ProvenanceBadgeProps = {
  provenance: Provenance
  edaProvenance?: never
} | {
  provenance?: never
  edaProvenance: EdaProvenance
}

export function ProvenanceBadge(props: ProvenanceBadgeProps) {
  const presentation = props.edaProvenance === undefined
    ? provenancePresentation[props.provenance]
    : edaProvenancePresentation[props.edaProvenance]
  return <Chip label={presentation.label} color={presentation.color} size="small" />
}
