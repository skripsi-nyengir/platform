import type { SlackSettingsResponse } from '../../contracts/slackSettings'

export const slackSettingsResponse = Object.freeze({
  request_id: 'req_slack_settings',
  enabled: false,
  channel_id: 'C0123456789',
  bot_token_configured: true,
  updated_at: '2026-08-08T01:02:03Z',
  updated_by_username: 'operator',
} satisfies SlackSettingsResponse)
