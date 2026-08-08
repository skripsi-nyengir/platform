import { http, HttpResponse } from 'msw'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { mockState } from '../mocks/state'
import { server } from '../mocks/node'
import { renderApp } from '../test/renderApp'

describe('SlackSettingsPage', () => {
  it('loads redacted settings without ever populating the token field', async () => {
    renderApp('/settings/slack')

    expect(screen.getByLabelText('Loading Slack settings')).toBeVisible()
    const token = await screen.findByLabelText('Bot token')
    expect(token).toHaveAttribute('type', 'password')
    expect(token).toHaveValue('')
    expect(screen.getByText('Stored token configured')).toBeVisible()
    expect(document.body).not.toHaveTextContent('xoxb-')
  })

  it('tests current unsaved channel and replacement token without saving or enabling', async () => {
    const user = userEvent.setup()
    renderApp('/settings/slack')

    await user.clear(await screen.findByLabelText('Channel ID'))
    await user.type(screen.getByLabelText('Channel ID'), 'CUNSAVED')
    await user.type(screen.getByLabelText('Bot token'), 'xoxb-unsaved')
    await user.click(screen.getByRole('button', { name: 'Send test notification' }))

    expect(await screen.findByText(/Test notification sent/)).toBeVisible()
    expect(mockState.slackTestRequests).toEqual([{
      channel_id: 'CUNSAVED',
      bot_token: 'xoxb-unsaved',
    }])
    expect(mockState.slackSettings).toMatchObject({
      enabled: false,
      channel_id: 'C0123456789',
    })
  })

  it('omits a blank token to test with the configured stored token', async () => {
    const user = userEvent.setup()
    renderApp('/settings/slack')

    await user.click(await screen.findByRole('button', { name: 'Send test notification' }))

    await waitFor(() => expect(mockState.slackTestRequests).toEqual([
      { channel_id: 'C0123456789' },
    ]))
  })

  it('does not test with a stored token that the unsaved form marks for clearing', async () => {
    const user = userEvent.setup()
    renderApp('/settings/slack')

    await user.click(await screen.findByRole('button', { name: 'Clear stored token' }))

    expect(screen.getByRole('button', { name: 'Send test notification' })).toBeDisabled()
    expect(mockState.slackTestRequests).toEqual([])

    await user.click(screen.getByRole('button', { name: 'Keep stored token' }))
    expect(screen.getByRole('button', { name: 'Send test notification' })).toBeEnabled()
  })

  it('preserves a stored token on save and clears it only through the explicit action', async () => {
    const user = userEvent.setup()
    renderApp('/settings/slack')

    await user.clear(await screen.findByLabelText('Channel ID'))
    await user.type(screen.getByLabelText('Channel ID'), 'CPRESERVED')
    await user.click(screen.getByRole('button', { name: 'Save' }))
    expect(await screen.findByText('Slack settings saved.')).toBeVisible()
    expect(mockState.slackSettings).toMatchObject({
      channel_id: 'CPRESERVED',
      bot_token_configured: true,
    })

    await user.click(screen.getByRole('button', { name: 'Clear stored token' }))
    expect(screen.getByRole('switch', { name: 'Enable Slack notifications' })).not.toBeChecked()
    expect(screen.getByText('Token will be cleared')).toBeVisible()
    await user.click(screen.getByRole('button', { name: 'Save' }))

    await waitFor(() => expect(mockState.slackSettings.bot_token_configured).toBe(false))
  })

  it('shows a safe test failure without echoing the submitted token', async () => {
    server.use(http.post('/api/settings/slack/test', () => HttpResponse.json({
      type: 'https://example.invalid/problems/slack-scope',
      title: 'Slack request failed',
      status: 403,
      detail: 'The Slack bot could not post to this channel',
      instance: '/api/settings/slack/test',
      request_id: 'req_slack_scope',
    }, { status: 403 })))
    const user = userEvent.setup()
    renderApp('/settings/slack')

    await user.type(await screen.findByLabelText('Bot token'), 'xoxb-do-not-render')
    await user.click(screen.getByRole('button', { name: 'Send test notification' }))

    expect(await screen.findByText(/Slack could not send the test notification/)).toBeVisible()
    expect(screen.getByText(/req_slack_scope/)).toBeVisible()
    expect(document.body).not.toHaveTextContent('xoxb-do-not-render')
  })
})
