import { Skeleton, Stack, Typography } from '@mui/material'

export interface PanelSkeletonProps {
  label: string
}

export function PanelSkeleton({ label }: PanelSkeletonProps) {
  return (
    <Stack role="status" aria-label={label} aria-busy="true" spacing={1}>
      <Typography variant="body2">{label}</Typography>
      <Skeleton animation={false} />
    </Stack>
  )
}
