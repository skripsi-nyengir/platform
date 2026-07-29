import { publicDeviceId, simDeviceId, type CorpusDeviceId } from '../../contracts/common'
import type {
  Device,
  ModelFamily,
  ModelsResponse,
  ReplayJob,
} from '../../contracts/preview'

export const previewDevice = Object.freeze({
  device_id: publicDeviceId,
  display_name: 'TALPHA Ruang Produksi',
  time_zone: 'Asia/Jakarta',
  channels: ['suhu', 'rh'],
  corpus_from: '2026-02-01T00:00:00',
  corpus_to: '2026-06-01T00:00:00',
  import_readiness: 'ready',
} satisfies Device)

const families = [
  ['ewma', 'EWMA'],
  ['pca', 'PCA'],
  ['wsn-dense-ae', 'WSN Dense AE'],
  ['lstm-ae', 'LSTM-AE'],
  ['usad', 'USAD'],
  ['cfc-autoencoder', 'CfC Autoencoder'],
  ['mtad-gat', 'MTAD-GAT'],
] as const

export const previewModelFamilies = Object.freeze(families.map(([model_key, display_name]) => ({
  model_key,
  display_name,
  artifact_status: 'pending',
  versions: [{
    version: `preview-${model_key}-v1`,
    runtime_kind: 'preview_simulator',
    selectable: true,
    compatible: true,
    artifact_status: 'pending',
    score_provenance: 'simulated_preview',
  }],
} satisfies ModelFamily)))

export function modelsResponse(activeModelVersion: string): ModelsResponse {
  return {
    request_id: 'req_models',
    device_id: publicDeviceId,
    active_activation_id: `activation-${activeModelVersion}`,
    active_model_version: activeModelVersion,
    families: previewModelFamilies.map((family) => structuredClone(family)),
  }
}

export function replayJob(
  jobId: string,
  from: string,
  to: string,
  modelVersion: string,
  status: ReplayJob['status'] = 'queued',
  deviceId: CorpusDeviceId = publicDeviceId,
): ReplayJob {
  return {
    job_id: jobId,
    device_id: deviceId,
    from,
    to,
    time_zone: 'Asia/Jakarta',
    model_version: modelVersion,
    activation_id: `activation-${modelVersion}`,
    score_provenance: deviceId === simDeviceId ? 'artifact_backed' : 'simulated_preview',
    status,
    progress: status === 'succeeded' ? 1 : status === 'running' ? 0.5 : 0,
    processed_count: status === 'succeeded' ? 100 : status === 'running' ? 50 : 0,
    result_count: status === 'succeeded' ? 100 : 0,
    episode_count: status === 'succeeded' ? 2 : 0,
    submitted_at: '2026-07-24T08:00:00Z',
    started_at: status === 'queued' ? null : '2026-07-24T08:00:01Z',
    completed_at: status === 'succeeded' ? '2026-07-24T08:00:05Z' : null,
    error_code: null,
    error_detail: null,
  }
}
