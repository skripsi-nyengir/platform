import '@testing-library/jest-dom/vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { mockState } from '../mocks/state'
import { renderApp } from '../test/renderApp'

async function signIn(username = 'operator', password = 'operator-password') {
  const user = userEvent.setup()
  await user.type(await screen.findByLabelText(/nama pengguna/i), username)
  await user.type(screen.getByLabelText(/kata sandi/i), password)
  await user.click(screen.getByRole('button', { name: 'Masuk' }))
  return user
}

describe('login', () => {
  it('sends an unauthenticated visitor to the login page', async () => {
    renderApp('/?__scenario=unauthenticated')

    expect(
      await screen.findByRole('heading', { name: 'Anomaly Detection Platform' }),
    ).toBeVisible()
    expect(screen.getByLabelText(/nama pengguna/i)).toBeVisible()
    // The protected route must not have rendered behind the form.
    expect(screen.queryByRole('navigation', { name: 'Primary navigation' })).toBeNull()
  })

  it('lands on the route the visitor originally asked for', async () => {
    renderApp('/system-health?__scenario=unauthenticated')

    await screen.findByLabelText(/nama pengguna/i)
    await signIn()

    expect(await screen.findByRole('heading', { name: 'System Health' })).toBeVisible()
  })

  it('keeps the visitor on the form and explains a rejected credential', async () => {
    renderApp('/?__scenario=login-invalid')

    await screen.findByLabelText(/nama pengguna/i)
    await signIn('operator', 'wrong-password')

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent(/username or password is incorrect/i)
    expect(screen.getByLabelText(/nama pengguna/i)).toBeVisible()
  })

  it('reports a locked account distinctly from a rejected password', async () => {
    renderApp('/?__scenario=login-locked')

    await screen.findByLabelText(/nama pengguna/i)
    await signIn()

    expect(await screen.findByRole('alert')).toHaveTextContent(
      /too many failed sign-in attempts/i,
    )
  })

  it('submits from the keyboard alone', async () => {
    renderApp('/?__scenario=unauthenticated')

    const user = userEvent.setup()
    await user.type(await screen.findByLabelText(/nama pengguna/i), 'operator')
    await user.tab()
    await user.keyboard('operator-password{Enter}')

    expect(await screen.findByRole('heading', { name: 'Overview' })).toBeVisible()
  })

  it('keeps the submit button unavailable until both fields are filled', async () => {
    renderApp('/?__scenario=unauthenticated')

    const submit = await screen.findByRole('button', { name: 'Masuk' })
    expect(submit).toBeDisabled()

    const user = userEvent.setup()
    await user.type(screen.getByLabelText(/nama pengguna/i), 'operator')
    expect(submit).toBeDisabled()

    await user.type(screen.getByLabelText(/kata sandi/i), 'operator-password')
    expect(submit).toBeEnabled()
  })

  it('never puts the password in the accessible value of a visible field', async () => {
    renderApp('/?__scenario=unauthenticated')

    const password = await screen.findByLabelText(/kata sandi/i)
    expect(password).toHaveAttribute('type', 'password')
  })

  it('signs the visitor out and returns them to the form', async () => {
    renderApp('/')

    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: 'Sign out' }))

    expect(await screen.findByLabelText(/nama pengguna/i)).toBeVisible()
    expect(mockState.signedIn).toBe(false)
  })

  it('returns to the form when the session lapses mid-visit', async () => {
    renderApp('/system-health')
    await screen.findByRole('heading', { name: 'System Health' })

    // The server forgets the session; the next query answers 401.
    mockState.signedIn = false
    const user = userEvent.setup()
    await user.click(screen.getByRole('link', { name: 'Alerts' }))

    await waitFor(() => {
      expect(screen.getByLabelText(/nama pengguna/i)).toBeVisible()
    })
  })
})
