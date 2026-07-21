import type { AlertEvent, AlertMutationResponse } from '../contracts/alerts'
import { activeAlertSeedEvents } from './fixtures/alerts'
import type { MockScenario } from './scenario'

export interface MockApiState {
  scenario: MockScenario
  events: AlertEvent[]
  acceptedCommands: Map<string, AlertMutationResponse>
}

function scenarioSeedEvents(scenario: MockScenario): AlertEvent[] {
  if (scenario !== 'active-anomaly') return []
  return activeAlertSeedEvents.map((event) => Object.freeze(structuredClone(event)))
}

export const mockState: MockApiState = {
  scenario: 'normal',
  events: [],
  acceptedCommands: new Map<string, AlertMutationResponse>(),
}

export function resetMockState(scenario: MockScenario = 'normal'): void {
  mockState.scenario = scenario
  mockState.events = scenarioSeedEvents(scenario)
  mockState.acceptedCommands.clear()
}

export function setMockScenario(scenario: MockScenario): void {
  resetMockState(scenario)
}
