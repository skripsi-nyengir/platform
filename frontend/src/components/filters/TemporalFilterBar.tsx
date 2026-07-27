import { FormControl, InputLabel, Select, Stack, TextField } from '@mui/material'
import { useId } from 'react'
import { BucketSchema, SensorIdSchema, sensorIds, sensorLabels } from '../../contracts/common'
import type { UrlFilters } from '../../features/filters/urlFilters'
import { tokens } from '../../theme/tokens'

export interface TemporalFilterBarProps {
  value: Pick<UrlFilters, 'sensor' | 'from' | 'to' | 'bucket'>
  onChange: (patch: Partial<UrlFilters>) => void
  allowAllSensors?: boolean
}

export function TemporalFilterBar({
  value,
  onChange,
  allowAllSensors = false,
}: TemporalFilterBarProps) {
  const sensorId = useId()
  const sensorLabelId = useId()
  const bucketId = useId()
  const bucketLabelId = useId()

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
      <TextField
        size="small"
        label="From"
        type="text"
        value={value.from}
        onChange={(event) => onChange({ from: event.target.value })}
      />
      <TextField
        size="small"
        label="To"
        type="text"
        value={value.to}
        onChange={(event) => onChange({ to: event.target.value })}
      />
      <FormControl size="small">
        <InputLabel id={bucketLabelId} htmlFor={bucketId}>
          Bucket
        </InputLabel>
        <Select
          native
          id={bucketId}
          labelId={bucketLabelId}
          label="Bucket"
          value={value.bucket}
          onChange={(event) => {
            const bucket = BucketSchema.safeParse(event.target.value)
            if (bucket.success) onChange({ bucket: bucket.data })
          }}
        >
          {BucketSchema.options.map((bucket) => (
            <option key={bucket} value={bucket}>
              {bucket}
            </option>
          ))}
        </Select>
      </FormControl>
    </Stack>
  )
}
