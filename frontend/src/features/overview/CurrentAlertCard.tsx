import { Box, Card, CardActions, CardContent, Link, Stack, Typography } from '@mui/material'
import { Link as RouterLink } from 'react-router-dom'
import type { CurrentAlert } from '../../contracts/alerts'
import { sensorLabels } from '../../contracts/common'
import { tokens } from '../../theme/tokens'
import { ActionQueue } from './ActionQueue'
import { ProvenanceBadge } from '../../components/data/ProvenanceBadge'

export interface CurrentAlertCardProps {
  alert: CurrentAlert
}

const technicalTextSx = {
  fontFamily: tokens.font.data,
  fontVariantNumeric: 'tabular-nums',
  overflowWrap: 'anywhere',
} as const

const touchTargetLinkSx = {
  alignItems: 'center',
  display: { xs: 'inline-flex', sm: 'inline' },
  minHeight: { xs: tokens.size.control, sm: 'auto' },
} as const

export function CurrentAlertCard({ alert }: CurrentAlertCardProps) {
  const sensorLabel = sensorLabels[alert.device_id]
  const sensorPath = `/sensors/${alert.device_id}?sensor=${alert.device_id}`
  const alertPath = `/alerts?sensor=${alert.device_id}`

  return (
    <Card
      component="section"
      aria-label={`Current alert for ${sensorLabel}`}
      variant="outlined"
      sx={{
        borderLeftWidth: tokens.size.activeRule,
        borderLeftStyle: 'solid',
        borderLeftColor: 'error.main',
      }}
    >
      <CardContent>
        <Stack spacing={2}>
          <Stack spacing={0.5}>
            <Typography variant="h3">Sensor {sensorLabel}</Typography>
            <Typography component="p" color="error.main" variant="h4">
              Active anomaly
            </Typography>
          </Stack>
          <Stack direction="row" spacing={1} useFlexGap sx={{ alignItems: 'center', flexWrap: 'wrap' }}>
            <ProvenanceBadge provenance={alert.detection_basis} />
            <Typography variant="body2" color="text.secondary">
              Episode replay {alert.replay_job_id}
            </Typography>
          </Stack>
          <Stack direction="row" spacing={3} useFlexGap sx={{ flexWrap: 'wrap', minWidth: 0 }}>
            <Typography variant="body2">
              Peak score: <Box component="span" sx={technicalTextSx}>{alert.peak_score}</Box>
            </Typography>
            <Typography variant="body2">
              Threshold: <Box component="span" sx={technicalTextSx}>{alert.threshold}</Box>
            </Typography>
            <Typography variant="body2">
              Episode (WIB): <Box component="span" sx={technicalTextSx}>{alert.episode_start_ts}</Box>
              {' – '}
              <Box component="span" sx={technicalTextSx}>{alert.episode_end_ts}</Box>
            </Typography>
          </Stack>
        </Stack>
      </CardContent>
      <CardActions sx={{ alignItems: 'stretch', display: 'block', px: 2, pb: 2, pt: 0 }}>
        <Stack spacing={2}>
          <Stack direction="row" spacing={2} useFlexGap sx={{ flexWrap: 'wrap' }}>
            <Link component={RouterLink} to={sensorPath} sx={touchTargetLinkSx}>
              Inspect sensor history
            </Link>
            <Link component={RouterLink} to={alertPath} sx={touchTargetLinkSx}>
              Review active alert
            </Link>
          </Stack>
          <ActionQueue alert={alert} />
        </Stack>
      </CardActions>
    </Card>
  )
}
