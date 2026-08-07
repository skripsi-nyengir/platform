import { Navigate, createBrowserRouter, createMemoryRouter } from 'react-router-dom'
import { RequireSession } from '../features/auth/RequireSession'
import { AlertsPage } from '../pages/AlertsPage'
import { EdaPage } from '../pages/EdaPage'
import { LoginPage } from '../pages/LoginPage'
import { ModelEvaluationPage } from '../pages/ModelEvaluationPage'
import { OverviewPage } from '../pages/OverviewPage'
import { SensorDetailPage } from '../pages/SensorDetailPage'
import { SimulationPage } from '../pages/SimulationPage'
import { SystemHealthPage } from '../pages/SystemHealthPage'
import { AppShell } from './AppShell'

const routes = [
  // Outside the shell: the sidebar and its queries have nothing to show without a
  // session, and rendering them behind the login form would fire doomed requests.
  { path: '/login', element: <LoginPage /> },
  {
    element: (
      <RequireSession>
        <AppShell />
      </RequireSession>
    ),
    children: [
      { path: '/', element: <OverviewPage /> },
      { path: '/sensors/:sensorId', element: <SensorDetailPage /> },
      { path: '/alerts', element: <AlertsPage /> },
      { path: '/eda', element: <EdaPage /> },
      { path: '/model-evaluation', element: <ModelEvaluationPage /> },
      { path: '/simulation', element: <SimulationPage /> },
      { path: '/system-health', element: <SystemHealthPage /> },
      { path: '*', element: <Navigate to="/" replace /> },
    ],
  },
]

export function createAppRouter(initialEntries?: string[]) {
  return initialEntries
    ? createMemoryRouter(routes, { initialEntries })
    : createBrowserRouter(routes)
}
