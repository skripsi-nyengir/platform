/// <reference types="node" />

import { existsSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const frontendRoot = resolve(process.cwd())
const edaFiles = [
  'src/api/eda.ts',
  'src/components/charts/CanvasHeatmap.tsx',
  'src/components/charts/edaV3Options.ts',
  'src/components/charts/relationshipEdaOptions.ts',
  'src/components/charts/structureEdaOptions.ts',
  'src/components/charts/temporalEdaOptions.ts',
  'src/contracts/common.ts',
  'src/contracts/eda.ts',
  'src/features/eda/AssociationSummaryPanel.tsx',
  'src/features/eda/AutocorrelationPanel.tsx',
  'src/features/eda/BootstrapUncertaintyPanel.tsx',
  'src/features/eda/ChangePointPanel.tsx',
  'src/features/eda/EdaRunControls.tsx',
  'src/features/eda/JointDensityPanel.tsx',
  'src/features/eda/PairingAuditPanel.tsx',
  'src/features/eda/QualityExcerptPanel.tsx',
  'src/features/eda/QualityIntegrityPanel.tsx',
  'src/features/eda/RollingCorrelationPanel.tsx',
  'src/features/eda/SpectrumPanel.tsx',
  'src/features/eda/StationarityEligibilityPanel.tsx',
  'src/features/eda/StlDecompositionPanel.tsx',
  'src/features/eda/TemporalCoveragePanel.tsx',
  'src/features/eda/TemporalDistributionPanel.tsx',
  'src/features/eda/UnivariateDiagnosticsPanel.tsx',
  'src/features/eda/WeekdayHourCoveragePanel.tsx',
  'src/features/eda/queries.ts',
  'src/mocks/fixtures/eda.ts',
  'src/pages/EdaPage.tsx',
] as const
const retiredFiles = [
  'src/components/charts/edaOptions.ts',
  'src/features/eda/CandidateOutliersPanel.tsx',
  'src/features/eda/CorrelationPanel.tsx',
  'src/features/eda/CoveragePanel.tsx',
  'src/features/eda/DistributionPanel.tsx',
  'src/features/eda/EdaFilters.tsx',
  'src/features/eda/MissingnessPanel.tsx',
  'src/features/eda/SensorComparisonPanel.tsx',
  'src/features/eda/TemporalPatternsPanel.tsx',
] as const
const forbiddenTokens = [
  'TALPHA',
  'talphaValidationRange',
  'candidate_outlier',
  'candidateOutlier',
  'score_provenance',
  'model_version',
  'simulated_preview',
  'artifact_backed',
  '86,104',
  '86104',
] as const

function containsForbiddenToken(source: string, token: string): boolean {
  if (token === '86104') return /(?<![\d.])86104(?!\d)/.test(source)
  if (token === '86,104') return /(?<!\d)86,104(?!\d)/.test(source)
  return source.includes(token)
}

function edaHandlerSource(): string {
  const source = readFileSync(resolve(frontendRoot, 'src/mocks/handlers.ts'), 'utf8')
  return source
    .split(/\n(?=\s{4}http\.)/)
    .filter((block) => block.includes("'/api/eda/"))
    .join('\n')
}

describe('legacy EDA removal', () => {
  it('keeps the explicit EDA production scope free of legacy identity and model coupling', () => {
    const sources: [string, string][] = edaFiles.map((relativePath) => {
      const path = resolve(frontendRoot, relativePath)
      expect(existsSync(path), `EDA guard allowlist path is missing: ${relativePath}`).toBe(true)
      return [relativePath, readFileSync(path, 'utf8')]
    })
    sources.push(['src/mocks/handlers.ts#eda', edaHandlerSource()])

    const matches = sources.flatMap(([relativePath, source]) =>
      forbiddenTokens
        .filter((token) => containsForbiddenToken(source, token))
        .map((token) => `${relativePath}: ${token}`),
    )
    expect(matches).toEqual([])
  })

  it('keeps retired EDA files deleted', () => {
    expect(retiredFiles.filter((relativePath) => existsSync(resolve(frontendRoot, relativePath))))
      .toEqual([])
  })
})
