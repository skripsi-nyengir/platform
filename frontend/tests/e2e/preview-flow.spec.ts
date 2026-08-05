import { expect, expectVisibleFocus, gotoScenario, tabTo, test } from './helpers'

test('compares five trained models and exposes exact offline data by keyboard', async ({ page }) => {
  await gotoScenario(page, '/model-evaluation', 'active-anomaly')

  const registry = page.getByRole('region', {
    name: 'Model terdaftar (metrik dilaporkan dari training)',
  })
  const offline = page.getByRole('region', {
    name: 'Evaluasi Step 7 (validation-injected berlabel)',
  })

  await expect(registry.getByRole('article')).toHaveCount(5)
  await expect(
    offline.getByRole('img', {
      name: 'Perbandingan precision recall dan F1 lima model pada bin evaluasi',
    }),
  ).toBeVisible()

  for (const name of [
    'Conv1D Autoencoder',
    'GRU Autoencoder',
    'LSTM Autoencoder',
    'RNN Autoencoder',
    'Transformer Autoencoder',
  ]) {
    await expect(registry.getByRole('heading', { name })).toBeVisible()
  }

  const conv1d = offline.getByRole('button', { name: 'Conv1D', exact: true })
  const gru = offline.getByRole('button', { name: 'GRU', exact: true })
  await expect(conv1d).toBeVisible()
  await expect(conv1d).toHaveAttribute('aria-pressed', 'true')
  await expect(gru).toHaveAttribute('aria-pressed', 'false')
  await tabTo(page, gru)
  await expectVisibleFocus(gru)
  await page.keyboard.press('Space')
  await expect(gru).toHaveAttribute('aria-pressed', 'true')
  await expect(conv1d).toHaveAttribute('aria-pressed', 'false')
  await expect(
    offline.getByRole('heading', { name: 'Tiga scope evaluasi · GRU' }),
  ).toBeVisible()
  await expect(offline.getByRole('table', { name: 'Metrik tiga scope GRU' })).toBeVisible()

  const exactDataTrigger = offline.getByRole('button', { name: 'Lihat data eksak' })
  await exactDataTrigger.click()
  const dialog = page.getByRole('dialog', { name: 'Data eksak evaluasi Step 7' })
  const table = dialog.getByRole('table', {
    name: 'Data eksak precision recall F1 dan confusion matrix',
  })
  await expect(table.getByRole('row')).toHaveCount(6)
  await expect(table.getByText('0.7319884726224783')).toBeVisible()
  await dialog.getByRole('button', { name: 'Tutup' }).click()
  await expect(exactDataTrigger).toBeFocused()
  await expect(page.getByText(/winner|pemenang|peringkat|model terbaik/i)).toHaveCount(0)
})
