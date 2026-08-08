import type { AlertEvent, AlertMutationResponse } from '../contracts/alerts'
import { activeAlertSeedEvents } from './fixtures/alerts'
import type { AppMockScenario } from './scenario'
import type { ReplayJob } from '../contracts/preview'
import type { SlackSettingsResponse, TestSlackSettingsRequest } from '../contracts/slackSettings'
import { slackSettingsResponse } from './fixtures/slackSettings'

export interface MockApiState {
  scenario: AppMockScenario
  events: AlertEvent[]
  acceptedCommands: Map<string, AlertMutationResponse>
  simActiveModelVersion: string
  replayJobs: Map<string, ReplayJob>
  edaRequestCounts: Map<string, number>
  signedIn: boolean
  slackSettings: SlackSettingsResponse
  slackTestRequests: TestSlackSettingsRequest[]
}

function scenarioSeedEvents(scenario: AppMockScenario): AlertEvent[] {
  if (scenario !== 'active-anomaly') return []
  return activeAlertSeedEvents.map((event) => Object.freeze(structuredClone(event)))
}

// Every route now sits behind the session guard. Starting signed in keeps existing
// page tests exercising their routes instead of all landing on the login form; the
// auth scenarios opt out explicitly.
const signedOutScenarios = new Set<AppMockScenario>([
  'unauthenticated',
  'login-invalid',
  'login-locked',
])

function scenarioStartsSignedIn(scenario: AppMockScenario): boolean {
  return !signedOutScenarios.has(scenario)
}

export const mockState: MockApiState = {
  scenario: 'normal',
  events: [],
  acceptedCommands: new Map<string, AlertMutationResponse>(),
  simActiveModelVersion: 'artifact-lstm-ae-v3',
  replayJobs: new Map<string, ReplayJob>(),
  edaRequestCounts: new Map<string, number>(),
  signedIn: true,
  slackSettings: structuredClone(slackSettingsResponse),
  slackTestRequests: [],
}

export function resetMockState(scenario: AppMockScenario = 'normal'): void {
  mockState.scenario = scenario
  mockState.events = scenarioSeedEvents(scenario)
  mockState.acceptedCommands.clear()
  mockState.simActiveModelVersion = 'artifact-lstm-ae-v3'
  mockState.replayJobs.clear()
  mockState.edaRequestCounts.clear()
  mockState.signedIn = scenarioStartsSignedIn(scenario)
  mockState.slackSettings = structuredClone(slackSettingsResponse)
  mockState.slackTestRequests = []
}

export function setMockScenario(scenario: AppMockScenario): void {
  resetMockState(scenario)
}
