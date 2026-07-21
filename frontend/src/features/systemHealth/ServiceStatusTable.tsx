import {
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
} from '@mui/material'
import type { SystemServiceStatus } from '../../contracts/systemHealth'
import { tokens } from '../../theme/tokens'

const technicalTextSx = {
  fontFamily: tokens.font.data,
  fontVariantNumeric: 'tabular-nums',
  overflowWrap: 'anywhere',
} as const

export interface ServiceStatusTableProps {
  services: readonly SystemServiceStatus[]
}

export function ServiceStatusTable({ services }: ServiceStatusTableProps) {
  return (
    <Paper component="section" variant="outlined" sx={{ overflow: 'hidden' }}>
      <TableContainer sx={{ overflowX: 'auto' }}>
        <Table
          size="small"
          sx={{
            width: '100%',
            minWidth: 720,
            tableLayout: 'fixed',
            '& caption': {
              p: 2,
              color: 'text.primary',
              fontWeight: 700,
              textAlign: 'left',
            },
          }}
        >
          <caption>Service liveness and readiness</caption>
          <TableHead>
            <TableRow>
              <TableCell>Service</TableCell>
              <TableCell>Liveness</TableCell>
              <TableCell>Readiness</TableCell>
              <TableCell>Checked at</TableCell>
              <TableCell>Detail</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {services.map((service) => (
              <TableRow key={service.name}>
                <TableCell component="th" scope="row" sx={technicalTextSx}>{service.name}</TableCell>
                <TableCell sx={{ overflowWrap: 'anywhere' }}>{service.liveness}</TableCell>
                <TableCell sx={{ overflowWrap: 'anywhere' }}>{service.readiness}</TableCell>
                <TableCell sx={technicalTextSx}>{service.checked_at}</TableCell>
                <TableCell sx={{ overflowWrap: 'anywhere' }}>{service.detail}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    </Paper>
  )
}
