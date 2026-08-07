import { Alert, Box, Button, Paper, Stack, TextField, Typography } from '@mui/material'
import { useState } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { ApiError } from '../api/errors'
import { useLogin, useSessionState } from '../features/auth/useSession'
import { tokens } from '../theme/tokens'

type LoginLocationState = { from?: string; reason?: string }

function failureMessage(error: unknown): string {
  if (error instanceof ApiError) {
    // The backend already words 401 and 429 for a reader; anything else is a
    // transport problem the detail text would not explain.
    if (error.kind === 'problem') return error.message
    if (error.kind === 'timeout') return 'Server tidak merespons. Coba lagi.'
    return 'Tidak dapat menghubungi server.'
  }
  return 'Terjadi kesalahan yang tidak terduga.'
}

export function LoginPage() {
  const location = useLocation()
  const state = (location.state ?? {}) as LoginLocationState
  const { session } = useSessionState()
  const signIn = useLogin()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')

  if (session) {
    return <Navigate to={state.from ?? '/'} replace />
  }

  const message = signIn.isError ? failureMessage(signIn.error) : state.reason

  return (
    <Box
      sx={{
        alignItems: 'center',
        display: 'flex',
        justifyContent: 'center',
        minHeight: '100vh',
        px: 3,
        py: 6,
      }}
    >
      <Paper
        variant="outlined"
        sx={{ maxWidth: 420, p: { xs: 4, sm: 6 }, width: '100%' }}
      >
        <Stack spacing={4}>
          <Stack spacing={0.5}>
            <Typography variant="h1" sx={{ fontSize: tokens.font.size.productTitle }}>
              Anomaly Detection Platform
            </Typography>
            <Typography color="text.secondary" variant="body2">
              Masuk untuk melihat telemetri, hasil inferensi, dan alert.
            </Typography>
          </Stack>

          {message ? (
            <Alert severity="error" role="alert">
              {message}
            </Alert>
          ) : null}

          <form
            noValidate
            onSubmit={(event) => {
              event.preventDefault()
              signIn.mutate({ username, password })
            }}
          >
            <Stack spacing={3}>
              <TextField
                label="Nama pengguna"
                name="username"
                autoComplete="username"
                autoFocus
                required
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                slotProps={{ htmlInput: { maxLength: 200 } }}
              />
              <TextField
                label="Kata sandi"
                name="password"
                type="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                slotProps={{ htmlInput: { maxLength: 1024 } }}
              />
              <Button
                type="submit"
                variant="contained"
                size="large"
                disabled={signIn.isPending || !username || !password}
              >
                {signIn.isPending ? 'Memproses…' : 'Masuk'}
              </Button>
            </Stack>
          </form>
        </Stack>
      </Paper>
    </Box>
  )
}
