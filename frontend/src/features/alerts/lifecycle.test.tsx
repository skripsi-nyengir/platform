import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { AlertLifecycleActions } from '../alerts-ui/AlertLifecycleActions'
import { activeDetectedAlert } from '../../mocks/fixtures/alerts'
import { AppProviders } from '../../app/AppProviders'

describe('alert lifecycle controls', () => {
  it('keeps the active action visible and full-width-capable', () => {
    render(<AppProviders><AlertLifecycleActions alert={activeDetectedAlert} /></AppProviders>)
    expect(screen.getByRole('button', { name: 'Acknowledge alert' })).toBeVisible()
  })
})
