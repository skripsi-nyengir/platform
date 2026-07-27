import { describe, expect, it } from 'vitest'
import { screen } from '@testing-library/react'
import { renderApp } from '../test/renderApp'

describe('SystemHealthPage', () => {
  it('shows separate preview and artifact readiness states', async () => {
    renderApp('/system-health')
    expect(await screen.findByText('Preview worker')).toBeVisible()
    expect(screen.getByText('Artifact asli')).toBeVisible()
  })
})
