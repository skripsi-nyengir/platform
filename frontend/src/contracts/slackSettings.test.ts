import { describe, expect, it } from 'vitest'
import {
  SlackSettingsResponseSchema,
  TestSlackSettingsRequestSchema,
  UpdateSlackSettingsRequestSchema,
} from './slackSettings'

describe('Slack settings contracts', () => {
  it('accepts a redacted settings response and rejects a leaked token', () => {
    const response = {
      request_id: 'req_slack_settings',
      enabled: false,
      channel_id: 'C0123456789',
      bot_token_configured: true,
      updated_at: '2026-08-08T01:02:03Z',
      updated_by_username: 'operator',
    }

    expect(SlackSettingsResponseSchema.parse(response)).toEqual(response)
    expect(() => SlackSettingsResponseSchema.parse({ ...response, bot_token: 'xoxb-secret' }))
      .toThrow()
  })

  it('distinguishes preserving, replacing, and clearing a token', () => {
    expect(UpdateSlackSettingsRequestSchema.parse({ enabled: false, channel_id: null }))
      .not.toHaveProperty('bot_token')
    expect(UpdateSlackSettingsRequestSchema.parse({
      enabled: true,
      channel_id: 'C0123456789',
      bot_token: 'xoxb-replacement',
    }).bot_token).toBe('xoxb-replacement')
    expect(UpdateSlackSettingsRequestSchema.parse({
      enabled: false,
      channel_id: null,
      bot_token: null,
    }).bot_token).toBeNull()
  })

  it('requires a channel but permits a stored token for tests', () => {
    expect(TestSlackSettingsRequestSchema.parse({ channel_id: 'C0123456789' }))
      .not.toHaveProperty('bot_token')
    expect(() => TestSlackSettingsRequestSchema.parse({ channel_id: '' })).toThrow()
  })
})
