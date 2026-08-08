import {
  Alert,
  Button,
  Chip,
  Divider,
  FormControlLabel,
  Paper,
  Skeleton,
  Stack,
  Switch,
  TextField,
  Typography,
} from '@mui/material'
import { useState } from 'react'
import { ApiError } from '../api/errors'
import { ApiErrorPanel } from '../components/states/ApiErrorPanel'
import type { SlackSettingsResponse } from '../contracts/slackSettings'
import {
  useSlackSettingsQuery,
  useTestSlackSettings,
  useUpdateSlackSettings,
} from '../features/slackSettings/queries'

type TokenOperation = 'preserve' | 'replace' | 'clear'

function actionErrorMessage(action: 'save' | 'test', error: unknown): string {
  const requestId = error instanceof ApiError ? error.requestId : undefined
  const suffix = requestId === undefined ? '' : ` Request ID: ${requestId}`
  if (error instanceof ApiError && error.kind === 'timeout') {
    return `Slack did not respond in time. Try again.${suffix}`
  }
  if (error instanceof ApiError && error.status === 429) {
    return `Slack is rate limiting requests. Try again shortly.${suffix}`
  }
  return action === 'save'
    ? `Slack settings could not be saved.${suffix}`
    : `Slack could not send the test notification. Check the token, scopes, channel, and bot membership.${suffix}`
}

function LoadingSettings() {
  return (
    <Paper variant="outlined" sx={{ p: { xs: 3, sm: 4 } }} aria-label="Loading Slack settings">
      <Stack spacing={3}>
        <Skeleton variant="text" width="35%" height={32} />
        <Skeleton variant="rounded" height={56} />
        <Skeleton variant="rounded" height={56} />
        <Skeleton variant="rounded" height={44} width={240} />
      </Stack>
    </Paper>
  )
}

export function SlackSettingsPage() {
  const settings = useSlackSettingsQuery()

  if (settings.data === undefined) {
    return (
      <Stack spacing={6}>
        <Stack spacing={0.5}>
          <Typography variant="h1">Slack</Typography>
          <Typography color="text.secondary" variant="body2">
            Configure operational alert notifications.
          </Typography>
        </Stack>
        {settings.isError ? (
          <ApiErrorPanel error={settings.error} onRetry={() => void settings.refetch()} />
        ) : (
          <LoadingSettings />
        )}
      </Stack>
    )
  }

  return <SlackSettingsForm settings={settings.data} />
}

