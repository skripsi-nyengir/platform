import { Divider, Stack, Typography } from '@mui/material'
import { tokens } from '../../theme/tokens'

export interface EdaSectionHeadingProps {
  id: string
  title: string
  supportingText: string
}

export function EdaSectionHeading({ id, title, supportingText }: EdaSectionHeadingProps) {
  return (
    <Stack spacing={1} sx={{ minWidth: 0 }}>
      <Divider sx={{ borderColor: 'divider' }} />
      <Typography
        component="h2"
        id={id}
        sx={{
          fontSize: tokens.font.size.productTitle,
          fontWeight: 700,
          lineHeight: tokens.font.lineHeight.productTitle,
        }}
      >
        {title}
      </Typography>
      <Typography variant="body2" color="text.secondary">
        {supportingText}
      </Typography>
    </Stack>
  )
}
