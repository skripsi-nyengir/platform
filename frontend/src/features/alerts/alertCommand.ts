import type { AlertCommandRequest } from '../../contracts/common'

export interface AlertLifecycleCommand {
  alertId: string
  action: 'acknowledge' | 'resolve'
  body: AlertCommandRequest
}

export function createAlertLifecycleCommand(
  alertId: string,
  action: 'acknowledge' | 'resolve',
  note?: string,
): AlertLifecycleCommand {
  const body: AlertCommandRequest = {
    command_id: crypto.randomUUID(),
  }
  if (note !== undefined) body.note = note
  return { alertId, action, body }
}
