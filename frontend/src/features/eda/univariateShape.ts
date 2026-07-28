export interface BinnedDistribution {
  edges: number[]
  histogram: number[]
}

export interface BoxStats {
  q1: number
  median: number
  q3: number
  iqr: number
  whiskerLow: number
  whiskerHigh: number
  min: number
  max: number
}

export interface Moments {
  mean: number
  std: number
  skewness: number
  excessKurtosis: number
}

export interface QqPoint {
  theoretical: number
  sample: number
}

export interface QqData {
  points: QqPoint[]
  referenceLine: QqPoint[]
}

interface PreparedDistribution extends BinnedDistribution {
  centers: number[]
  cumulativeFractions: number[]
  total: number
}

const a = [
  -3.969683028665376e1,
  2.209460984245205e2,
  -2.759285104469687e2,
  1.383577518672690e2,
  -3.066479806614716e1,
  2.506628277459239e0,
]
const b = [
  -5.447609879822406e1,
  1.615858368580409e2,
  -1.556989798598866e2,
  6.680131188771972e1,
  -1.328068155288572e1,
]
const c = [
  -7.784894002430293e-3,
  -3.223964580411365e-1,
  -2.400758277161838e0,
  -2.549732539343734e0,
  4.374664141464968e0,
  2.938163982698783e0,
]
const d = [
  7.784695709041462e-3,
  3.224671290700398e-1,
  2.445134137142996e0,
  3.754408661907416e0,
]

function prepare({ edges, histogram }: BinnedDistribution): PreparedDistribution | null {
  if (edges.length !== histogram.length + 1 || histogram.length === 0) return null
  if (edges.some((edge, index) => !Number.isFinite(edge) || (index > 0 && edge <= edges[index - 1]!))) return null
  if (histogram.some((count) => !Number.isFinite(count) || count < 0)) return null

  const total = histogram.reduce((sum, count) => sum + count, 0)
  if (total === 0) return null

  let running = 0
  return {
    edges,
    histogram,
    total,
    centers: histogram.map((_, index) => (edges[index]! + edges[index + 1]!) / 2),
    cumulativeFractions: histogram.map((count) => {
      running += count
      return running / total
    }),
  }
}

function quantile(distribution: PreparedDistribution, q: number): number {
  let previousFraction = 0

  for (let index = 0; index < distribution.histogram.length; index += 1) {
    const fraction = distribution.cumulativeFractions[index]!
    if (fraction >= q && fraction > previousFraction) {
      const start = distribution.edges[index]!
      const end = distribution.edges[index + 1]!
      const value = start + ((q - previousFraction) / (fraction - previousFraction)) * (end - start)
      return Math.min(distribution.edges.at(-1)!, Math.max(distribution.edges[0]!, value))
    }
    previousFraction = fraction
  }

  return distribution.edges.at(-1)!
}

function calculateMoments(distribution: PreparedDistribution): Moments | null {
  const mean = distribution.histogram.reduce(
    (sum, count, index) => sum + count * distribution.centers[index]!,
    0,
  ) / distribution.total
  const centeredMoment = (power: number) => distribution.histogram.reduce(
    (sum, count, index) => sum + count * ((distribution.centers[index]! - mean) ** power),
    0,
  ) / distribution.total
  const m2 = centeredMoment(2)
  const std = Math.sqrt(m2)
  if (std === 0) return null

  // Sheppard's correction exists for binned kurtosis but is intentionally not applied here.
  return {
    mean,
    std,
    skewness: centeredMoment(3) / (std ** 3),
    excessKurtosis: centeredMoment(4) / (std ** 4) - 3,
  }
}

export function boxStats(input: BinnedDistribution): BoxStats | null {
  const distribution = prepare(input)
  if (distribution === null) return null

  const q1 = quantile(distribution, 0.25)
  const median = quantile(distribution, 0.5)
  const q3 = quantile(distribution, 0.75)
  const iqr = q3 - q1
  const min = distribution.edges[0]!
  const max = distribution.edges.at(-1)!

  return {
    q1,
    median,
    q3,
    iqr,
    whiskerLow: Math.max(min, q1 - 1.5 * iqr),
    whiskerHigh: Math.min(max, q3 + 1.5 * iqr),
    min,
    max,
  }
}

export function moments(input: BinnedDistribution): Moments | null {
  const distribution = prepare(input)
  return distribution === null ? null : calculateMoments(distribution)
}

export function qqPoints(input: BinnedDistribution, m = 60): QqData | null {
  const distribution = prepare(input)
  if (distribution === null) return null
  const distributionMoments = calculateMoments(distribution)
  if (distributionMoments === null) return null

  const pointCount = Math.min(60, distribution.histogram.length, Math.floor(m))
  if (pointCount <= 0) return null
  const points = Array.from({ length: pointCount }, (_, index) => {
    const p = (index + 0.5) / pointCount
    return {
      theoretical: invNormalCdf(p),
      sample: quantile(distribution, p),
    }
  })
  const minimumTheoretical = points[0]!.theoretical
  const maximumTheoretical = points.at(-1)!.theoretical

  return {
    points,
    referenceLine: [minimumTheoretical, maximumTheoretical].map((theoretical) => ({
      theoretical,
      sample: distributionMoments.mean + distributionMoments.std * theoretical,
    })),
  }
}

export function invNormalCdf(p: number): number {
  if (p <= 0) return Number.NEGATIVE_INFINITY
  if (p >= 1) return Number.POSITIVE_INFINITY

  const plow = 0.02425
  const phigh = 1 - plow
  if (p < plow) {
    const q = Math.sqrt(-2 * Math.log(p))
    return (((((c[0]! * q + c[1]!) * q + c[2]!) * q + c[3]!) * q + c[4]!) * q + c[5]!) /
      ((((d[0]! * q + d[1]!) * q + d[2]!) * q + d[3]!) * q + 1)
  }
  if (p <= phigh) {
    const q = p - 0.5
    const r = q * q
    return (((((a[0]! * r + a[1]!) * r + a[2]!) * r + a[3]!) * r + a[4]!) * r + a[5]!) * q /
      (((((b[0]! * r + b[1]!) * r + b[2]!) * r + b[3]!) * r + b[4]!) * r + 1)
  }

  const q = Math.sqrt(-2 * Math.log(1 - p))
  return -(((((c[0]! * q + c[1]!) * q + c[2]!) * q + c[3]!) * q + c[4]!) * q + c[5]!) /
    ((((d[0]! * q + d[1]!) * q + d[2]!) * q + d[3]!) * q + 1)
}