function SlackSettingsForm({ settings }: { settings: SlackSettingsResponse }) {
  const save = useUpdateSlackSettings()
  const test = useTestSlackSettings()
  const [enabled, setEnabled] = useState(settings.enabled)
  const [channelId, setChannelId] = useState(settings.channel_id ?? '')
  const [botToken, setBotToken] = useState('')
  const [tokenOperation, setTokenOperation] = useState<TokenOperation>('preserve')

  const trimmedChannel = channelId.trim()
  const trimmedToken = botToken.trim()
  const replacingToken = tokenOperation === 'replace' && trimmedToken.length > 0
  const effectiveTokenConfigured = replacingToken || (
    settings.bot_token_configured && tokenOperation !== 'clear'
  )
  const saveDisabled = save.isPending || test.isPending || (
    enabled && (trimmedChannel.length === 0 || !effectiveTokenConfigured)
  )
  const testDisabled = save.isPending || test.isPending || trimmedChannel.length === 0
    || !effectiveTokenConfigured

  return (
    <Stack spacing={6}>
      <Stack spacing={0.5}>
        <Typography variant="h1">Slack</Typography>
        <Typography color="text.secondary" variant="body2" sx={{ maxWidth: '68ch' }}>
          Configure the Slack bot destination for alert charts and verify it with a test notification.
        </Typography>
      </Stack>

      <Paper variant="outlined" sx={{ p: { xs: 3, sm: 4 }, maxWidth: 760 }}>
        <Stack
          component="form"
          spacing={4}
          noValidate
          onSubmit={(event) => {
            event.preventDefault()
            const body = {
              enabled,
              channel_id: trimmedChannel || null,
              ...(replacingToken
                ? { bot_token: trimmedToken }
                : tokenOperation === 'clear'
                  ? { bot_token: null }
                  : {}),
            }
            save.mutate(body, {
              onSuccess: (savedSettings) => {
                setEnabled(savedSettings.enabled)
                setChannelId(savedSettings.channel_id ?? '')
                // A submitted replacement is discarded immediately; only the
                // redacted configured flag remains in the query cache.
                setBotToken('')
                setTokenOperation('preserve')
              },
            })
          }}
        >
          <Stack spacing={1}>
            <FormControlLabel
              control={(
                <Switch
                  checked={enabled}
                  onChange={(event) => setEnabled(event.target.checked)}
                  slotProps={{ input: { 'aria-label': 'Enable Slack notifications' } }}
                />
              )}
              label="Enable Slack notifications"
            />
            <Typography color="text.secondary" variant="body2">
              Changes take effect for the notifier after you save.
            </Typography>
          </Stack>

          <TextField
            label="Channel ID"
            name="channel_id"
            placeholder="C0123456789"
            value={channelId}
            onChange={(event) => setChannelId(event.target.value)}
            required={enabled}
            error={enabled && trimmedChannel.length === 0}
            helperText="Use the Slack channel ID, not the channel name."
            slotProps={{ htmlInput: { maxLength: 255 } }}
          />

          <Stack spacing={2}>
            <TextField
              label="Bot token"
              name="bot_token"
              type="password"
              autoComplete="new-password"
              placeholder={settings.bot_token_configured ? 'Enter a new token to replace the stored token' : 'xoxb-…'}
              value={botToken}
              onChange={(event) => {
                const value = event.target.value
                setBotToken(value)
                setTokenOperation(value.trim() ? 'replace' : 'preserve')
              }}
              helperText="The stored token is never returned or displayed. Leaving this blank preserves it."
              slotProps={{ htmlInput: { maxLength: 4096 } }}
            />
            <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2} sx={{ alignItems: { sm: 'center' } }}>
              <Chip
                size="small"
                color={effectiveTokenConfigured ? 'success' : 'default'}
                label={tokenOperation === 'clear'
                  ? 'Token will be cleared'
                  : settings.bot_token_configured
                    ? 'Stored token configured'
                    : replacingToken
                      ? 'New token ready to save'
                      : 'No stored token'}
              />
              {settings.bot_token_configured && tokenOperation !== 'clear' ? (
                <Button
                  type="button"
                  color="error"
                  onClick={() => {
                    setEnabled(false)
                    setBotToken('')
                    setTokenOperation('clear')
                  }}
                >
                  Clear stored token
                </Button>
              ) : tokenOperation === 'clear' ? (
                <Button type="button" onClick={() => setTokenOperation('preserve')}>
                  Keep stored token
                </Button>
              ) : null}
            </Stack>
          </Stack>

          <Divider />

          {save.isError ? <Alert severity="error">{actionErrorMessage('save', save.error)}</Alert> : null}
          {save.isSuccess ? <Alert severity="success">Slack settings saved.</Alert> : null}
          {test.isError ? <Alert severity="error">{actionErrorMessage('test', test.error)}</Alert> : null}
          {test.isSuccess ? (
            <Alert severity="success">Test notification sent at {test.data.sent_at}.</Alert>
          ) : null}

          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
            <Button type="submit" variant="contained" disabled={saveDisabled}>
              {save.isPending ? 'Saving…' : 'Save'}
            </Button>
            <Button
              type="button"
              variant="outlined"
              disabled={testDisabled}
              onClick={() => test.mutate({
                channel_id: trimmedChannel,
                ...(replacingToken ? { bot_token: trimmedToken } : {}),
              })}
            >
              {test.isPending ? 'Sending test…' : 'Send test notification'}
            </Button>
          </Stack>

          <Typography color="text.secondary" variant="caption">
            Last updated {settings.updated_at}
            {settings.updated_by_username === null ? '' : ` by ${settings.updated_by_username}`}.
          </Typography>
        </Stack>
      </Paper>
    </Stack>
  )
}
