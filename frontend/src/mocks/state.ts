import type { AlertEvent, AlertMutationResponse } from '../contracts/alerts'
import { activeAlertSeedEvents } from './fixtures/alerts'
import type { AppMockScenario } from './scenario'
import type { ReplayJob } from '../contracts/preview'

export interface MockApiState {
  scenario: AppMockScenario
  events: AlertEvent[]
  acceptedCommands: Map<string, AlertMutationResponse>
  simActiveModelVersion: string
  replayJobs: Map<string, ReplayJob>
  edaRequestCounts: Map<string, number>
}

function scenarioSeedEvents(scenario: AppMockScenario): AlertEvent[] {
  if (scenario !== 'active-anomaly') return []
  return activeAlertSeedEvents.map((event) => Object.freeze(structuredClone(event)))
}

export const mockState: MockApiState = {
  scenario: 'normal',
  events: [],
  acceptedCommands: new Map<string, AlertMutationResponse>(),
  simActiveModelVersion: 'artifact-lstm-ae-v3',
  replayJobs: new Map<string, ReplayJob>(),
  edaRequestCounts: new Map<string, number>(),
}

export function resetMockState(scenario: AppMockScenario = 'normal'): void {
  mockState.scenario = scenario
  mockState.events = scenarioSeedEvents(scenario)
  mockState.acceptedCommands.clear()
  mockState.simActiveModelVersion = 'artifact-lstm-ae-v3'
  mockState.replayJobs.clear()
  mockState.edaRequestCounts.clear()
}

export function setMockScenario(scenario: AppMockScenario): void {
  resetMockState(scenario)
}
