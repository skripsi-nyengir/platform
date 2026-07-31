import { render, type RenderResult } from '@testing-library/react'
import { RouterProvider } from 'react-router-dom'
import { AppProviders } from '../app/AppProviders'
import { createAppRouter } from '../app/router'
import { scenarioFromSearch } from '../mocks/scenario'
import { setMockScenario } from '../mocks/state'

export function renderApp(route: string): RenderResult {
  setMockScenario(scenarioFromSearch(new URL(route, 'http://localhost').search))
  return render(
    <AppProviders>
      <RouterProvider router={createAppRouter([route])} />
    </AppProviders>,
  )
}
