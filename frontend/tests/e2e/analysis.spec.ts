import type { Page } from '@playwright/test'
import {
  disableAppQueryRetries,
  expect,
  gotoScenario,
  refetchAppQuery,
  resetAppQuery,
  setMockScenarioOnPage,
  test,
} from './helpers'

const canonicalRunId = 'run-b02-canonical-v3'
const cachedRunId = 'run-b02-custom-cache'
const publishedRunId = 'run-b02-custom-published'
const customFrom = '2026-02-10T00:00:00'
const customTo = '2026-02-11T00:00:00'
const cachedFrom = '2026-02-01T00:00:00'
const cachedTo = '2026-02-02T00:00:00'

const sectionHeadings = [
  'Kualitas Data',
  'Pola Temporal',
  'Hubungan Suhu-RH',
  'Struktur Temporal dan Perubahan Rezim',
  'Metadata Audit dan Akses Data',
] as const

const panelHeadings = [
  'Audit pairing timestamp',
  'Kepadatan gabungan Suhu–RH',
  'Diagnostik univariat',
  'Excerpt kejadian kualitas',
  'Integritas kualitas',
  'Cakupan kalender temporal',
  'Cakupan hari × jam',
  'Distribusi temporal Suhu dan RH',
  'Ringkasan asosiasi Suhu–RH',
  'Korelasi Pearson bergulir',
  'Ketidakpastian bootstrap asosiasi',
  'Kelayakan struktur temporal',
  'Autokorelasi ACF dan PACF',
  'Spektrum frekuensi',
  'Dekomposisi STL',
  'Kandidat perubahan rezim',
] as const

function trackEdaRequests(page: Page): string[] {
  const requests: string[] = []
  page.on('request', (request) => {
    const url = new URL(request.url())
    if (url.pathname.startsWith('/api/eda/')) {
      requests.push(`${request.method()} ${url.pathname}${url.search}`)
    }
  })
  return requests
}

function countRequests(requests: readonly string[], prefix: string): number {
  return requests.filter((request) => request.startsWith(prefix)).length
}

async function gotoCustomScenario(
  page: Page,
  scenario: Parameters<typeof gotoScenario>[2],
  from = customFrom,
  to = customTo,
): Promise<void> {
  await gotoScenario(
    page,
    `/eda?mode=custom&period_kind=monthly&from=${from}&to=${to}&run=run-b02-monthly-2026-02`,
    scenario,
  )
  await expect(page.getByRole('button', { name: 'Hitung EDA' })).toBeEnabled()
}

function panel(page: Page, heading: string) {
  return page.getByRole('heading', { name: heading }).locator('xpath=ancestor::section[1]')
}

test('latest precompute falls back monthly → weekly and keeps every first-class panel visible', async ({ page }) => {
  await gotoScenario(page, '/eda', 'eda-latest-fallback')

  await expect(page).toHaveURL(/period_kind=weekly/)
  await expect(page).toHaveURL(/run=run-b02-weekly-latest/)
  await expect(page.getByText('Komputasi rentang setara-algoritme')).toBeVisible()
  for (const heading of sectionHeadings) {
    await expect(page.getByRole('heading', { name: heading })).toBeVisible()
  }
  for (const heading of panelHeadings) {
    await expect(page.getByRole('heading', { name: heading })).toBeVisible()
  }
})

test('canonical and custom not-eligible pages preserve provenance and methodology boundaries', async ({ page }) => {
  await gotoScenario(
    page,
    `/eda?mode=precompute&period_kind=monthly&run=${canonicalRunId}`,
    'eda-canonical',
  )

  await expect(page.getByText('Rilis v3 terpublikasi (paritas kanonik)')).toBeVisible()
  const methodology = page.getByRole('note', { name: 'Batas metodologi EDA' })
  await expect(methodology).toContainText('Kualitas kandidat saja')
  await expect(methodology).toContainText('deskriptif, bukan kausal')
  await expect(methodology).toContainText('tidak memuat bukti model atau deteksi anomali')

  await gotoScenario(
    page,
    `/eda?mode=custom&from=${cachedFrom}&to=${cachedTo}&run=${cachedRunId}`,
    'eda-custom-not-eligible',
  )
  await expect(page.getByText('Komputasi rentang setara-algoritme')).toBeVisible()
  await expect(page.getByText('Kandidat perubahan belum memenuhi syarat')).toBeVisible()
  await expect(page.getByText('Bootstrap belum memenuhi syarat')).toBeVisible()
})

