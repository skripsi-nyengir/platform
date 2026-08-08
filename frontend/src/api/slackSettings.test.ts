import { afterEach, describe, expect, it, vi } from 'vitest'
import { getSlackSettings, testSlackSettings, updateSlackSettings } from './slackSettings'

const response = {
  request_id: 'req_slack_settings',
  enabled: false,
  channel_id: 'C0123456789',
  bot_token_configured: true,
  updated_at: '2026-08-08T01:02:03Z',
  updated_by_username: 'operator',
}

afterEach(() => vi.unstubAllGlobals())

describe('Slack settings API', () => {
  it('loads only the redacted response contract', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(new Response(JSON.stringify(response)))))
    await expect(getSlackSettings()).resolves.toEqual(response)
  })

  it.each([
    ['preserve', { enabled: true, channel_id: 'CNEW' }],
    ['replace', { enabled: true, channel_id: 'CNEW', bot_token: 'xoxb-new' }],
    ['clear', { enabled: false, channel_id: null, bot_token: null }],
  ] as const)('serializes token operation: %s', async (_name, body) => {
    const fetchMock = vi.fn(() => Promise.resolve(new Response(JSON.stringify(response))))
    vi.stubGlobal('fetch', fetchMock)

    await updateSlackSettings(body)

    expect(fetchMock).toHaveBeenCalledWith('/api/settings/slack', expect.objectContaining({
      method: 'PUT',
      body: JSON.stringify(body),
    }))
  })

  it('omits a blank stored token override from a test request', async () => {
    const fetchMock = vi.fn(() => Promise.resolve(new Response(JSON.stringify({
      request_id: 'req_slack_test',
      status: 'sent',
      sent_at: '2026-08-08T01:03:00Z',
    }))))
    vi.stubGlobal('fetch', fetchMock)

    await testSlackSettings({ channel_id: 'CUNSAVED' })

    expect(fetchMock).toHaveBeenCalledWith('/api/settings/slack/test', expect.objectContaining({
      method: 'POST',
      body: JSON.stringify({ channel_id: 'CUNSAVED' }),
    }))
  })
})
