import '@testing-library/jest-dom/vitest'
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import {
  ModelsResponseSchema,
  ReplayJobRequestSchema,
} from './contracts/preview'
import {
  publicDeviceId,
  sensorIds,
  sensorLabels,
  wibHistoricalDateTimeToUtcInstant,
} from './contracts/common'
import {
  AlertEventsQuerySchema,
} from './contracts/alerts'
import {
  ModelEvaluationDetailSchema,
  ModelEvaluationSummarySchema,
} from './contracts/modelEvaluation'
import { modelsResponse, previewDevice, previewModelFamilies } from './mocks/fixtures/preview'
import {
  modelEvaluationDetails,
  modelEvaluationSummaries,
} from './mocks/fixtures/modelEvaluations'
import { renderApp } from './test/renderApp'

describe('B02F3872 preview contract', () => {
  it('exposes one WIB device and exactly seven pending model families', () => {
    expect(sensorIds).toEqual([publicDeviceId])
    expect(sensorLabels[publicDeviceId]).toBe('B02')
    expect(previewDevice).toMatchObject({
      time_zone: 'Asia/Jakarta',
      channels: ['suhu', 'rh'],
      import_readiness: 'ready',
    })
    expect(previewModelFamilies).toHaveLength(7)
    expect(previewModelFamilies.every((family) => family.artifact_status === 'pending')).toBe(true)
    expect(ModelsResponseSchema.parse(modelsResponse('preview-lstm-ae-v1')).active_model_version)
      .toBe('preview-lstm-ae-v1')
  })

  it('enforces half-open replay ordering and the 31-day maximum', () => {
    const base = {
      command_id: '550e8400-e29b-41d4-a716-446655440000',
      device_id: publicDeviceId,
      from: '2026-02-01T00:00:00',
    } as const
    expect(ReplayJobRequestSchema.safeParse({ ...base, to: '2026-03-04T00:00:00' }).success)
      .toBe(true)
    expect(ReplayJobRequestSchema.safeParse({ ...base, to: '2026-03-04T00:00:01' }).success)
      .toBe(false)
    expect(ReplayJobRequestSchema.safeParse({ ...base, to: base.from }).success).toBe(false)
  })

  it('parses seven public reported Dandy pilot rows with honest provenance', () => {
    expect(modelEvaluationSummaries).toHaveLength(7)
    for (const summary of modelEvaluationSummaries) {
      expect(ModelEvaluationSummarySchema.parse(summary)).toMatchObject({
        track: 'reported_dandy_pilot',
        validation_only: false,
        test_evaluated: true,
        test_observed: true,
        independent_final: false,
        report_source: 'reported_dandy_pilot',
        label_source: 'synthetic_injection',
        evaluation_kind: 'comparison_snapshot',
        threshold_policy: {
          source: 'reported_dandy_pilot',
          comparator: '>',
        },
      })
      expect(summary.source_commit).toMatch(/^[0-9a-f]{40}$/)
      expect(summary.source_path).toBe('notebooks/step10/summaries/step10_comparison_summary.json')
      expect(summary.source_sha256).toMatch(/^[0-9a-f]{64}$/)
      expect(ModelEvaluationDetailSchema.parse(modelEvaluationDetails[summary.version]).metrics)
        .toHaveProperty('stuck_event_hit_rate', 0)
    }
  })

  it('converts WIB corpus filters to UTC operational instants for alert event queries', () => {
    const from = wibHistoricalDateTimeToUtcInstant('2026-02-01T00:00:00')
    const to = wibHistoricalDateTimeToUtcInstant('2026-02-02T00:00:00')
    expect({ from, to }).toEqual({
      from: '2026-01-31T17:00:00.000Z',
      to: '2026-02-01T17:00:00.000Z',
    })
    expect(AlertEventsQuerySchema.safeParse({ from, to }).success).toBe(true)
    expect(AlertEventsQuerySchema.safeParse({
      from: '2026-02-01T00:00:00',
      to: '2026-02-02T00:00:00',
    }).success).toBe(false)
  })
})

describe('B02F3872 preview UI', () => {
  it('renders registry, pilot disclaimer, artifact readiness, and replay controls', async () => {
    renderApp('/model-evaluation')

    expect(await screen.findByRole('heading', { name: 'Model registry' })).toBeVisible()
    expect(await screen.findAllByText('Artifact Pending')).toHaveLength(7)
    expect(screen.getAllByText('Simulasi preview').length).toBeGreaterThanOrEqual(7)
    expect(screen.getByText(/satu run; test sudah diamati/i)).toBeVisible()
    expect(screen.getByText(/seluruh model gagal skenario stuck/i)).toBeVisible()
    expect(await screen.findAllByText(/Evaluasi final independen: tidak/)).toHaveLength(7)
    expect(screen.getAllByText(/notebooks\/step10\/summaries/)).toHaveLength(7)
    expect(screen.getByRole('heading', { name: 'Preview replay' })).toBeVisible()
  })

  it('confirms a future-only activation without mutating history', async () => {
    const user = userEvent.setup()
    renderApp('/model-evaluation')
    const registry = await screen.findByRole('heading', { name: 'Model registry' })
    const section = registry.closest('section')
    expect(section).not.toBeNull()

    await user.click(within(section as HTMLElement).getAllByRole('button', { name: 'Pilih model' })[0])
    const dialog = screen.getByRole('dialog')
    expect(dialog).toHaveTextContent('berlaku untuk replay berikutnya')
    expect(dialog).toHaveTextContent('histori lama tidak berubah')
    await user.click(within(dialog).getByRole('button', { name: 'Aktifkan untuk replay berikutnya' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(within(section as HTMLElement).getAllByText('Dipilih')).toHaveLength(1)
  })

  it('submits one replay command and exposes its model/provenance progress', async () => {
    const user = userEvent.setup()
    renderApp('/model-evaluation')
    const replayHeading = await screen.findByRole('heading', { name: 'Preview replay' })
    const replay = replayHeading.closest('section')
    expect(replay).not.toBeNull()

    const submit = within(replay as HTMLElement).getByRole('button', { name: 'Jalankan replay' })
    await user.click(submit)
    expect(await within(replay as HTMLElement).findByRole('status', { name: 'Replay progress' }))
      .toHaveTextContent(/preview-.*-v1/)
    expect(within(replay as HTMLElement).getByText(/Simulasi preview/)).toBeVisible()
  })
})
