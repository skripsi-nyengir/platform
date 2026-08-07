import { render, type RenderResult } from '@testing-library/react'
import { RouterProvider } from 'react-router-dom'
import { AppProviders } from '../app/AppProviders'
import { queryClient } from '../app/queryClient'
import { createAppRouter } from '../app/router'
import { sessionQueryKey } from '../features/auth/useSession'
import { scenarioFromSearch } from '../mocks/scenario'
import { mockState, setMockScenario } from '../mocks/state'

export function renderApp(route: string): RenderResult {
  setMockScenario(scenarioFromSearch(new URL(route, 'http://localhost').search))

  // Stand in for a visitor arriving with a cookie the server still honours. Without
  // it every route would spend its first render inside the session guard's spinner,
  // and page tests that read the DOM synchronously after renderApp would see nothing.
  // Signed-out scenarios deliberately skip this so the guard still redirects them.
  if (mockState.signedIn) {
    queryClient.setQueryData(sessionQueryKey, {
      request_id: 'req_seeded_session',
      username: 'operator',
      display_name: 'Operator',
      expires_at: '2026-08-08T00:00:00Z',
    })
  }

  return render(
    <AppProviders>
      <RouterProvider router={createAppRouter([route])} />
    </AppProviders>,
  )
}
