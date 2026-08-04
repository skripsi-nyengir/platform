import {
  Box,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  SvgIcon,
  Tooltip,
} from '@mui/material'
import { useColorScheme } from '@mui/material/styles'
import { tokens } from '../theme/tokens'

const sunPath = 'M12 4.5a1 1 0 0 1-1-1V2a1 1 0 1 1 2 0v1.5a1 1 0 0 1-1 1Zm0 15a1 1 0 0 1 1 1V22a1 1 0 1 1-2 0v-1.5a1 1 0 0 1 1-1ZM4.5 12a1 1 0 0 1-1 1H2a1 1 0 1 1 0-2h1.5a1 1 0 0 1 1 1Zm15 0a1 1 0 0 1 1-1H22a1 1 0 1 1 0 2h-1.5a1 1 0 0 1-1-1ZM5.64 7.05 4.58 5.99a1 1 0 1 1 1.41-1.41l1.06 1.06a1 1 0 1 1-1.41 1.41Zm11.31 9.9a1 1 0 0 1 1.41 0l1.06 1.06a1 1 0 0 1-1.41 1.41l-1.06-1.06a1 1 0 0 1 0-1.41ZM7.05 16.95a1 1 0 0 1 0 1.41l-1.06 1.06a1 1 0 0 1-1.41-1.41l1.06-1.06a1 1 0 0 1 1.41 0Zm9.9-9.9a1 1 0 0 1 0-1.41l1.06-1.06a1 1 0 1 1 1.41 1.41l-1.06 1.06a1 1 0 0 1-1.41 0ZM12 7a5 5 0 1 1 0 10 5 5 0 0 1 0-10Zm0 2a3 3 0 1 0 0 6 3 3 0 0 0 0-6Z'
const moonPath = 'M20.72 15.16A8.5 8.5 0 0 1 8.84 3.28 9 9 0 1 0 20.72 15.16ZM12 21a7 7 0 0 1-6.22-10.21 10.5 10.5 0 0 0 7.43 7.43A7 7 0 0 1 12 21Z'

export function SidebarThemeToggle() {
  const { colorScheme, setMode } = useColorScheme()
  const resolved = colorScheme === 'light' || colorScheme === 'dark'
  const targetMode = colorScheme === 'dark' ? 'light' : 'dark'
  const label = resolved ? `Switch to ${targetMode} theme` : 'Switch theme'

  return (
    <Tooltip title={label} placement="right">
      <Box component="span" sx={{ display: 'block', width: '100%' }}>
        <ListItemButton
          component="button"
          type="button"
          aria-label={label}
          disabled={!resolved}
          onClick={() => {
            if (resolved) setMode(targetMode)
          }}
          sx={{
            justifyContent: { xs: 'center', sm: 'flex-start' },
            pl: { xs: 0, sm: 4 },
            pr: { xs: `${tokens.size.activeRule}px`, sm: 4 },
            width: '100%',
          }}
        >
          <ListItemIcon sx={{ color: 'inherit', minWidth: { xs: 0, sm: 40 } }}>
            <SvgIcon fontSize="small">
              <path d={targetMode === 'light' ? sunPath : moonPath} />
            </SvgIcon>
          </ListItemIcon>
          <ListItemText primary={label} sx={{ display: { xs: 'none', sm: 'block' } }} />
        </ListItemButton>
      </Box>
    </Tooltip>
  )
}
