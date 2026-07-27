import { FormControl, InputLabel, Select } from '@mui/material'
import { useId } from 'react'
import type { ModelEvaluationSummary } from '../../contracts/modelEvaluation'

export interface VersionSelectProps {
  versions: readonly ModelEvaluationSummary[]
  value?: string
  onChange: (version: string) => void
}

export function VersionSelect({ versions, value, onChange }: VersionSelectProps) {
  const selectId = useId()
  const labelId = useId()

  return (
    <FormControl size="small">
      <InputLabel id={labelId} htmlFor={selectId}>
        Evaluation track
      </InputLabel>
      <Select<string>
        native
        id={selectId}
        labelId={labelId}
        label="Evaluation track"
        value={value ?? ''}
        onChange={(event) => onChange(event.target.value)}
      >
        {value === undefined ? (
          <option value="" disabled>
            Select evaluation track
          </option>
        ) : null}
        {versions.map((version) => (
          <option key={version.version} value={version.version}>
            {version.label}
          </option>
        ))}
      </Select>
    </FormControl>
  )
}
