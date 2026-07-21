import { Stack, Typography } from '@mui/material'
import { useId } from 'react'

export interface EmptyStateProps {
  title: string
  detail: string
}

export function EmptyState({ title, detail }: EmptyStateProps) {
  const titleId = useId()
  const detailId = useId()

  return (
    <Stack
      role="status"
      aria-labelledby={titleId}
      aria-describedby={detailId}
      spacing={1}
    >
      <Typography id={titleId} variant="h3">
        {title}
      </Typography>
      <Typography id={detailId} variant="body2" color="text.secondary">
        {detail}
      </Typography>
    </Stack>
  )
}
