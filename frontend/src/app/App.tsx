import { RouterProvider } from 'react-router-dom'
import { AppProviders } from './AppProviders'
import { createAppRouter } from './router'

export function App() {
  return (
    <AppProviders>
      <RouterProvider router={createAppRouter()} />
    </AppProviders>
  )
}
