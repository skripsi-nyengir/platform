import { Chip, Stack, Typography } from '@mui/material'
import type { Availability, Freshness } from '../../contracts/common'
import { tokens } from '../../theme/tokens'

export interface SensorStatusProps {
  freshness: Freshness
  availability: Availability
  ageSeconds?: number
  timestamp?: string
  statusOnly?: boolean
}

const technicalTextSx = {
  fontFamily: tokens.font.data,
  fontVariantNumeric: 'tabular-nums',
  overflowWrap: 'anywhere',
} as const

export function SensorStatus({
  freshness,
  availability,
  ageSeconds,
  timestamp,
  statusOnly = false,
}: SensorStatusProps) {
  const label = availability === 'unknown'
    ? 'Current status unknown'
    : availability === 'offline'
      ? 'Offline sensor'
      : freshness === 'stale'
        ? 'Stale telemetry'
        : freshness === 'fresh'
          ? 'Fresh telemetry'
          : 'Telemetry freshness unknown'
  const color = availability !== 'online' || freshness === 'unknown'
    ? 'default'
    : freshness === 'stale'
      ? 'warning'
      : 'success'

  return (
    <Stack role="status" aria-label={label} spacing={0.5} sx={{ alignItems: 'flex-start' }}>
      <Chip label={label} color={color} size="small" />
      {statusOnly ? null : (
        <Typography variant="caption" color="text.secondary" sx={technicalTextSx}>
          {timestamp === undefined ? 'Last telemetry timestamp unknown' : `Last telemetry: ${timestamp}`}
          {'; '}
          {ageSeconds === undefined ? 'Telemetry age unknown' : `Telemetry age: ${ageSeconds} seconds`}
        </Typography>
      )}
    </Stack>
  )
}
