import {
  Box,
  Button,
  Chip,
  Collapse,
  Link,
  List,
  ListItem,
  Paper,
  Stack,
  Typography,
} from '@mui/material'
import { useState } from 'react'
import { Link as RouterLink } from 'react-router-dom'
import { ProvenanceBadge } from '../../components/data/ProvenanceBadge'
import type { CurrentAlert } from '../../contracts/alerts'
import { sensorLabels } from '../../contracts/common'
import { formatWibDateTime } from '../../lib/dateTime'
import { tokens } from '../../theme/tokens'
import { AlertEpisodeContext } from '../alerts-ui/AlertEpisodeContext'
import { ActionQueue } from '../overview/ActionQueue'

export interface ActiveAlertsSectionProps {
  alerts: readonly CurrentAlert[]
}

const initialVisibleAlerts = 3

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

const statusLabels = {
  detected: 'Active anomaly',
  acknowledged: 'Acknowledged alert',
  resolved: 'Resolved alert',
} as const

function ActiveAlertRow({ alert }: { alert: CurrentAlert }) {
  const [expanded, setExpanded] = useState(false)
  const sensorLabel = sensorLabels[alert.device_id]
  const sensorPath = `/sensors/${alert.device_id}?sensor=${alert.device_id}`
  const alertPath = `/alerts?sensor=${alert.device_id}`
  const detailsId = `alert-details-${alert.alert_id}`

  return (
    <ListItem
      disablePadding
      sx={{
        display: 'block',
        '&:not(:first-of-type)': {
          borderTopColor: 'divider',
          borderTopStyle: 'solid',
          borderTopWidth: tokens.size.rule,
        },
      }}
    >
      <Box
        component="article"
        aria-label={`Current alert for ${sensorLabel}`}
        sx={{
          borderLeftColor: 'error.main',
          borderLeftStyle: 'solid',
          borderLeftWidth: tokens.size.activeRule,
          minWidth: 0,
          px: 2,
          py: 2,
        }}
      >
        <Stack spacing={1.5}>
          <Stack
            direction="row"
            spacing={1}
            useFlexGap
            sx={{ alignItems: 'center', flexWrap: 'wrap', minWidth: 0 }}
          >
            <Typography variant="h3">Sensor {sensorLabel}</Typography>
            <Chip label={statusLabels[alert.status]} color="error" size="small" />
            <ProvenanceBadge provenance={alert.detection_basis} />
          </Stack>

          <Box
            component="dl"
            sx={{
              columnGap: 3,
              display: 'grid',
              gridTemplateColumns: {
                xs: 'minmax(0, 1fr)',
                sm: 'repeat(2, minmax(0, 1fr))',
                lg: 'auto auto minmax(0, 1fr)',
              },
              m: 0,
              minWidth: 0,
              rowGap: 1,
            }}
          >
            <Box>
              <Typography component="dt" variant="caption" color="text.secondary">Peak score</Typography>
              <Typography component="dd" variant="body2" sx={{ ...technicalTextSx, m: 0 }}>
                {alert.peak_score}
              </Typography>
            </Box>
            <Box>
              <Typography component="dt" variant="caption" color="text.secondary">Threshold</Typography>
              <Typography component="dd" variant="body2" sx={{ ...technicalTextSx, m: 0 }}>
                {alert.threshold}
              </Typography>
            </Box>
            <Box>
              <Typography component="dt" variant="caption" color="text.secondary">Episode (WIB)</Typography>
              <Typography
                component="dd"
                variant="body2"
                sx={{ ...technicalTextSx, m: 0, overflowWrap: 'normal' }}
              >
                <Box
                  component="span"
                  sx={{
                    columnGap: 2,
                    display: 'flex',
                    flexDirection: { xs: 'column', sm: 'row' },
                    flexWrap: 'wrap',
                  }}
                >
                  <Box component="span" sx={{ whiteSpace: 'nowrap' }}>
                    Start {formatWibDateTime(alert.episode_start_ts)}
                  </Box>
                  <Box component="span" sx={{ whiteSpace: 'nowrap' }}>
                    End {formatWibDateTime(alert.episode_end_ts)}
                  </Box>
                </Box>
              </Typography>
            </Box>
          </Box>

          <Stack
            direction={{ xs: 'column', sm: 'row' }}
            spacing={1}
            useFlexGap
            sx={{ alignItems: 'flex-start' }}
          >
            <ActionQueue alert={alert} />
            <Button
              aria-controls={detailsId}
              aria-expanded={expanded}
              aria-label={`${expanded ? 'Hide' : 'Show'} episode context for ${sensorLabel}`}
              onClick={() => setExpanded((value) => !value)}
              variant="outlined"
            >
              {expanded ? 'Hide episode context' : 'Show episode context'}
            </Button>
          </Stack>

          <Collapse in={expanded} unmountOnExit>
            <Stack id={detailsId} spacing={1.5}>
              <AlertEpisodeContext alertId={alert.alert_id} compact />
              <Typography variant="body2" color="text.secondary">
                Episode replay:{' '}
                <Box component="span" sx={technicalTextSx}>
                  {alert.replay_job_id ?? 'Unavailable'}
                </Box>
              </Typography>
              <Stack direction="row" spacing={2} useFlexGap sx={{ flexWrap: 'wrap' }}>
                <Link component={RouterLink} to={sensorPath} sx={touchTargetLinkSx}>
                  Inspect sensor history
                </Link>
                <Link component={RouterLink} to={alertPath} sx={touchTargetLinkSx}>
                  Review active alert
                </Link>
              </Stack>
            </Stack>
          </Collapse>
        </Stack>
      </Box>
    </ListItem>
  )
}

export function ActiveAlertsSection({ alerts }: ActiveAlertsSectionProps) {
  const [showAll, setShowAll] = useState(false)
  const hiddenAlertCount = Math.max(0, alerts.length - initialVisibleAlerts)
  const visibleAlerts = showAll ? alerts : alerts.slice(0, initialVisibleAlerts)

  return (
    <Paper component="section" aria-labelledby="active-alerts-heading" variant="outlined" sx={{ overflow: 'hidden' }}>
      <Box
        sx={{
          borderBottomColor: 'divider',
          borderBottomStyle: 'solid',
          borderBottomWidth: tokens.size.rule,
          p: 2,
        }}
      >
        <Typography id="active-alerts-heading" variant="h2">
          Active alerts ({alerts.length})
        </Typography>
      </Box>
      <List id="active-alert-list" aria-label="Active alerts" disablePadding>
        {visibleAlerts.map((alert) => <ActiveAlertRow key={alert.alert_id} alert={alert} />)}
      </List>
      {hiddenAlertCount > 0 ? (
        <Box
          sx={{
            borderTopColor: 'divider',
            borderTopStyle: 'solid',
            borderTopWidth: tokens.size.rule,
            p: 2,
          }}
        >
          <Button
            aria-controls="active-alert-list"
            aria-expanded={showAll}
            onClick={() => setShowAll((value) => !value)}
            variant="outlined"
          >
            {showAll ? 'Show fewer alerts' : `Show ${hiddenAlertCount} more`}
          </Button>
        </Box>
      ) : null}
    </Paper>
  )
}
