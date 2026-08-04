import { FormControl, InputLabel, Select, Stack, TextField } from '@mui/material'
import { useId } from 'react'
import { SensorIdSchema, sensorIds, sensorLabels } from '../../contracts/common'
import {
  liveRanges,
  resolveLiveRange,
  type LiveRange,
  type LiveUrlFilters,
} from '../../features/filters/urlFilters'
import { tokens } from '../../theme/tokens'

export interface TemporalFilterBarProps {
  value: LiveUrlFilters
  onChange: (patch: Partial<LiveUrlFilters>) => void
  allowAllSensors?: boolean
}

const liveRangeLabels: Record<LiveRange, string> = {
  '1m': 'Last 1 minute',
  '5m': 'Last 5 minutes',
  '10m': 'Last 10 minutes',
  '15m': 'Last 15 minutes',
  '30m': 'Last 30 minutes',
  '1h': 'Last 1 hour',
  '6h': 'Last 6 hours',
  '12h': 'Last 12 hours',
  '24h': 'Last 24 hours',
  custom: 'Custom',
}

export function TemporalFilterBar({
  value,
  onChange,
  allowAllSensors = false,
}: TemporalFilterBarProps) {
  const sensorId = useId()
  const sensorLabelId = useId()
  const rangeId = useId()
  const rangeLabelId = useId()

  return (
    <Stack
      role="group"
      aria-label="Temporal filters"
      direction="row"
      spacing={2}
      useFlexGap
      sx={{
        width: '100%',
        minWidth: 0,
        alignItems: 'center',
        flexWrap: 'wrap',
        rowGap: 1,
        '& > .MuiFormControl-root': { minWidth: 136 },
        '& > .MuiTextField-root': {
          flex: '1 1 220px',
          minWidth: 220,
          maxWidth: 320,
        },
        '& .MuiInputBase-root': {
          fontFamily: tokens.font.data,
          fontVariantNumeric: 'tabular-nums',
        },
      }}
    >
      <FormControl size="small">
        <InputLabel id={sensorLabelId} htmlFor={sensorId} shrink={allowAllSensors ? true : undefined}>
          Sensor
        </InputLabel>
        <Select<string>
          native
          id={sensorId}
          labelId={sensorLabelId}
          label="Sensor"
          value={value.sensor ?? ''}
          onChange={(event) => {
            if (event.target.value === '' && allowAllSensors) {
              onChange({ sensor: undefined })
              return
            }
            const sensor = SensorIdSchema.safeParse(event.target.value)
            if (sensor.success) onChange({ sensor: sensor.data })
          }}
        >
          {allowAllSensors ? <option value="">All sensors</option> : null}
          {!allowAllSensors && value.sensor === undefined ? (
            <option value="" disabled>
              Select sensor
            </option>
          ) : null}
          {sensorIds.map((sensorId) => (
            <option key={sensorId} value={sensorId}>
              {sensorLabels[sensorId]}
            </option>
          ))}
        </Select>
      </FormControl>
      <FormControl size="small">
        <InputLabel id={rangeLabelId} htmlFor={rangeId}>
          Range
        </InputLabel>
        <Select<string>
          native
          id={rangeId}
          labelId={rangeLabelId}
          label="Range"
          value={value.range}
          onChange={(event) => {
            const range = liveRanges.find((candidate) => candidate === event.target.value)
            if (range === undefined) return
            if (range === 'custom') {
              const resolved = resolveLiveRange(value)
              onChange({ range, from: resolved.from, to: resolved.to })
              return
            }
            onChange({ range, from: undefined, to: undefined })
          }}
        >
          {liveRanges.map((range) => (
            <option key={range} value={range}>
              {liveRangeLabels[range]}
            </option>
          ))}
        </Select>
      </FormControl>
      {value.range === 'custom' ? (
        <>
          <TextField
            size="small"
            label="From"
            type="text"
            value={value.from ?? ''}
            onChange={(event) => onChange({ from: event.target.value })}
          />
          <TextField
            size="small"
            label="To"
            type="text"
            value={value.to ?? ''}
            onChange={(event) => onChange({ to: event.target.value })}
          />
        </>
      ) : null}
    </Stack>
  )
}
