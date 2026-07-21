import {
  FormControl,
  InputLabel,
  Paper,
  Select,
  Stack,
  TextField,
} from '@mui/material'
import { useId } from 'react'
import { TemporalFilterBar } from '../../components/filters/TemporalFilterBar'
import { EdaFieldSchema, type EdaField } from '../../contracts/eda'
import { tokens } from '../../theme/tokens'
import type { UrlFilters } from '../filters/urlFilters'

export interface EdaFiltersValue extends UrlFilters {
  sampleSize: number
  xField: EdaField
  yField: EdaField
}

export interface EdaFiltersProps {
  value: EdaFiltersValue
  onChange: (patch: Partial<EdaFiltersValue>) => void
}

function boundedInteger(value: string, minimum: number, maximum: number): number | undefined {
  const parsed = Number(value)
  if (!Number.isFinite(parsed)) return undefined
  return Math.min(maximum, Math.max(minimum, Math.trunc(parsed)))
}

function differentField(field: EdaField): EdaField | undefined {
  return EdaFieldSchema.options.find((candidate) => candidate !== field)
}

export function EdaFilters({ value, onChange }: EdaFiltersProps) {
  const xFieldId = useId()
  const xFieldLabelId = useId()
  const yFieldId = useId()
  const yFieldLabelId = useId()

  return (
    <Paper variant="outlined" sx={{ minWidth: 0, p: 4 }}>
      <Stack
        role="group"
        aria-label="EDA filters"
        spacing={2}
        sx={{
          '& > [aria-label="Temporal filters"] .MuiInputBase-root': {
            fontFamily: tokens.font.ui,
            fontVariantNumeric: 'normal',
          },
        }}
      >
        <TemporalFilterBar value={value} onChange={onChange} allowAllSensors />
        <Stack
          direction="row"
          spacing={2}
          useFlexGap
          sx={{
            minWidth: 0,
            alignItems: 'center',
            flexWrap: 'wrap',
          }}
        >
          <TextField
            size="small"
            label="Sample size"
            type="number"
            value={value.sampleSize}
            slotProps={{ htmlInput: { min: 100, max: 5_000, step: 100 } }}
            sx={{ minWidth: 160 }}
            onChange={(event) => {
              const sampleSize = boundedInteger(event.target.value, 100, 5_000)
              if (sampleSize !== undefined) onChange({ sampleSize })
            }}
          />
          <FormControl size="small">
            <InputLabel id={xFieldLabelId} htmlFor={xFieldId}>X field</InputLabel>
            <Select
              native
              id={xFieldId}
              labelId={xFieldLabelId}
              label="X field"
              value={value.xField}
              onChange={(event) => {
                const parsed = EdaFieldSchema.safeParse(event.target.value)
                if (!parsed.success) return
                if (parsed.data !== value.yField) {
                  onChange({ xField: parsed.data })
                  return
                }
                const yField = differentField(parsed.data)
                if (yField !== undefined) onChange({ xField: parsed.data, yField })
              }}
            >
              {EdaFieldSchema.options.map((field) => (
                <option key={field} value={field}>{field}</option>
              ))}
            </Select>
          </FormControl>
          <FormControl size="small">
            <InputLabel id={yFieldLabelId} htmlFor={yFieldId}>Y field</InputLabel>
            <Select
              native
              id={yFieldId}
              labelId={yFieldLabelId}
              label="Y field"
              value={value.yField}
              onChange={(event) => {
                const parsed = EdaFieldSchema.safeParse(event.target.value)
                if (!parsed.success) return
                if (parsed.data !== value.xField) {
                  onChange({ yField: parsed.data })
                  return
                }
                const xField = differentField(parsed.data)
                if (xField !== undefined) onChange({ xField, yField: parsed.data })
              }}
            >
              {EdaFieldSchema.options.map((field) => (
                <option key={field} value={field}>{field}</option>
              ))}
            </Select>
          </FormControl>
        </Stack>
      </Stack>
    </Paper>
  )
}
