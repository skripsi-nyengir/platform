import { Box, Paper, Stack, Typography } from '@mui/material'
import type { SystemStatusResponse } from '../../contracts/systemHealth'
import { tokens } from '../../theme/tokens'

const technicalTextSx = {
  fontFamily: tokens.font.data,
  fontVariantNumeric: 'tabular-nums',
  overflowWrap: 'anywhere',
} as const

export interface StatusSnapshotProps {
  snapshot: SystemStatusResponse
  displayedAt: string
  pollAgeSeconds: number
}

export function StatusSnapshot({ snapshot, displayedAt, pollAgeSeconds }: StatusSnapshotProps) {
  return (
    <Paper
      component="section"
      aria-labelledby="status-snapshot-heading"
      variant="outlined"
      sx={{ p: 4 }}
    >
      <Stack spacing={2}>
        <Typography id="status-snapshot-heading" variant="h2">
          Latest known system snapshot
        </Typography>
        <Box
          role="group"
          aria-label="Freshness snapshot"
          sx={{
            display: 'grid',
            gridTemplateColumns: 'repeat(2, minmax(0, 1fr))',
            gap: 3,
            alignItems: 'start',
            minWidth: 0,
          }}
        >
          <Stack
            component="section"
            role="region"
            aria-labelledby="status-poll-freshness-heading"
            spacing={0.5}
            sx={{ alignItems: 'flex-start', minWidth: 0 }}
          >
            <Typography id="status-poll-freshness-heading" variant="h3">
              Status-poll freshness
            </Typography>
            <Typography variant="body2">
              Status checked at (UTC):{' '}
              <Box component="span" sx={technicalTextSx}>{snapshot.checked_at}</Box>
            </Typography>
            <Typography variant="body2">
              Displayed at: <Box component="span" sx={technicalTextSx}>{displayedAt}</Box>
            </Typography>
            <Typography variant="body2">
              Status poll age:{' '}
              <Box component="span" sx={technicalTextSx}>{pollAgeSeconds} seconds</Box>
            </Typography>
            <Typography variant="caption" color="text.secondary">
              Poll age describes this retained snapshot, not the age of sensor telemetry.
            </Typography>
          </Stack>
          <Stack
            component="section"
            role="region"
            aria-labelledby="telemetry-freshness-heading"
            spacing={0.5}
            sx={{ alignItems: 'flex-start', minWidth: 0 }}
          >
            <Typography id="telemetry-freshness-heading" variant="h3">
              Historical corpus time
            </Typography>
            <Typography variant="body2">
              Historical corpus latest timestamp:{' '}
              {snapshot.telemetry.latest_ts === null ? (
                'Unavailable'
              ) : (
                <Box component="span" sx={technicalTextSx}>{snapshot.telemetry.latest_ts}</Box>
              )}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Asia/Jakarta (WIB)
            </Typography>
            <Typography variant="body2">
              Corpus telemetry age:{' '}
              {snapshot.telemetry.age_seconds === null ? (
                'Unknown'
              ) : (
                <Box component="span" sx={technicalTextSx}>
                  {snapshot.telemetry.age_seconds} seconds
                </Box>
              )}
            </Typography>
            <Typography variant="body2">
              Fresh sensors:{' '}
              <Box component="span" sx={technicalTextSx}>{snapshot.telemetry.fresh_sensor_count}</Box>
              ; stale sensors:{' '}
              <Box component="span" sx={technicalTextSx}>{snapshot.telemetry.stale_sensor_count}</Box>
              ; offline sensors:{' '}
              <Box component="span" sx={technicalTextSx}>{snapshot.telemetry.offline_sensor_count}</Box>
            </Typography>
            <Typography variant="caption" color="text.secondary">
              Waktu korpus historis tidak menetapkan readiness layanan saat ini.
            </Typography>
          </Stack>
        </Box>
      </Stack>
    </Paper>
  )
}
