import { Box, CircularProgress } from '@mui/material'
import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { useSessionState } from './useSession'

export function RequireSession({ children }: { children: ReactNode }) {
  const { session, isPending, error, rejected } = useSessionState()
  const location = useLocation()

  if (isPending) {
    return (
      <Box
        role="status"
        aria-label="Checking your session"
        sx={{ alignItems: 'center', display: 'flex', justifyContent: 'center', minHeight: '100vh' }}
      >
        <CircularProgress />
      </Box>
    )
  }

  if (!session) {
    // Anything other than a clean 401 is still a reason to send the visitor to the
    // login page: without a session there is nothing to show, and the login page
    // surfaces the error rather than leaving a blank shell behind.
    const reason = rejected ? undefined : error?.message
    return (
      <Navigate
        to="/login"
        replace
        state={{ from: location.pathname + location.search, reason }}
      />
    )
  }

  return <>{children}</>
}
