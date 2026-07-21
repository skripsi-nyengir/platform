/// <reference types="node" />

import { readdirSync, readFileSync } from 'node:fs'
import { join, relative, resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const sourceDirectory = resolve(process.cwd(), 'src')
const testFile = join(sourceDirectory, 'components/charts/noEcharts.test.ts')
const forbiddenPatterns = [
  ['echarts package or runtime', /\becharts\b/i],
  ['EChart module', /\/EChart\b/],
  ['echartsTheme module', /\bechartsTheme\b/],
  [
    'legacy option builder',
    /\b(?:buildTemporalOptions|buildOverviewSparklineOptions|buildHistogramOptions|buildScatterOptions|buildConfusionMatrixOptions|buildRocOptions|buildPrecisionRecallOptions)\b/,
  ],
] as const

function sourceFiles(directory: string): string[] {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const path = join(directory, entry.name)
    return entry.isDirectory() ? sourceFiles(path) : [path]
  })
}

describe('ECharts removal', () => {
  it('keeps every source file free of ECharts and its legacy option builders', () => {
    const violations = sourceFiles(sourceDirectory)
      .filter((path) => path !== testFile)
      .flatMap((path) => {
        const source = readFileSync(path, 'utf8')
        return forbiddenPatterns
          .filter(([, pattern]) => pattern.test(source))
          .map(([name]) => `${relative(sourceDirectory, path)}: ${name}`)
      })

    expect(violations).toEqual([])
  })
})
