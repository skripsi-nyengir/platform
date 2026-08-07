import { ThemeProvider } from '@mui/material/styles'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { theme } from '../theme/theme'
import { AppShell, SIDEBAR_COLLAPSED_STORAGE_KEY } from './AppShell'

class MemoryStorage implements Storage {
  readonly #values = new Map<string, string>()

  get length() {
    return this.#values.size
  }

  clear() {
    this.#values.clear()
  }

  getItem(key: string) {
    return this.#values.get(key) ?? null
  }

  key(index: number) {
    return [...this.#values.keys()][index] ?? null
  }

  removeItem(key: string) {
    this.#values.delete(key)
  }

  setItem(key: string, value: string) {
    this.#values.set(key, String(value))
  }
}

function renderShell() {
  // The sidebar footer now holds a sign-out action, so the shell needs a query
  // client even when the test only exercises collapse behaviour.
  const queryClient = new QueryClient()
  return render(
    <QueryClientProvider client={queryClient}>
      <ThemeProvider theme={theme} defaultMode="dark" noSsr>
        <MemoryRouter initialEntries={['/']}>
          <Routes>
            <Route element={<AppShell />}>
              <Route index element={<div>Overview content</div>} />
            </Route>
          </Routes>
        </MemoryRouter>
      </ThemeProvider>
    </QueryClientProvider>,
  )
}

describe('AppShell sidebar collapse', () => {
  beforeEach(() => {
    Object.defineProperty(window, 'localStorage', {
      configurable: true,
      value: new MemoryStorage(),
    })
  })

  afterEach(() => {
    window.localStorage.clear()
  })

  it('collapses to the compact rail and persists the choice across remounts', async () => {
    const user = userEvent.setup()
    const firstRender = renderShell()

    const collapse = screen.getByRole('button', { name: 'Collapse sidebar' })
    expect(collapse).toHaveAttribute('aria-expanded', 'true')
    await user.click(collapse)

    expect(screen.getByRole('button', { name: 'Expand sidebar' })).toHaveAttribute('aria-expanded', 'false')
    expect(window.localStorage.getItem(SIDEBAR_COLLAPSED_STORAGE_KEY)).toBe('true')
    expect(document.querySelector('[data-sidebar-state]')).toHaveAttribute('data-sidebar-state', 'collapsed')

    firstRender.unmount()
    renderShell()

    expect(screen.getByRole('button', { name: 'Expand sidebar' })).toBeVisible()
    expect(screen.getByRole('link', { name: 'Overview' })).toBeVisible()
  })
})
