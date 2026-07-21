export type MockScenario =
  | 'normal'
  | 'active-anomaly'
  | 'stale'
  | 'offline'
  | 'data-gap'
  | 'empty'
  | 'timeout'
  | 'server-error'

export function scenarioFromSearch(search: string): MockScenario {
  const value = new URLSearchParams(search).get('__scenario')
  return value === 'active-anomaly' ||
    value === 'stale' ||
    value === 'offline' ||
    value === 'data-gap' ||
    value === 'empty' ||
    value === 'timeout' ||
    value === 'server-error'
    ? value
    : 'normal'
}
