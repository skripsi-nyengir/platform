import { describe, expect, it } from 'vitest'
import * as alertContracts from './alerts'
import { BucketSchema, SensorIdSchema } from './common'
import { InferenceResponseSchema } from './inference'
import { SystemStatusResponseSchema } from './systemHealth'
import { TelemetryHistoryResponseSchema } from './telemetry'

describe('B02 public contracts', () => {
  it('accepts only the public B02 device', () => {
    expect(SensorIdSchema.parse('b02f3872-ruang-produksi')).toBe('b02f3872-ruang-produksi')
    expect(SensorIdSchema.safeParse('talpha-1').success).toBe(false)
  })

  it('uses the Task 9 history bucket contract', () => {
    expect(BucketSchema.options).toEqual(['raw', 'one_minute', 'adaptive'])
  })

  it('accepts Task 9 telemetry aggregate metadata', () => {
    expect(TelemetryHistoryResponseSchema.parse({
      request_id: 'req-telemetry',
      device_id: 'b02f3872-ruang-produksi',
      from: '2026-07-31T02:00:00',
      to: '2026-07-31T08:00:00',
      bucket: 'one_minute',
      bucket_seconds: 60,
      time_zone: 'Asia/Jakarta',
      points: [{
        ts: '2026-07-31T02:00:00',
        temperature_c: 26,
        relative_humidity_pct: 70,
        temperature_c_min: 25.8,
        temperature_c_max: 26.2,
        relative_humidity_pct_min: 69.5,
        relative_humidity_pct_max: 70.5,
        sample_count: 2,
        gap_before: false,
      }],
      next_cursor: null,
      returned_count: 1,
    }).bucket_seconds).toBe(60)
  })

  it('accepts Task 9 inference severity and latest bucket score', () => {
    const response = InferenceResponseSchema.parse({
      request_id: 'req-inference',
      device_id: 'b02f3872-ruang-produksi',
      from: '2026-07-31T02:00:00',
      to: '2026-07-31T08:00:00',
      bucket: 'one_minute',
      bucket_seconds: 60,
      time_zone: 'Asia/Jakarta',
      model_version: 'lstm-live-v1',
      points: [{
        window_start_ts: '2026-07-31T02:00:00',
        window_end_ts: '2026-07-31T02:00:10',
        score_ts: '2026-07-31T02:00:10',
        score: 0.9,
        latest_score: 0.7,
        threshold: 0.5,
        is_anomaly: true,
        severity: 'critical',
        sample_count: 3,
        model_version: 'lstm-live-v1',
        score_provenance: 'artifact_backed',
        recon_temperature_c: null,
        recon_relative_humidity_pct: null,
        band_half_temperature_c: null,
        band_half_relative_humidity_pct: null,
      }],
      next_cursor: null,
      returned_count: 1,
    })

    expect(response.points[0]).toMatchObject({ severity: 'critical', latest_score: 0.7, sample_count: 3 })
  })

  it('accepts Task 9 alert detail context and nullable replay IDs', () => {
    const schema = Reflect.get(alertContracts, 'AlertDetailResponseSchema') as {
      parse: (input: unknown) => { alert: { replay_job_id: string | null }, episode_points: unknown[] }
    } | undefined
    expect(schema).toBeDefined()
    const sourceReading = {
      ts: '2026-07-31T02:00:00',
      temperature_c: 26,
      relative_humidity_pct: 70,
      temperature_c_min: 26,
      temperature_c_max: 26,
      relative_humidity_pct_min: 70,
      relative_humidity_pct_max: 70,
      sample_count: 1,
      gap_before: false,
    }
    const alert = {
      alert_id: 'alert-live-1',
      device_id: 'b02f3872-ruang-produksi',
      status: 'acknowledged',
      episode_start_ts: '2026-07-31T02:00:00',
      episode_end_ts: '2026-07-31T02:01:00',
      last_score_ts: '2026-07-31T02:01:00',
      created_at: '2026-07-30T19:01:00Z',
      latest_event_at: '2026-07-30T19:02:00Z',
      latest_event_id: 'event-2',
      peak_score: 0.9,
      latest_score: 0.7,
      anomalous_window_count: 2,
      replay_job_id: null,
      threshold: 0.5,
      model_version: 'lstm-live-v1',
      detection_basis: 'artifact_backed',
      can_acknowledge: false,
      can_resolve: true,
    }
    const inference = {
      window_start_ts: '2026-07-31T02:00:00',
      window_end_ts: '2026-07-31T02:00:10',
      score_ts: '2026-07-31T02:00:10',
      score: 0.9,
      latest_score: 0.9,
      threshold: 0.5,
      is_anomaly: true,
      severity: 'critical',
      sample_count: 1,
      model_version: 'lstm-live-v1',
      score_provenance: 'artifact_backed',
      recon_temperature_c: null,
      recon_relative_humidity_pct: null,
      band_half_temperature_c: null,
      band_half_relative_humidity_pct: null,
    }
    const parsed = schema?.parse({
      request_id: 'req-alert-detail',
      time_zone: 'Asia/Jakarta',
      alert,
      context_before: [sourceReading],
      episode_points: [{ inference, source_readings: Array.from({ length: 10 }, () => sourceReading) }],
      recovery_points: [],
    })

    expect(parsed?.alert.replay_job_id).toBeNull()
    expect(parsed?.episode_points).toHaveLength(1)
  })

  it('accepts Task 9 alert-event snapshot bounds', () => {
    expect(alertContracts.AlertEventsResponseSchema.parse({
      request_id: 'req-events',
      time_zone: 'Asia/Jakarta',
      from: null,
      to: '2026-07-31T01:00:00Z',
      events: [],
      next_cursor: null,
      returned_count: 0,
    }).to).toBe('2026-07-31T01:00:00Z')
  })

  it('accepts actionable Task 9 live-health fields', () => {
    const response = SystemStatusResponseSchema.parse({
      request_id: 'req-health',
      checked_at: '2026-07-31T01:00:00Z',
      overall_observation: 'Live telemetry is degraded.',
      services: [],
      telemetry: {
        classification: 'degraded',
        reasons: ['Start the live subscriber or restore its database lease.'],
        configuration_valid: true,
        lease_active: false,
        fencing_token: null,
        database_heartbeat: null,
        connection_state: 'disconnected',
        connack_received: false,
        suback_received: false,
        latest_ts: '2026-07-31T07:59:00',
        last_valid_reading_ts: '2026-07-31T07:59:00',
        last_valid_reading_at: '2026-07-31T00:59:00Z',
        age_seconds: 60,
        last_gap_at: null,
        invalid_message_count: null,
        retained_message_count: null,
        last_persistence_failure_at: null,
        ingress_queue_depth: null,
        dropped_newest_count: null,
        pending_boundary_count: 0,
        durable_backlog_count: 0,
        cursor_ts: '2026-07-31T07:59:00',
        cursor_id: 'row-1',
        recovery_ready: false,
        active_model_version: 'lstm-live-v1',
        active_scaler_corpus_id: 'b02-live',
        artifact_hashes: { model: 'abc' },
        retry_state: 'idle',
        fresh_sensor_count: 1,
        stale_sensor_count: 0,
        offline_sensor_count: 0,
      },
    })

    expect(response.telemetry.reasons).toHaveLength(1)
  })

})
