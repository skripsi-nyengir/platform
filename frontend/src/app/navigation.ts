export interface NavigationItem {
  path: '/' | '/sensors/b02f3872-ruang-produksi' | '/alerts' | '/eda' | '/model-evaluation' | '/simulation' | '/system-health' | '/settings/slack'
  label: string
  group: 'operations' | 'analysis' | 'system'
}

export const navigationItems: readonly NavigationItem[] = [
  { path: '/', label: 'Overview', group: 'operations' },
  { path: '/sensors/b02f3872-ruang-produksi', label: 'Sensor', group: 'operations' },
  { path: '/alerts', label: 'Alerts', group: 'operations' },
  // ponytail: EDA route/page kept for direct-URL access but hidden from the sidebar (out of thesis scope).
  { path: '/model-evaluation', label: 'Model Evaluation', group: 'analysis' },
  // Simulation stays available by direct URL but is intentionally hidden from the sidebar.
  { path: '/system-health', label: 'System Health', group: 'system' },
  { path: '/settings/slack', label: 'Slack', group: 'system' },
]
