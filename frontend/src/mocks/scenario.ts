export type MockScenario =
  | 'normal'
  | 'active-anomaly'
  | 'stale'
  | 'offline'
  | 'data-gap'
  | 'empty'
  | 'timeout'
  | 'server-error'
  | 'unauthenticated'
  | 'login-invalid'
  | 'login-locked'

const edaScenarios = [
  'eda-latest-fallback',
  'eda-canonical',
  'eda-custom-not-eligible',
  'eda-job-queued',
  'eda-job-running',
  'eda-job-success',
  'eda-job-failed',
  'eda-period-error',
  'eda-job-error',
  'eda-section-error',
  'eda-multiple-section-error',
] as const

export type EdaMockScenario = typeof edaScenarios[number]
export type AppMockScenario = MockScenario | EdaMockScenario

export function scenarioFromSearch(search: string): AppMockScenario {
  const value = new URLSearchParams(search).get('__scenario')
  return value === 'active-anomaly' ||
    value === 'stale' ||
    value === 'offline' ||
    value === 'data-gap' ||
    value === 'empty' ||
    value === 'timeout' ||
    value === 'server-error' ||
    value === 'unauthenticated' ||
    value === 'login-invalid' ||
    value === 'login-locked' ||
    edaScenarios.some((scenario) => scenario === value)
      ? value as AppMockScenario
      : 'normal'
}