test('explicit Hitung EDA cache hit selects the custom run without creating or polling a job', async ({ page }) => {
  const requests = trackEdaRequests(page)
  await gotoCustomScenario(page, 'active-anomaly', cachedFrom, cachedTo)

  await page.getByRole('button', { name: 'Hitung EDA' }).click()

  await expect(page).toHaveURL(new RegExp(`run=${cachedRunId}`))
  await expect(page.getByText('Komputasi rentang setara-algoritme')).toBeVisible()
  expect(countRequests(requests, 'POST /api/eda/compute')).toBe(1)
  expect(countRequests(requests, 'GET /api/eda/jobs/')).toBe(0)
})

test('custom compute exposes a queued state and locks duplicate submission', async ({ page }) => {
  await gotoCustomScenario(page, 'eda-job-queued')
  const submit = page.getByRole('button', { name: 'Hitung EDA' })

  await submit.click()

  await expect(page.getByText('Status perhitungan EDA: queued')).toBeVisible()
  await expect(submit).toBeDisabled()
})

test('custom compute exposes a running state and locks duplicate submission', async ({ page }) => {
  await gotoCustomScenario(page, 'eda-job-running')
  const submit = page.getByRole('button', { name: 'Hitung EDA' })

  await submit.click()

  await expect(page.getByText('Status perhitungan EDA: running')).toBeVisible()
  await expect(submit).toBeDisabled()
})

test('custom compute publishes the succeeded run after one deterministic job poll', async ({ page }) => {
  const requests = trackEdaRequests(page)
  await gotoCustomScenario(page, 'eda-job-success')

  await page.getByRole('button', { name: 'Hitung EDA' }).click()

  await expect(page).toHaveURL(new RegExp(`run=${publishedRunId}`))
  await expect(page.getByText('Komputasi rentang setara-algoritme')).toBeVisible()
  expect(countRequests(requests, 'POST /api/eda/compute')).toBe(1)
  expect(countRequests(requests, 'GET /api/eda/jobs/')).toBe(1)
})

test('failed compute stops polling and Retry creates exactly one replacement request', async ({ page }) => {
  const requests = trackEdaRequests(page)
  await gotoCustomScenario(page, 'eda-job-failed')

  await page.getByRole('button', { name: 'Hitung EDA' }).click()
  const failure = page.getByRole('alert').filter({ hasText: 'Perhitungan EDA gagal setelah tiga percobaan.' })
  await expect(failure).toBeVisible()
  expect(countRequests(requests, 'POST /api/eda/compute')).toBe(1)
  expect(countRequests(requests, 'GET /api/eda/jobs/')).toBe(1)

  await failure.getByRole('button', { name: 'Retry' }).click()

  await expect(page).toHaveURL(new RegExp(`run=${cachedRunId}`))
  expect(countRequests(requests, 'POST /api/eda/compute')).toBe(2)
  expect(countRequests(requests, 'GET /api/eda/jobs/')).toBe(1)
})

test('period-list Problem Details recover in place without creating compute work', async ({
  page,
  httpErrorGuard,
}) => {
  const requests = trackEdaRequests(page)
  httpErrorGuard.allow(503)
  await gotoScenario(page, '/eda', 'normal')
  await expect(page).toHaveURL(/run=run-b02-monthly-2026-02/)
  await disableAppQueryRetries(page)
  await setMockScenarioOnPage(page, 'eda-period-error')
  requests.length = 0
  await refetchAppQuery(page, ['eda', 'periods'])
  const failure = page.getByRole('group', { name: 'Kontrol run EDA' }).getByRole('alert')

  await expect(failure).toContainText('EDA period list unavailable')
  await expect(failure).toContainText('Request ID: req-eda-period-monthly')
  await failure.getByRole('button', { name: 'Retry' }).click()

  await expect(page).toHaveURL(/run=run-b02-monthly-2026-02/)
  expect(countRequests(requests, 'GET /api/eda/periods')).toBe(6)
  expect(countRequests(requests, 'POST /api/eda/compute')).toBe(0)
  expect(countRequests(requests, 'GET /api/eda/jobs/')).toBe(0)
})

