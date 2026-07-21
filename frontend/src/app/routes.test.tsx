import { describe, expect, it } from 'vitest'
import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { navigationItems } from './navigation'
import { renderApp } from '../test/renderApp'
import { tokens } from '../theme/tokens'

const routes = [
  ['/', 'Overview'],
  ['/sensors/n4', 'Sensor Detail & History'],
  ['/alerts', 'Alerts'],
  ['/eda', 'EDA'],
  ['/model-evaluation', 'Model Evaluation'],
  ['/system-health', 'System Health'],
] as const

describe('application routes', () => {
  it.each(routes)('renders %s as %s', (path, heading) => {
    renderApp(path)
    expect(screen.getByRole('heading', { name: heading })).toBeVisible()
  })

  it('redirects an unknown path to Overview', () => {
    renderApp('/not-a-route')
    expect(screen.getByRole('heading', { name: 'Overview' })).toBeVisible()
  })

  it('renders all six approved sidebar entries as one ordered navigation list', () => {
    renderApp('/')
    expect(navigationItems).toHaveLength(6)
    const navigation = screen.getByRole('navigation', { name: 'Primary navigation' })
    expect(screen.getByText('ADP')).toBeVisible()
    const productTitle = screen.getByText('Anomaly Detection Platform')
    expect(productTitle).toBeInTheDocument()
    expect(productTitle.tagName).toBe('DIV')
    expect(productTitle).toHaveStyle({
      fontSize: tokens.font.size.productTitle,
      fontWeight: '700',
      lineHeight: tokens.font.lineHeight.productTitle,
    })
    expect(screen.queryByRole('heading', { name: 'Anomaly Detection Platform' })).not.toBeInTheDocument()
    expect(screen.getByText('IoT sensor operations')).toBeInTheDocument()
    expect(within(navigation).getByRole('link', { name: 'Overview' })).toHaveAttribute('href', '/')
    expect(within(navigation).getByRole('link', { name: 'Sensors' })).toHaveAttribute('href', '/sensors/n1')
    expect(within(navigation).getByRole('link', { name: 'Alerts' })).toHaveAttribute('href', '/alerts')
    expect(within(navigation).getByRole('link', { name: 'EDA' })).toHaveAttribute('href', '/eda')
    expect(within(navigation).getByRole('link', { name: 'Model Evaluation' })).toHaveAttribute(
      'href',
      '/model-evaluation',
    )
    expect(within(navigation).getByRole('link', { name: 'System Health' })).toHaveAttribute(
      'href',
      '/system-health',
    )
    for (const item of navigationItems) {
      expect(within(navigation).getByRole('link', { name: item.label })).toHaveAttribute(
        'aria-label',
        item.label,
      )
    }
    expect(within(navigation).getAllByRole('link').map((link) => link.textContent)).toEqual(
      navigationItems.map((item) => item.label),
    )
    expect(navigation.querySelectorAll('.MuiList-root')).toHaveLength(1)
    expect(within(navigation).queryByText('Operations')).not.toBeInTheDocument()
    expect(within(navigation).queryByText('Analysis')).not.toBeInTheDocument()
    expect(within(navigation).queryByText('System')).not.toBeInTheDocument()
    const drawerRoot = navigation.closest('.MuiDrawer-root')
    if (!(drawerRoot instanceof HTMLElement)) throw new Error('Navigation has no Drawer root')
    expect(drawerRoot).toHaveStyle({
      backgroundColor: tokens.color.paper,
      borderRight: `${tokens.size.rule}px solid ${tokens.color.ruleStrong}`,
      boxSizing: 'border-box',
    })
    const icons = navigation.querySelectorAll('.MuiSvgIcon-root')
    expect(icons).toHaveLength(6)
    for (const icon of icons) expect(icon).toHaveAttribute('aria-hidden', 'true')
  })

  it('marks and keyboard-focuses the active destination while exposing a bounded route canvas', async () => {
    renderApp('/')
    const navigation = screen.getByRole('navigation', { name: 'Primary navigation' })
    const activeLink = within(navigation).getByRole('link', { name: 'Overview' })
    expect(activeLink).toHaveAttribute(
      'aria-current',
      'page',
    )
    expect(activeLink).toHaveClass('active')
    await userEvent.tab()
    expect(activeLink).toHaveFocus()

    const main = screen.getByRole('main')
    expect(main).toHaveStyle({ minWidth: '0px' })
    const routeCanvas = main.firstElementChild
    if (!(routeCanvas instanceof HTMLElement)) throw new Error('Route canvas was not rendered')
    expect(routeCanvas).toHaveStyle({
      width: '100%',
      maxWidth: '1600px',
      minWidth: '0px',
      marginLeft: 'auto',
      marginRight: 'auto',
    })
  })

  it('keeps the Sensors destination active for every sensor detail route', () => {
    renderApp('/sensors/n4')
    const navigation = screen.getByRole('navigation', { name: 'Primary navigation' })
    const activeLink = within(navigation).getByRole('link', { name: 'Sensors' })

    expect(activeLink).toHaveAttribute('href', '/sensors/n1')
    expect(activeLink).toHaveAttribute('aria-current', 'page')
    expect(activeLink).toHaveClass('active')
  })
})
