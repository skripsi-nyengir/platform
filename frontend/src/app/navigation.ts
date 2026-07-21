export interface NavigationItem {
  path: '/' | '/sensors/n1' | '/alerts' | '/eda' | '/model-evaluation' | '/system-health'
  label: string
  group: 'operations' | 'analysis' | 'system'
}

export const navigationItems: readonly NavigationItem[] = [
  { path: '/', label: 'Overview', group: 'operations' },
  { path: '/sensors/n1', label: 'Sensors', group: 'operations' },
  { path: '/alerts', label: 'Alerts', group: 'operations' },
  { path: '/eda', label: 'EDA', group: 'analysis' },
  { path: '/model-evaluation', label: 'Model Evaluation', group: 'analysis' },
  { path: '/system-health', label: 'System Health', group: 'system' },
]
