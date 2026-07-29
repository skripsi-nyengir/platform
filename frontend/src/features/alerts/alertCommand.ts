import type { AlertCommandRequest } from '../../contracts/common'
import { randomId } from '../../lib/id'

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
    command_id: randomId(),
  }
  if (note !== undefined) body.note = note
  return { alertId, action, body }
}
