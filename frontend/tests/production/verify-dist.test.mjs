import assert from 'node:assert/strict'
import { readFile, readdir } from 'node:fs/promises'
import { join, relative, sep } from 'node:path'
import { fileURLToPath } from 'node:url'
import { test } from 'node:test'

const forbiddenArtifactPath = /(?:^|\/)[^/]*(?:mockserviceworker|msw|mocks?|fixtures?|scenario)[^/]*/i
const forbiddenContent = [
  ['MSW worker', /mockServiceWorker/i],
  ['MSW browser initializer', /setupWorker/],
  ['MSW server initializer', /setupServer/],
  ['MSW package', /\bmsw(?:\/(?:browser|node))?\b/i],
  ['scenario query parameter', /__scenario/],
  ['scenario parser', /scenarioFromSearch/],
  ['scenario state', /(?:set|reset)MockScenario|mockState/],
  ['mock-only scenario', /active-anomaly|data-gap|server-error/],
  ['mock alert fixture', /alert_talpha_1_active/],
  ['mock request fixture', /\breq_(?:telemetry_latest|telemetry_history|inference_results|alert_events|current_alerts|eda_summary|eda_distributions|eda_correlation|model_evaluations|system_status|server_error)\b/],
  ['mock timestamp fixture', /2025-12-12T00:02:57/],
  ['live inference claim', /\blive inference\b/i],
  ['production-ready claim', /\bproduction[- ]ready\b/i],
  ['deployed model claim', /\bmodel (?:is )?deployed\b/i],
  ['final evaluation claim', /\b(?:independent )?final evaluation (?:result|report)\b/i],
]
const requiredRelativeApiPaths = [
  '/api/telemetry/latest',
  '/api/inference-results',
  '/api/alerts/current',
  '/api/eda/periods',
  '/api/model-registry',
  '/api/offline-evaluations',
  '/api/system/status',
]
const absoluteApiOrigin = /(?:https?:)?\/\/[a-z0-9._~%:-]+\/api(?:\/|[?#])/i

async function listFiles(directory) {
  const entries = await readdir(directory, { withFileTypes: true })
  const nested = await Promise.all(entries.map((entry) => {
    const path = join(directory, entry.name)
    if (entry.isDirectory()) return listFiles(path)
    return entry.isFile() ? [path] : []
  }))
  return nested.flat().sort()
}

export async function verifyProductionArtifact(distDirectory) {
  const root = fileURLToPath(distDirectory)
  const artifactFiles = await listFiles(root)
  const files = artifactFiles.map((file) => relative(root, file).split(sep).join('/'))
  const text = (await Promise.all(artifactFiles.map((file) => readFile(file)))).join('\n')

  assert.ok(files.length > 0, 'dist must contain production artifacts')
  for (const file of files) {
    assert.doesNotMatch(file, forbiddenArtifactPath, `mock artifact found: ${file}`)
  }
  for (const [label, pattern] of forbiddenContent) {
    assert.doesNotMatch(text, pattern, `${label} leaked into dist`)
  }
  for (const path of requiredRelativeApiPaths) {
    assert.ok(text.includes(path), `relative API path missing from dist: ${path}`)
  }
  assert.doesNotMatch(text, absoluteApiOrigin, 'absolute API origin found in dist')

  return {
    files,
    hasMswWorker: false,
    hasScenarioData: false,
    usesRelativeApiPaths: true,
  }
}

test('production artifacts exclude MSW and scenario data and retain relative API paths', async () => {
  const report = await verifyProductionArtifact(new URL('../../dist/', import.meta.url))

  assert.ok(report.files.includes('index.html'))
  assert.deepEqual(
    {
      hasMswWorker: report.hasMswWorker,
      hasScenarioData: report.hasScenarioData,
      usesRelativeApiPaths: report.usesRelativeApiPaths,
    },
    {
      hasMswWorker: false,
      hasScenarioData: false,
      usesRelativeApiPaths: true,
    },
  )
})
