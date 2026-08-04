import {
  Box,
  Drawer,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  SvgIcon,
  Tooltip,
  Typography,
} from '@mui/material'
import { useEffect, useState } from 'react'
import { Link as RouterLink, Outlet, useLocation } from 'react-router-dom'
import { tokens } from '../theme/tokens'
import { navigationItems, type NavigationItem } from './navigation'
import { SidebarThemeToggle } from './SidebarThemeToggle'

const routeIconPaths: Record<NavigationItem['path'], string> = {
  '/': 'M3 13h8V3H3v10Zm0 8h8v-6H3v6Zm10 0h8V11h-8v10Zm0-18v6h8V3h-8Z',
  '/sensors/b02f3872-ruang-produksi': 'M7.76 16.24A5.98 5.98 0 0 1 6 12c0-1.66.67-3.16 1.76-4.24l1.41 1.41A4 4 0 0 0 8 12c0 1.1.45 2.1 1.17 2.83l-1.41 1.41Zm8.48 0-1.41-1.41A4 4 0 0 0 16 12c0-1.1-.45-2.1-1.17-2.83l1.41-1.41A5.98 5.98 0 0 1 18 12c0 1.66-.67 3.16-1.76 4.24ZM4.93 19.07A9.97 9.97 0 0 1 2 12c0-2.76 1.12-5.26 2.93-7.07l1.42 1.42A7.96 7.96 0 0 0 4 12c0 2.21.9 4.21 2.35 5.65l-1.42 1.42Zm14.14 0-1.42-1.42A7.96 7.96 0 0 0 20 12c0-2.21-.9-4.21-2.35-5.65l1.42-1.42A9.97 9.97 0 0 1 22 12c0 2.76-1.12 5.26-2.93 7.07ZM12 14a2 2 0 1 1 0-4 2 2 0 0 1 0 4Z',
  '/alerts': 'M12 22a2.5 2.5 0 0 0 2.45-2h-4.9A2.5 2.5 0 0 0 12 22Zm6-6v-5a6 6 0 0 0-5-5.91V4a1 1 0 1 0-2 0v1.09A6 6 0 0 0 6 11v5l-2 2v1h16v-1l-2-2Z',
  '/eda': 'M3 3v18h18v-2H5V3H3Zm4 12h3v2H7v-2Zm0-4h7v2H7v-2Zm0-4h11v2H7V7Zm9 4h2v6h-2v-6Zm-4 3h2v3h-2v-3Z',
  '/model-evaluation': 'M4 3h16a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-5l-3 3-3-3H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2Zm2 12 3-4 3 2 4-6 2 1-5 8-3-2-2 3-2-2Z',
  '/simulation': 'M9 2v2h1v5.59L4.59 15A4 4 0 0 0 8 21h8a4 4 0 0 0 3.41-6L14 9.59V4h1V2H9Zm3 9.41V4h2v7.41L15 13H9l1-1.59V4h2v7.41Z',
  '/system-health': 'M3 12h4l2-6 4 12 2-6h6v2h-4.5L13 22 9 10l-.5 4H3v-2Z',
}

export const SIDEBAR_COLLAPSED_STORAGE_KEY = 'adp-sidebar-collapsed'

const collapseIconPath = 'M15.41 7.41 14 6l-6 6 6 6 1.41-1.41L10.83 12l4.58-4.59Z'
const expandIconPath = 'm8.59 16.59L13.17 12 8.59 7.41 10 6l6 6-6 6-1.41-1.41Z'

function readCollapsedSidebar(): boolean {
  try {
    return window.localStorage?.getItem(SIDEBAR_COLLAPSED_STORAGE_KEY) === 'true'
  } catch {
    return false
  }
}

function persistCollapsedSidebar(collapsed: boolean) {
  try {
    window.localStorage?.setItem(SIDEBAR_COLLAPSED_STORAGE_KEY, String(collapsed))
  } catch {
    // Storage may be unavailable in privacy-restricted browsing contexts.
  }
}

