import { Navigate, createBrowserRouter, createMemoryRouter } from 'react-router-dom'
import { AlertsPage } from '../pages/AlertsPage'
import { EdaPage } from '../pages/EdaPage'
import { ModelEvaluationPage } from '../pages/ModelEvaluationPage'
import { OverviewPage } from '../pages/OverviewPage'
import { SensorDetailPage } from '../pages/SensorDetailPage'
import { SimulationPage } from '../pages/SimulationPage'
import { SystemHealthPage } from '../pages/SystemHealthPage'
import { AppShell } from './AppShell'

const routes = [
  {
    element: <AppShell />,
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