test('job Problem Details retry resumes the same poll without duplicating compute', async ({
  page,
  httpErrorGuard,
}) => {
  const requests = trackEdaRequests(page)
  httpErrorGuard.allow(503)
  await gotoCustomScenario(page, 'normal')
  await disableAppQueryRetries(page)
  await setMockScenarioOnPage(page, 'eda-job-error')
  requests.length = 0
  await page.getByRole('button', { name: 'Hitung EDA' }).click()
  const failure = page.getByRole('group', { name: 'Kontrol run EDA' }).getByRole('alert')

  await expect(failure).toContainText('EDA job status unavailable')
  await expect(failure).toContainText('Request ID: req-eda-job-status')
  await failure.getByRole('button', { name: 'Retry' }).click()

  await expect(page).toHaveURL(new RegExp(`run=${publishedRunId}`))
  expect(countRequests(requests, 'POST /api/eda/compute')).toBe(1)
  expect(countRequests(requests, 'GET /api/eda/jobs/')).toBe(2)
})

test('one section Problem Details stays scoped and recovers only that section', async ({
  page,
  httpErrorGuard,
}) => {
  const requests = trackEdaRequests(page)
  httpErrorGuard.allow(503)
  await gotoScenario(
    page,
    `/eda?mode=precompute&period_kind=monthly&run=${canonicalRunId}`,
    'eda-canonical',
  )
  await expect(page.getByRole('button', { name: 'Lihat data bootstrap' })).toBeVisible()
  await disableAppQueryRetries(page)
  await setMockScenarioOnPage(page, 'eda-section-error')
  requests.length = 0
  await resetAppQuery(page, [
    'eda',
    'run',
    canonicalRunId,
    'section',
    'uncertainty',
  ])
  const failedPanel = panel(page, 'Ketidakpastian bootstrap asosiasi')
  const uncertaintyPath = `GET /api/eda/runs/${canonicalRunId}/sections/uncertainty`

  expect(countRequests(requests, uncertaintyPath)).toBe(1)
  await expect(failedPanel.getByRole('alert')).toContainText('Request ID: req-eda-section-uncertainty')
  await expect(panel(page, 'Cakupan kalender temporal').getByRole('alert')).toHaveCount(0)
  await expect(page.getByRole('heading', { name: 'Audit pairing timestamp' })).toBeVisible()
  await failedPanel.getByRole('button', { name: 'Retry' }).click()

  await expect(failedPanel.getByRole('alert')).toHaveCount(0)
  expect(countRequests(requests, uncertaintyPath)).toBe(2)
  expect(countRequests(requests, 'POST /api/eda/compute')).toBe(0)
})

test('multiple section Problem Details remain independent and each retry issues one refetch', async ({
  page,
  httpErrorGuard,
}) => {
  const requests = trackEdaRequests(page)
  httpErrorGuard.allow(503)
  await gotoScenario(
    page,
    `/eda?mode=precompute&period_kind=monthly&run=${canonicalRunId}`,
    'eda-canonical',
  )
  await expect(page.getByRole('button', { name: 'Lihat data ringkasan asosiasi' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Lihat data kelayakan struktur temporal' })).toBeVisible()
  await disableAppQueryRetries(page)
  await setMockScenarioOnPage(page, 'eda-multiple-section-error')
  requests.length = 0
  await Promise.all([
    resetAppQuery(page, [
      'eda',
      'run',
      canonicalRunId,
      'section',
      'relationships',
    ]),
    resetAppQuery(page, [
      'eda',
      'run',
      canonicalRunId,
      'section',
      'stationarity',
    ]),
  ])
  const relationship = panel(page, 'Ringkasan asosiasi Suhu–RH')
  const stationarity = panel(page, 'Kelayakan struktur temporal')
  const relationshipsPath = `GET /api/eda/runs/${canonicalRunId}/sections/relationships`
  const stationarityPath = `GET /api/eda/runs/${canonicalRunId}/sections/stationarity`

  expect(countRequests(requests, relationshipsPath)).toBe(1)
  expect(countRequests(requests, stationarityPath)).toBe(1)
  await expect(relationship.getByRole('alert')).toContainText('Request ID: req-eda-section-relationships')
  await expect(stationarity.getByRole('alert')).toContainText('Request ID: req-eda-section-stationarity')
  await expect(panel(page, 'Cakupan kalender temporal').getByRole('alert')).toHaveCount(0)

  await relationship.getByRole('button', { name: 'Retry' }).click()
  await stationarity.getByRole('button', { name: 'Retry' }).click()

  await expect(relationship.getByRole('alert')).toHaveCount(0)
  await expect(stationarity.getByRole('alert')).toHaveCount(0)
  expect(countRequests(requests, relationshipsPath)).toBe(2)
  expect(countRequests(requests, stationarityPath)).toBe(2)
  expect(countRequests(requests, 'GET /api/eda/jobs/')).toBe(0)
})
