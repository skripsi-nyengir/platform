import { expect, gotoScenario, test } from './helpers'

test('operator can test unsaved Slack values and then save redacted settings', async ({ page }) => {
  await gotoScenario(page, '/settings/slack', 'normal')

  const channel = page.getByLabel('Channel ID')
  const token = page.getByLabel('Bot token')
  await expect(token).toHaveAttribute('type', 'password')
  await expect(token).toHaveValue('')
  await channel.fill('CUNSAVED')
  await token.fill('xoxb-e2e-unsaved')
  await page.getByRole('button', { name: 'Send test notification' }).click()
  await expect(page.getByText(/Test notification sent/)).toBeVisible()
  await expect(page.getByLabel('Enable Slack notifications')).not.toBeChecked()

  await page.getByRole('button', { name: 'Save' }).click()
  await expect(page.getByText('Slack settings saved.')).toBeVisible()
  await expect(token).toHaveValue('')
  await expect(page.getByText('Stored token configured')).toBeVisible()
  await expect(page.locator('body')).not.toContainText('xoxb-e2e-unsaved')
})