export function AppShell() {
  const { pathname } = useLocation()
  const [collapsed, setCollapsed] = useState(() => typeof window !== 'undefined' && readCollapsedSidebar())
  const sidebarWidth = { xs: tokens.size.sidebarCompact, sm: collapsed ? tokens.size.sidebarCompact : tokens.size.sidebar }
  const collapseLabel = collapsed ? 'Expand sidebar' : 'Collapse sidebar'

  useEffect(() => {
    persistCollapsedSidebar(collapsed)
  }, [collapsed])

  return (
    <Box sx={{ display: 'flex', minHeight: '100vh' }}>
      <Drawer
        variant="permanent"
        data-sidebar-state={collapsed ? 'collapsed' : 'expanded'}
        sx={{
          boxSizing: 'border-box',
          transition: (theme) => theme.transitions.create('width'),
          width: sidebarWidth,
          flexShrink: 0,
          '& .MuiDrawer-paper': {
            boxSizing: 'border-box',
            borderRight: (theme) => `${tokens.size.rule}px solid ${theme.palette.app.sidebarDivider}`,
            display: 'flex',
            flexDirection: 'column',
            overflowX: 'hidden',
            transition: (theme) => theme.transitions.create('width'),
            width: sidebarWidth,
          },
        }}
      >
        <Box
          sx={{
            px: { xs: 0, sm: collapsed ? 0 : 4 },
            pb: 4,
            pt: 5,
            textAlign: { xs: 'center', sm: collapsed ? 'center' : 'left' },
          }}
        >
          <Typography
            component="div"
            sx={{
              display: { xs: 'block', sm: collapsed ? 'block' : 'none' },
              fontSize: tokens.font.size.productTitle,
              fontWeight: 700,
              lineHeight: tokens.font.lineHeight.productTitle,
            }}
          >
            ADP
          </Typography>
          <Typography
            component="div"
            sx={{
              display: { xs: 'none', sm: collapsed ? 'none' : 'block' },
              fontSize: tokens.font.size.productTitle,
              fontWeight: 700,
              lineHeight: tokens.font.lineHeight.productTitle,
            }}
          >
            Anomaly Detection Platform
          </Typography>
          <Typography
            component="div"
            color="text.secondary"
            variant="caption"
            sx={{ display: { xs: 'none', sm: collapsed ? 'none' : 'block' }, mt: 0.5 }}
          >
            IoT sensor operations
          </Typography>
        </Box>
        <Box sx={{ display: { xs: 'none', sm: 'block' }, pb: 2 }}>
          <Tooltip title={collapseLabel} placement="right">
            <ListItemButton
              component="button"
              type="button"
              aria-expanded={!collapsed}
              aria-label={collapseLabel}
              onClick={() => setCollapsed((value) => !value)}
              sx={{
                justifyContent: collapsed ? 'center' : 'flex-start',
                pl: collapsed ? 0 : 4,
                pr: collapsed ? 0 : 4,
              }}
            >
              <ListItemIcon sx={{ color: 'inherit', minWidth: collapsed ? 0 : 40 }}>
                <SvgIcon fontSize="small">
                  <path d={collapsed ? expandIconPath : collapseIconPath} />
                </SvgIcon>
              </ListItemIcon>
              <ListItemText primary={collapseLabel} sx={{ display: collapsed ? 'none' : 'block' }} />
            </ListItemButton>
          </Tooltip>
        </Box>
        <Box component="nav" aria-label="Primary navigation" sx={{ flexGrow: 1, pb: 4 }}>
          <List sx={{ py: 0 }}>
            {navigationItems.map((item) => {
              const selected = item.path === '/sensors/b02f3872-ruang-produksi'
                ? pathname.startsWith('/sensors/')
                : pathname === item.path

              return (
                <ListItemButton
                  key={item.path}
                  component={RouterLink}
                  to={item.path}
                  aria-label={item.label}
                  aria-current={selected ? 'page' : undefined}
                  className={selected ? 'active' : undefined}
                  sx={{
                    justifyContent: { xs: 'center', sm: collapsed ? 'center' : 'flex-start' },
                    pl: { xs: 0, sm: collapsed ? 0 : 4 },
                    pr: { xs: `${tokens.size.activeRule}px`, sm: collapsed ? 0 : 4 },
                  }}
                >
                  <ListItemIcon sx={{ color: 'inherit', minWidth: { xs: 0, sm: collapsed ? 0 : 40 } }}>
                    <SvgIcon fontSize="small">
                      <path d={routeIconPaths[item.path]} />
                    </SvgIcon>
                  </ListItemIcon>
                  <ListItemText primary={item.label} sx={{ display: { xs: 'none', sm: collapsed ? 'none' : 'block' } }} />
                </ListItemButton>
              )
            })}
          </List>
        </Box>
        <Box component="footer" sx={{ mt: 'auto', pb: 4 }}>
          <SidebarThemeToggle compact={collapsed} />
        </Box>
      </Drawer>
      <Box
        component="main"
        sx={{
          flexGrow: 1,
          minWidth: 0,
          px: { xs: 3, md: 6, xl: 8 },
          py: { xs: 4, md: 6 },
        }}
      >
        <Box sx={{ width: '100%', maxWidth: tokens.size.routeCanvas, minWidth: 0, mx: 'auto' }}>
          <Outlet />
        </Box>
      </Box>
    </Box>
  )
}
