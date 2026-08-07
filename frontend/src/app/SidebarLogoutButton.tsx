import {
  Box,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  SvgIcon,
  Tooltip,
} from '@mui/material'
import { useNavigate } from 'react-router-dom'
import { useLogout } from '../features/auth/useSession'
import { tokens } from '../theme/tokens'

const logoutIconPath =
  'M10 17v-2H5V5h5V3H3v16h7v-2Zm4.59-1.41L16 17l5-5-5-5-1.41 1.41L17.17 11H9v2h8.17l-2.58 2.59Z'

export function SidebarLogoutButton({ compact = false }: { compact?: boolean }) {
  const navigate = useNavigate()
  // Navigating explicitly rather than waiting for the route guard to notice: the
  // cache has just been cleared, so leaving it to a refetch would show a spinner
  // over a shell the visitor has already left.
  const signOut = useLogout(() => void navigate('/login', { replace: true }))
  const label = signOut.isPending ? 'Signing out' : 'Sign out'

  return (
    <Tooltip title={label} placement="right">
      <Box component="span" sx={{ display: 'block', width: '100%' }}>
        <ListItemButton
          component="button"
          type="button"
          aria-label={label}
          disabled={signOut.isPending}
          onClick={() => signOut.mutate()}
          sx={{
            justifyContent: { xs: 'center', sm: compact ? 'center' : 'flex-start' },
            pl: { xs: 0, sm: compact ? 0 : 4 },
            pr: { xs: `${tokens.size.activeRule}px`, sm: compact ? 0 : 4 },
            width: '100%',
          }}
        >
          <ListItemIcon sx={{ color: 'inherit', minWidth: { xs: 0, sm: compact ? 0 : 40 } }}>
            <SvgIcon fontSize="small">
              <path d={logoutIconPath} />
            </SvgIcon>
          </ListItemIcon>
          <ListItemText
            primary={label}
            sx={{ display: { xs: 'none', sm: compact ? 'none' : 'block' } }}
          />
        </ListItemButton>
      </Box>
    </Tooltip>
  )
}
