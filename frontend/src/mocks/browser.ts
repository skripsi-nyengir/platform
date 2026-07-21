import { setupWorker } from 'msw/browser'
import { createHandlers } from './handlers'
import { scenarioFromSearch } from './scenario'
import { mockState, setMockScenario } from './state'

const worker = setupWorker(...createHandlers(mockState))

export async function startBrowserMocks(): Promise<void> {
  setMockScenario(scenarioFromSearch(window.location.search))
  await worker.start({ onUnhandledRequest: 'error' })
}
