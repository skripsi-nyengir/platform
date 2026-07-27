import { b02DeviceId, expect, gotoScenario, test } from './helpers'

test('activates USAD, replays, opens result, and verifies health/provenance', async ({ page }) => {
  await gotoScenario(page, '/model-evaluation', 'active-anomaly')
  const usad = page.getByRole('heading', { name: 'USAD' }).locator('..').locator('..')
  await usad.getByRole('button', { name: 'Pilih model' }).click()
  const dialog = page.getByRole('dialog', { name: 'Aktifkan USAD' })
  await expect(dialog).toContainText('berlaku untuk replay berikutnya')
  await dialog.getByRole('button', { name: 'Aktifkan untuk replay berikutnya' }).click()
  await expect(usad.getByText('Dipilih')).toBeVisible()

  const replay = page.getByRole('heading', { name: 'Preview replay' }).locator('..').locator('..')
  await replay.getByRole('button', { name: 'Jalankan replay' }).click()
  const status = replay.getByRole('status', { name: 'Replay progress' })
  await expect(status).toContainText('preview-usad-v1')
  await expect(status.getByText('Simulasi preview')).toBeVisible()
  await status.getByRole('link', { name: 'Lihat hasil replay' }).click()
  await expect(page).toHaveURL(new RegExp(`/sensors/${b02DeviceId}.*model_version=preview-usad-v1`))
  await expect(page.getByText('Simulasi preview').first()).toBeVisible()

  await page.getByRole('link', { name: 'System Health' }).click()
  await expect(page.getByText('Preview worker')).toBeVisible()
  await expect(page.getByRole('rowheader', { name: 'Artifact asli' })).toBeVisible()
})
