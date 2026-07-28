import { describe, expect, it } from 'vitest'
import { boxStats, invNormalCdf, moments, qqPoints } from './univariateShape'

const symmetric = {
  edges: [-2.5, -1.5, -0.5, 0.5, 1.5, 2.5],
  histogram: [1, 4, 6, 4, 1],
}

describe('univariate histogram shape diagnostics', () => {
  it('derives monotonic box statistics and symmetric moments', () => {
    const box = boxStats(symmetric)
    const distributionMoments = moments(symmetric)

    expect(box).not.toBeNull()
    expect(distributionMoments).not.toBeNull()
    expect(box!.q1).toBeLessThanOrEqual(box!.median)
    expect(box!.median).toBeLessThanOrEqual(box!.q3)
    expect(box!.whiskerLow).toBeGreaterThanOrEqual(box!.min)
    expect(box!.whiskerHigh).toBeLessThanOrEqual(box!.max)
    expect(distributionMoments!.skewness).toBeCloseTo(0, 10)
    expect(distributionMoments!.excessKurtosis).toBeCloseTo(-0.5, 10)
  })

  it('detects a right-skewed binned distribution', () => {
    const distributionMoments = moments({
      edges: [0, 1, 2, 3, 4, 5],
      histogram: [20, 8, 4, 2, 1],
    })

    expect(distributionMoments).not.toBeNull()
    expect(distributionMoments!.skewness).toBeGreaterThan(0)
  })

  it('builds capped QQ points and normal reference endpoints', () => {
    const qq = qqPoints(symmetric, 60)

    expect(qq).not.toBeNull()
    expect(qq!.points).toHaveLength(symmetric.histogram.length)
    expect(qq!.referenceLine).toHaveLength(2)
    expect(qq!.points[0]!.theoretical).toBeLessThan(qq!.points.at(-1)!.theoretical)
  })

  it('implements the Acklam inverse standard-normal CDF', () => {
    expect(invNormalCdf(0.5)).toBeCloseTo(0, 10)
    expect(invNormalCdf(0.975)).toBeCloseTo(1.959_964, 5)
    expect(invNormalCdf(0)).toBe(Number.NEGATIVE_INFINITY)
    expect(invNormalCdf(1)).toBe(Number.POSITIVE_INFINITY)
  })

  it('returns null for empty or zero-variance moments', () => {
    expect(boxStats({ edges: [0, 1], histogram: [0] })).toBeNull()
    expect(moments({ edges: [0, 1], histogram: [4] })).toBeNull()
    expect(qqPoints({ edges: [0, 1], histogram: [4] })).toBeNull()
  })
})
