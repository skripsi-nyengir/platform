import { Box, Paper, Stack, Typography } from '@mui/material'
import { useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import { ApiErrorPanel } from '../components/states/ApiErrorPanel'
import { EmptyState } from '../components/states/EmptyState'
import { PanelSkeleton } from '../components/states/PanelSkeleton'
import { LabeledMetricsPanels } from '../features/modelEvaluation/LabeledMetricsPanels'
import { MetricsPanel } from '../features/modelEvaluation/MetricsPanel'
import {
  normalizeModelEvaluationVersion,
  useModelEvaluationQuery,
  useModelEvaluationsQuery,
} from '../features/modelEvaluation/queries'
import { VersionSelect } from '../features/modelEvaluation/VersionSelect'
import { updateUrlFilters } from '../features/filters/urlFilters'
import { tokens } from '../theme/tokens'

const technicalTextSx = {
  fontFamily: tokens.font.data,
  fontVariantNumeric: 'tabular-nums',
  overflowWrap: 'anywhere',
} as const

export function ModelEvaluationPage() {
  const [params, setParams] = useSearchParams()
  const listing = useModelEvaluationsQuery()
  const versions = listing.data?.items ?? []
  const requestedVersion = params.get('model_version')
  const selectedVersion = normalizeModelEvaluationVersion(versions, requestedVersion)
  const detail = useModelEvaluationQuery(selectedVersion)

  useEffect(() => {
    if (selectedVersion === undefined || requestedVersion === selectedVersion) return
    setParams(updateUrlFilters(params, { modelVersion: selectedVersion }), { replace: true })
  }, [params, requestedVersion, selectedVersion, setParams])

  return (
    <Stack spacing={6}>
      <Typography variant="h1">Model Evaluation</Typography>
      {listing.data === undefined ? (
        listing.isError ? (
          <ApiErrorPanel error={listing.error} onRetry={() => void listing.refetch()} />
        ) : (
          <PanelSkeleton label="Loading evaluation artifacts" />
        )
      ) : versions.length === 0 ? (
        <EmptyState
          title="No evaluation artifact exists"
          detail="Live scores do not establish model quality."
        />
      ) : (
        <>
          <Box sx={{ width: '100%', maxWidth: 280, minWidth: 0, '& > *': { width: '100%' } }}>
            <VersionSelect
              versions={versions}
              value={selectedVersion}
              onChange={(modelVersion) =>
                setParams(updateUrlFilters(params, { modelVersion }))
              }
            />
          </Box>
          {detail.data === undefined ? (
            detail.isError ? (
              <ApiErrorPanel error={detail.error} onRetry={() => void detail.refetch()} />
            ) : (
              <PanelSkeleton label="Loading selected evaluation artifact" />
            )
          ) : (
            <Stack component="section" aria-label={`Evaluation artifact ${detail.data.version}`} spacing={2}>
              <Paper
                component="section"
                aria-label="Artifact identity and metadata"
                variant="outlined"
                sx={{ maxWidth: '84ch', minWidth: 0, p: 4 }}
              >
                <Stack spacing={2}>
                  <Typography variant="h2">Artifact identity and metadata</Typography>
                  <Box
                    component="dl"
                    sx={{
                      display: 'grid',
                      gridTemplateColumns: 'repeat(2, minmax(0, 1fr))',
                      gap: 2,
                      m: 0,
                      minWidth: 0,
                    }}
                  >
                    <Box component="div" sx={{ minWidth: 0 }}>
                      <Typography component="dt" variant="caption" color="text.secondary">
                        Selected version:
                      </Typography>
                      {' '}
                      <Typography component="dd" variant="body1" sx={{ ...technicalTextSx, m: 0, minWidth: 0 }}>
                        {detail.data.version}
                      </Typography>
                    </Box>
                    <Box component="div" sx={{ minWidth: 0 }}>
                      <Typography component="dt" variant="caption" color="text.secondary">
                        Created at:
                      </Typography>
                      {' '}
                      <Typography component="dd" variant="body1" sx={{ ...technicalTextSx, m: 0, minWidth: 0 }}>
                        {detail.data.created_at}
                      </Typography>
                    </Box>
                    <Box component="div" sx={{ minWidth: 0 }}>
                      <Typography component="dt" variant="caption" color="text.secondary">
                        Evaluation period:
                      </Typography>
                      {' '}
                      <Typography component="dd" variant="body1" sx={{ ...technicalTextSx, m: 0, minWidth: 0 }}>
                        {detail.data.evaluation_period}
                      </Typography>
                    </Box>
                    {detail.data.model_hash === null ? null : (
                      <Box component="div" sx={{ minWidth: 0 }}>
                        <Typography component="dt" variant="caption" color="text.secondary">
                          Model hash:
                        </Typography>
                        {' '}
                        <Typography component="dd" variant="body1" sx={{ ...technicalTextSx, m: 0, minWidth: 0 }}>
                          {detail.data.model_hash}
                        </Typography>
                      </Box>
                    )}
                    {detail.data.preprocessing_hash === null ? null : (
                      <Box component="div" sx={{ minWidth: 0 }}>
                        <Typography component="dt" variant="caption" color="text.secondary">
                          Preprocessing hash:
                        </Typography>
                        {' '}
                        <Typography component="dd" variant="body1" sx={{ ...technicalTextSx, m: 0, minWidth: 0 }}>
                          {detail.data.preprocessing_hash}
                        </Typography>
                      </Box>
                    )}
                    {detail.data.threshold_hash === null ? null : (
                      <Box component="div" sx={{ minWidth: 0 }}>
                        <Typography component="dt" variant="caption" color="text.secondary">
                          Threshold hash:
                        </Typography>
                        {' '}
                        <Typography component="dd" variant="body1" sx={{ ...technicalTextSx, m: 0, minWidth: 0 }}>
                          {detail.data.threshold_hash}
                        </Typography>
                      </Box>
                    )}
                  </Box>
                </Stack>
              </Paper>
              <MetricsPanel
                availableMetrics={detail.data.available_metrics}
                metrics={detail.data.metrics}
              />
              <LabeledMetricsPanels artifact={detail.data} />
              {detail.data.notes === null ? null : (
                <Typography variant="body2" color="text.secondary">
                  Notes: {detail.data.notes}
                </Typography>
              )}
            </Stack>
          )}
        </>
      )}
    </Stack>
  )
}
