import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  THEME_COLOR_SCHEME_STORAGE_KEY,
  THEME_MODE_STORAGE_KEY,
} from '../theme/theme'
import { AppProviders } from './AppProviders'
import { SidebarThemeToggle } from './SidebarThemeToggle'

const darkPreferenceQuery = '(prefers-color-scheme: dark)'
const mediaListeners = new Set<(event: MediaQueryListEvent) => void>()
let systemPrefersDark = false

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

function installMatchMedia(prefersDark: boolean) {
  systemPrefersDark = prefersDark
  Object.defineProperty(window, 'matchMedia', {
    configurable: true,
    writable: true,
    value: vi.fn((query: string): MediaQueryList => ({
      matches: query === darkPreferenceQuery && systemPrefersDark,
      media: query,
      onchange: null,
      addListener: (listener) => mediaListeners.add(listener),
      removeListener: (listener) => mediaListeners.delete(listener),
      addEventListener: (_type, listener) => mediaListeners.add(listener as (event: MediaQueryListEvent) => void),
      removeEventListener: (_type, listener) => mediaListeners.delete(listener as (event: MediaQueryListEvent) => void),
      dispatchEvent: () => true,
    })),
  })
}

function changeSystemPreference(prefersDark: boolean) {
  systemPrefersDark = prefersDark
  const event = { matches: prefersDark, media: darkPreferenceQuery } as MediaQueryListEvent
  mediaListeners.forEach((listener) => listener(event))
}

function renderToggle() {
  return render(
    <AppProviders>
      <SidebarThemeToggle />
    </AppProviders>,
  )
}

beforeEach(() => {
  Object.defineProperty(window, 'localStorage', {
    configurable: true,
    value: new MemoryStorage(),
  })
  window.localStorage.clear()
  mediaListeners.clear()
  document.documentElement.removeAttribute('data-light')
  document.documentElement.removeAttribute('data-dark')
  installMatchMedia(false)
})

afterEach(() => {
  window.localStorage.clear()
  mediaListeners.clear()
  document.documentElement.removeAttribute('data-light')
  document.documentElement.removeAttribute('data-dark')
})

describe('SidebarThemeToggle', () => {
  it.each([
    { prefersDark: false, activeAttribute: 'data-light', action: 'Switch to dark theme' },
    { prefersDark: true, activeAttribute: 'data-dark', action: 'Switch to light theme' },
  ])('follows a $activeAttribute system preference without saved state', async ({
    prefersDark,
    activeAttribute,
    action,
  }) => {
    installMatchMedia(prefersDark)
    renderToggle()

    expect(await screen.findByRole('button', { name: action })).toBeEnabled()
    expect(document.documentElement).toHaveAttribute(activeAttribute, '')
    expect(window.localStorage.getItem(THEME_MODE_STORAGE_KEY)).toBeNull()
  })

  it('lets a saved explicit mode override the system preference', async () => {
    installMatchMedia(false)
    window.localStorage.setItem(THEME_MODE_STORAGE_KEY, 'dark')
    renderToggle()

    expect(await screen.findByRole('button', { name: 'Switch to light theme' })).toBeEnabled()
    expect(document.documentElement).toHaveAttribute('data-dark', '')
  })

  it('persists a binary choice across remounts and synchronizes storage changes', async () => {
    const user = userEvent.setup()
    const firstRender = renderToggle()
    await user.click(await screen.findByRole('button', { name: 'Switch to dark theme' }))

    expect(window.localStorage.getItem(THEME_MODE_STORAGE_KEY)).toBe('dark')
    expect(window.localStorage.getItem(`${THEME_COLOR_SCHEME_STORAGE_KEY}-light`)).toBeNull()
    expect(window.localStorage.getItem(`${THEME_COLOR_SCHEME_STORAGE_KEY}-dark`)).toBeNull()
    expect(await screen.findByRole('button', { name: 'Switch to light theme' })).toBeEnabled()
    expect(document.documentElement).toHaveAttribute('data-dark', '')

    firstRender.unmount()
    renderToggle()
    expect(await screen.findByRole('button', { name: 'Switch to light theme' })).toBeEnabled()

    act(() => {
      window.localStorage.setItem(THEME_MODE_STORAGE_KEY, 'light')
      window.dispatchEvent(new StorageEvent('storage', {
        key: THEME_MODE_STORAGE_KEY,
        newValue: 'light',
        oldValue: 'dark',
      }))
    })

    expect(await screen.findByRole('button', { name: 'Switch to dark theme' })).toBeEnabled()
    expect(document.documentElement).toHaveAttribute('data-light', '')

    act(() => changeSystemPreference(true))
    expect(screen.getByRole('button', { name: 'Switch to dark theme' })).toBeEnabled()

    act(() => {
      window.localStorage.removeItem(THEME_MODE_STORAGE_KEY)
      window.dispatchEvent(new StorageEvent('storage', {
        key: THEME_MODE_STORAGE_KEY,
        newValue: null,
        oldValue: 'light',
      }))
    })

    expect(await screen.findByRole('button', { name: 'Switch to light theme' })).toBeEnabled()
    expect(document.documentElement).toHaveAttribute('data-dark', '')
    expect(window.localStorage.getItem(THEME_MODE_STORAGE_KEY)).toBe('system')
  })

  it('tracks system changes only until the user makes an explicit choice', async () => {
    const user = userEvent.setup()
    renderToggle()
    expect(await screen.findByRole('button', { name: 'Switch to dark theme' })).toBeEnabled()

    act(() => changeSystemPreference(true))
    expect(await screen.findByRole('button', { name: 'Switch to light theme' })).toBeEnabled()
    expect(window.localStorage.getItem(THEME_MODE_STORAGE_KEY)).toBeNull()

    await user.click(screen.getByRole('button', { name: 'Switch to light theme' }))
    expect(window.localStorage.getItem(THEME_MODE_STORAGE_KEY)).toBe('light')

    act(() => changeSystemPreference(true))
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Switch to dark theme' })).toBeEnabled()
      expect(document.documentElement).toHaveAttribute('data-light', '')
    })
  })

  it('supports keyboard activation and exposes its action in a tooltip', async () => {
    const user = userEvent.setup()
    renderToggle()
    const toggle = await screen.findByRole('button', { name: 'Switch to dark theme' })

    await user.hover(toggle)
    expect(await screen.findByRole('tooltip', { name: 'Switch to dark theme' })).toBeVisible()

    toggle.focus()
    expect(toggle).toHaveFocus()
    await user.keyboard('{Enter}')
    expect(await screen.findByRole('button', { name: 'Switch to light theme' })).toHaveFocus()
    expect(window.localStorage.getItem(THEME_MODE_STORAGE_KEY)).toBe('dark')

    await user.keyboard(' ')
    expect(await screen.findByRole('button', { name: 'Switch to dark theme' })).toHaveFocus()
    expect(window.localStorage.getItem(THEME_MODE_STORAGE_KEY)).toBe('light')
  })

  it('stays disabled and does not write storage while the scheme is unresolved', () => {
    render(<SidebarThemeToggle />)
    const toggle = screen.getByRole('button', { name: 'Switch theme' })

    expect(toggle).toBeDisabled()
    fireEvent.click(toggle)
    expect(window.localStorage.getItem(THEME_MODE_STORAGE_KEY)).toBeNull()
  })
})
