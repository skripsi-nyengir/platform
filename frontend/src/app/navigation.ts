export interface NavigationItem {
  path: '/' | '/sensors/b02f3872-ruang-produksi' | '/alerts' | '/eda' | '/model-evaluation' | '/simulation' | '/system-health'
  label: string
  group: 'operations' | 'analysis' | 'system'
}

export const navigationItems: readonly NavigationItem[] = [
  { path: '/', label: 'Overview', group: 'operations' },
  { path: '/sensors/b02f3872-ruang-produksi', label: 'Sensor', group: 'operations' },
  { path: '/alerts', label: 'Alerts', group: 'operations' },
  // ponytail: EDA route/page kept for direct-URL access but hidden from the sidebar (out of thesis scope).
  { path: '/model-evaluation', label: 'Model Evaluation', group: 'analysis' },
  { path: '/simulation', label: 'Simulation', group: 'analysis' },
  { path: '/system-health', label: 'System Health', group: 'system' },
]
