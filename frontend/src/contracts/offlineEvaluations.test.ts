import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'
import { offlineEvaluationsResponse } from '../mocks/fixtures/offlineEvaluations'
import { OfflineEvaluationsResponseSchema } from './offlineEvaluations'

const MODEL_ORDER = ['conv1d', 'gru', 'lstm', 'rnn', 'transformer']

describe('offline evaluations contract', () => {
  it('matches the backend Step 7 fixture byte-for-data and accepts all three scopes', () => {
    const backendFixture = JSON.parse(
      readFileSync(
        resolve(
          process.cwd(),
          '../backend/anomaly_backend/fixtures/offline_eval/offline_evaluations.json',
        ),
        'utf8',
      ),
    ) as unknown

    expect(offlineEvaluationsResponse).toEqual(backendFixture)

    const parsed = OfflineEvaluationsResponseSchema.parse(backendFixture)
    expect(parsed.evaluation).toMatchObject({
      evaluation_split: 'val_injected',
      test_consumed: false,
      primary_scope: 'non_overlapping_evaluation_bins',
      n_evaluation_bins: 2_071,
    })
    expect(parsed.items.map((item) => item.model_family)).toEqual(MODEL_ORDER)
    expect(parsed.items[0]?.scopes.non_overlapping_evaluation_bins).toMatchObject({
      precision: 0.828169014084507,
      recall: 0.725925925925926,
      f1: 0.7736842105263158,
      tn: 1_605,
      fp: 61,
      fn: 111,
      tp: 294,
    })
  })

  it('rejects metrics that do not match their confusion counts', () => {
    const response = structuredClone(offlineEvaluationsResponse)
    response.items[0]!.scopes.timestamp.tp += 1

    expect(OfflineEvaluationsResponseSchema.safeParse(response).success).toBe(false)
  })

  it('rejects a missing evaluation scope', () => {
    const response: Record<string, unknown> = structuredClone(
      offlineEvaluationsResponse,
    )
    const items = response.items as Array<Record<string, unknown>>
    const scopes = items[0]!.scopes as Record<string, unknown>
    delete scopes.timestamp

    expect(OfflineEvaluationsResponseSchema.safeParse(response).success).toBe(false)
  })

  it('rejects any claim that the final test set was consumed', () => {
    const response: Record<string, unknown> = structuredClone(
      offlineEvaluationsResponse,
    )
    const evaluation = response.evaluation as Record<string, unknown>
    evaluation.test_consumed = true

    expect(OfflineEvaluationsResponseSchema.safeParse(response).success).toBe(false)
  })
})
