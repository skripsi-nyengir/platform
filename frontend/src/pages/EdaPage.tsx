import { Box, Stack, Typography } from '@mui/material'
import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import type { EdaField } from '../contracts/eda'
import { CandidateOutliersPanel } from '../features/eda/CandidateOutliersPanel'
import { CorrelationPanel } from '../features/eda/CorrelationPanel'
import { CoveragePanel } from '../features/eda/CoveragePanel'
import { DistributionPanel } from '../features/eda/DistributionPanel'
import { EdaFilters, type EdaFiltersValue } from '../features/eda/EdaFilters'
import { MissingnessPanel } from '../features/eda/MissingnessPanel'
import { useEdaSummaryQuery } from '../features/eda/queries'
import { SensorComparisonPanel } from '../features/eda/SensorComparisonPanel'
import { TemporalPatternsPanel } from '../features/eda/TemporalPatternsPanel'
import {
  parseUrlFilters,
  updateUrlFilters,
  type UrlFilters,
} from '../features/filters/urlFilters'

export function EdaPage() {
  const [params, setParams] = useSearchParams()
  const [sampleSize, setSampleSize] = useState(1_000)
  const [xField, setXField] = useState<EdaField>('temperature_c')
  const [yField, setYField] = useState<EdaField>('relative_humidity_pct')
  const filters = parseUrlFilters(params)
  const summary = useEdaSummaryQuery(filters)
  const error = summary.isError ? summary.error : undefined
  const loading = summary.data === undefined && error === undefined
  const retrySummary = () => void summary.refetch()

  const handleFilterChange = (patch: Partial<EdaFiltersValue>) => {
    if (patch.sampleSize !== undefined) setSampleSize(patch.sampleSize)
    if (patch.xField !== undefined) setXField(patch.xField)
    if (patch.yField !== undefined) setYField(patch.yField)

    const urlPatch: Partial<UrlFilters> = {}
    if (Object.hasOwn(patch, 'sensor')) urlPatch.sensor = patch.sensor
    if (patch.from !== undefined) urlPatch.from = patch.from
    if (patch.to !== undefined) urlPatch.to = patch.to
    if (patch.bucket !== undefined) urlPatch.bucket = patch.bucket
    if (Object.keys(urlPatch).length > 0) setParams(updateUrlFilters(params, urlPatch))
  }

  return (
    <Stack spacing={6}>
      <Typography variant="h1">EDA</Typography>
      <EdaFilters
        value={{ ...filters, sampleSize, xField, yField }}
        onChange={handleFilterChange}
      />
      <Box
        role="group"
        aria-label="Quality and missingness"
        sx={{
          display: 'grid',
          gridTemplateColumns: 'repeat(2, minmax(0, 1fr))',
          gap: 4,
          alignItems: 'stretch',
          '& > *': { minWidth: 0 },
        }}
      >
        <CoveragePanel
          coverage={summary.data?.coverage}
          loading={loading}
          error={error}
          onRetry={retrySummary}
        />
        <MissingnessPanel
          missingness={summary.data?.missingness}
          loading={loading}
          error={error}
          onRetry={retrySummary}
        />
      </Box>
      <DistributionPanel filters={filters} />
      <TemporalPatternsPanel filters={filters} sampleSize={sampleSize} />
      <CorrelationPanel
        filters={filters}
        sampleSize={sampleSize}
        xField={xField}
        yField={yField}
      />
      <SensorComparisonPanel
        rows={summary.data?.sensor_comparison}
        loading={loading}
        error={error}
        onRetry={retrySummary}
      />
      <CandidateOutliersPanel
        rows={summary.data?.candidate_outliers}
        loading={loading}
        error={error}
        onRetry={retrySummary}
      />
    </Stack>
  )
}
