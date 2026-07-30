import { expect, gotoScenario, test } from './helpers'

test('shows five trained models in the two model-evaluation sections', async ({ page }) => {
  await gotoScenario(page, '/model-evaluation', 'active-anomaly')

  const registry = page.getByRole('region', {
    name: 'Model terdaftar (metrik dilaporkan dari training)',
  })
  const offline = page.getByRole('region', {
    name: 'Evaluasi offline (test-set injected berlabel)',
  })

  await expect(registry.getByRole('article')).toHaveCount(5)
  await expect(offline.getByRole('article')).toHaveCount(5)
  await expect(page.getByRole('region')).toHaveCount(2)

  for (const name of [
    'Conv1D Autoencoder',
    'GRU Autoencoder',
    'LSTM Autoencoder',
    'RNN Autoencoder',
    'Transformer Autoencoder',
  ]) {
    await expect(registry.getByRole('heading', { name })).toBeVisible()
  }

})
