import { describe, expect, it } from 'vitest'
import { getAlertEvents } from '../api/alerts'
import {
  computeEda,
  getEdaJob,
  getEdaPeriods,
  getEdaSection,
} from '../api/eda'
import {
  edaFailedJob,
  edaReadyMonthlyRun,
  edaRunningCustomJob,
} from './fixtures/eda'

describe('B02 mock handlers', () => {
  it('returns the deterministic monthly run and exact custom compute states', async () => {
    const periods = await getEdaPeriods({ period_kind: 'monthly' })
    const cacheHit = await computeEda({
      device_id: 'b02f3872-39a2-4b6f-a4ec-045a287fde4b',
      time_zone: 'Asia/Jakarta',
      period_kind: 'custom',
      from: '2026-02-01T00:00:00',
      to: '2026-02-02T00:00:00',
    })
    const active = await computeEda({
      device_id: 'b02f3872-39a2-4b6f-a4ec-045a287fde4b',
      time_zone: 'Asia/Jakarta',
      period_kind: 'custom',
      from: '2026-02-10T00:00:00',
      to: '2026-02-11T00:00:00',
    })

    expect(periods.items).toEqual([edaReadyMonthlyRun])
    expect(cacheHit).toMatchObject({ cache_hit: true, run: { scope: { period_kind: 'custom' } } })
    expect(active).toMatchObject({ cache_hit: false, job: { status: 'running' } })
    await expect(getEdaJob(edaRunningCustomJob.job_id)).resolves.toMatchObject({
      job: { status: 'running' },
    })
    await expect(getEdaJob(edaFailedJob.job_id)).resolves.toMatchObject({
      job: { status: 'failed', error_code: 'eda_compute_failed' },
    })
  })

  it('serves complete, not-eligible, and failed sections as isolated unions', async () => {
    const complete = await getEdaSection(edaReadyMonthlyRun.run_id, 'quality_overview')
    const notEligible = await getEdaSection(edaReadyMonthlyRun.run_id, 'stationarity')
    const failed = await getEdaSection(edaReadyMonthlyRun.run_id, 'relationships')

    expect(complete).toMatchObject({ status: 'complete', section: 'quality_overview' })
    expect(notEligible).toMatchObject({
      status: 'not_eligible',
      reason_code: 'insufficient_stationarity_primary_tier',
    })
    expect(notEligible.payload).toBeNull()
    expect(failed).toMatchObject({ status: 'failed', reason_code: 'section_compute_failed' })
    expect(failed.payload).toBeNull()
  })

  it('does not require corpus bounds for operational lifecycle history', async () => {
    await expect(getAlertEvents({
      deviceId: 'b02f3872-ruang-produksi',
      limit: 200,
    })).resolves.toMatchObject({ time_zone: 'Asia/Jakarta' })
  })
})
