import type { ProblemDetails } from '../contracts/common'

export type ApiErrorKind = 'problem' | 'schema' | 'network' | 'timeout'

export class ApiError extends Error {
  readonly kind: ApiErrorKind
  readonly status?: number
  readonly requestId?: string
  readonly problem?: ProblemDetails

  constructor(
    kind: ApiErrorKind,
    message: string,
    status?: number,
    requestId?: string,
    problem?: ProblemDetails,
  ) {
    super(message)
    this.name = 'ApiError'
    this.kind = kind
    this.status = status
    this.requestId = requestId
    this.problem = problem
  }
}
