import { expect, gotoScenario, test } from './helpers'

const from = '2026-07-19T10:00:00Z'
const to = '2026-07-19T10:30:00Z'

test('examiner changes bounded EDA filters and sample controls', async ({ page }) => {
  await gotoScenario(
    page,
    `/eda?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}&bucket=5m`,
    'data-gap',
  )

  await page.getByRole('combobox', { name: 'Sensor' }).selectOption('n5')
  await page.getByRole('spinbutton', { name: 'Sample size' }).fill('5000')
  await page.getByRole('combobox', { name: 'X field' }).selectOption('relative_humidity_pct')

  await expect(page.getByRole('combobox', { name: 'Sensor' })).toHaveValue('n5')
  await expect(page.getByRole('spinbutton', { name: 'Sample size' })).toHaveValue('5000')
  await expect(page.getByRole('combobox', { name: 'X field' })).toHaveValue('relative_humidity_pct')
  await expect(page.getByRole('combobox', { name: 'Y field' })).toHaveValue('temperature_c')
  await expect(page.getByText('1 absent sample')).toBeVisible()
  await expect(page.getByText('1 cadence gap')).toBeVisible()
  await expect(page.getByText('5 telemetry points returned')).toBeVisible()
  await expect(page.getByText('4 inference points returned')).toBeVisible()
  await expect(page.getByRole('img', {
    name: /relative_humidity_pct by temperature_c scatter/i,
  })).toBeVisible()

  const url = new URL(page.url())
  expect(url.searchParams.get('sensor')).toBe('n5')
  expect(url.searchParams.get('from')).toBe(from)
  expect(url.searchParams.get('to')).toBe(to)
  expect(url.searchParams.get('bucket')).toBe('5m')
  expect(url.searchParams.has('sampleSize')).toBe(false)
})

test('examiner switches model versions and sees only declared panel types', async ({ page }) => {
  await gotoScenario(page, '/model-evaluation?model_version=model-v2', 'active-anomaly')

  const version = page.getByRole('combobox', { name: 'Model version' })
  const metrics = page.getByRole('region', { name: 'Artifact metrics' })
  await expect(version).toHaveValue('model-v2')
  await expect(metrics).toContainText('accuracy: 0.96')
  await expect(metrics).toContainText('f1: 0.91')
  await expect(metrics).not.toContainText('confusion_matrix:')
  await expect(page.getByRole('table', { name: 'Confusion matrix' })).toBeVisible()
  await expect(page.getByRole('img', { name: 'ROC curve' })).toBeVisible()
  await expect(page.getByRole('img', { name: /Precision-recall curve/i })).toBeVisible()

  const confusionMatrixData = page.getByRole('button', { name: 'Lihat data Confusion matrix' })
  const rocCurveData = page.getByRole('button', { name: 'Lihat data ROC curve' })
  const precisionRecallCurveData = page.getByRole('button', {
    name: 'Lihat data Precision recall curve',
  })
  await expect(confusionMatrixData).toHaveCount(1)
  await expect(rocCurveData).toHaveCount(1)
  await expect(precisionRecallCurveData).toHaveCount(1)

  await confusionMatrixData.click()
  const confusionMatrixDialog = page.getByRole('dialog', { name: 'Confusion matrix data' })
  await expect(confusionMatrixDialog).toBeVisible()
  await expect(confusionMatrixDialog.getByRole('heading', { name: 'Confusion matrix data' })).toBeVisible()
  const confusionMatrixGrid = confusionMatrixDialog.getByRole('grid')
  await expect(confusionMatrixGrid.getByRole('row')).toHaveCount(5)
  await expect(confusionMatrixGrid.getByRole('columnheader', { name: 'Actual' })).toBeVisible()
  await expect(confusionMatrixGrid.getByRole('columnheader', { name: 'Predicted' })).toBeVisible()
  await expect(confusionMatrixGrid.getByRole('columnheader', { name: 'Count' })).toBeVisible()
  await expect(confusionMatrixGrid.getByRole('gridcell', { name: '92' })).toBeVisible()
  await confusionMatrixDialog.getByRole('button', { name: 'Close' }).click()
  await expect(confusionMatrixDialog).toBeHidden()

  await rocCurveData.click()
  const rocCurveDialog = page.getByRole('dialog', { name: 'ROC curve data; AUC 0.97' })
  await expect(rocCurveDialog).toBeVisible()
  await expect(rocCurveDialog.getByRole('heading', { name: 'ROC curve data; AUC 0.97' })).toBeVisible()
  const rocCurveGrid = rocCurveDialog.getByRole('grid')
  await expect(rocCurveGrid.getByRole('row')).toHaveCount(4)
  await expect(rocCurveGrid.getByRole('columnheader', { name: 'False positive rate' })).toBeVisible()
  await expect(rocCurveGrid.getByRole('columnheader', { name: 'True positive rate' })).toBeVisible()
  await expect(rocCurveGrid.getByRole('gridcell', { name: '0.08' })).toBeVisible()
  await expect(rocCurveGrid.getByRole('gridcell', { name: '0.9' })).toBeVisible()
  await rocCurveDialog.getByRole('button', { name: 'Close' }).click()
  await expect(rocCurveDialog).toBeHidden()

  await precisionRecallCurveData.click()
  const precisionRecallCurveDialog = page.getByRole('dialog', {
    name: 'Precision recall curve data; average precision 0.93',
  })
  await expect(precisionRecallCurveDialog).toBeVisible()
  await expect(
    precisionRecallCurveDialog.getByRole('heading', {
      name: 'Precision recall curve data; average precision 0.93',
    }),
  ).toBeVisible()
  const precisionRecallCurveGrid = precisionRecallCurveDialog.getByRole('grid')
  await expect(precisionRecallCurveGrid.getByRole('row')).toHaveCount(4)
  await expect(precisionRecallCurveGrid.getByRole('columnheader', { name: 'Recall' })).toBeVisible()
  await expect(precisionRecallCurveGrid.getByRole('columnheader', { name: 'Precision' })).toBeVisible()
  await expect(precisionRecallCurveGrid.getByRole('gridcell', { name: '0.9' })).toBeVisible()
  await expect(precisionRecallCurveGrid.getByRole('gridcell', { name: '0.88' })).toBeVisible()
  await precisionRecallCurveDialog.getByRole('button', { name: 'Close' }).click()
  await expect(precisionRecallCurveDialog).toBeHidden()

  await version.selectOption('model-v1')
  await expect(version).toHaveValue('model-v1')
  await expect(page.getByText('Model hash: sha256:model-v1')).toBeVisible()
  await expect(metrics).toContainText('accuracy: 0.94')
  await expect(metrics).toContainText('f1: 0.88')
  expect(new URL(page.url()).searchParams.get('model_version')).toBe('model-v1')
})
