import { Box, Button, Paper, Stack, Typography } from '@mui/material'
import type { GridColDef } from '@mui/x-data-grid'
import { useEffect, useId, useMemo, useRef, useState } from 'react'
import { BoundedDataDialog } from '../data/BoundedDataDialog'
import { tokens } from '../../theme/tokens'
import { jointDensityColor } from './edaV3Options'

interface HeatmapRow {
  id: string
  temperatureStart: number
  temperatureEnd: number
  humidityStart: number
  humidityEnd: number
  count: number
}

const heatmapColumns: readonly GridColDef<HeatmapRow>[] = [
  { field: 'temperatureStart', headerName: 'Suhu mulai (°C)', flex: 1 },
  { field: 'temperatureEnd', headerName: 'Suhu akhir (°C)', flex: 1 },
  { field: 'humidityStart', headerName: 'RH mulai (%)', flex: 1 },
  { field: 'humidityEnd', headerName: 'RH akhir (%)', flex: 1 },
  { field: 'count', headerName: 'Jumlah pasangan', flex: 1 },
]

export interface CanvasHeatmapProps {
  title: string
  description: string
  temperatureEdges: readonly number[]
  humidityEdges: readonly number[]
  matrix: readonly (readonly number[])[]
  maximumCount: number
  colors: readonly string[]
}

export function CanvasHeatmap({
  title,
  description,
  temperatureEdges,
  humidityEdges,
  matrix,
  maximumCount,
  colors,
}: CanvasHeatmapProps) {
  const [dialogOpen, setDialogOpen] = useState(false)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const titleId = useId()
  const descriptionId = useId()
  const humidityBinCount = Math.max(1, humidityEdges.length - 1)
  const temperatureBinCount = Math.max(1, temperatureEdges.length - 1)
  const rows = useMemo<HeatmapRow[]>(() => matrix.flatMap((counts, temperatureIndex) => (
    counts.map((count, humidityIndex) => ({
      id: `${temperatureIndex}-${humidityIndex}`,
      temperatureStart: temperatureEdges[temperatureIndex] ?? 0,
      temperatureEnd: temperatureEdges[temperatureIndex + 1] ?? 0,
      humidityStart: humidityEdges[humidityIndex] ?? 0,
      humidityEnd: humidityEdges[humidityIndex + 1] ?? 0,
      count,
    }))
  )), [humidityEdges, matrix, temperatureEdges])

  useEffect(() => {
    const canvas = canvasRef.current
    if (canvas === null) return
    let context: CanvasRenderingContext2D | null = null
    try {
      context = canvas.getContext('2d')
    } catch {
      return
    }
    if (context === null) return
    context.clearRect(0, 0, canvas.width, canvas.height)
    matrix.forEach((counts, temperatureIndex) => {
      counts.forEach((count, humidityIndex) => {
        context.fillStyle = jointDensityColor(count, maximumCount, colors)
        context.fillRect(
          temperatureIndex,
          humidityBinCount - humidityIndex - 1,
          1,
          1,
        )
      })
    })
  }, [colors, humidityBinCount, matrix, maximumCount])

  return (
    <Paper component="article" variant="outlined" sx={{ minWidth: 0, p: 4 }}>
      <Stack spacing={2} sx={{ minWidth: 0, height: '100%' }}>
        <Typography id={titleId} variant="h3">{title}</Typography>
        <Typography id={descriptionId} variant="body2" color="text.secondary">
          {description}
        </Typography>
        <Box sx={{ minWidth: 0 }}>
          <canvas
            ref={canvasRef}
            width={temperatureBinCount}
            height={humidityBinCount}
            role="img"
            aria-labelledby={titleId}
            aria-describedby={descriptionId}
            style={{
              display: 'block',
              height: tokens.size.control * 7,
              maxWidth: '100%',
              width: '100%',
            }}
          >
            {description}
          </canvas>
          <Stack
            direction="row"
            spacing={1}
            useFlexGap
            sx={{ alignItems: 'center', justifyContent: 'space-between', mt: 1, minWidth: 0 }}
          >
            <Typography variant="caption">RH rendah</Typography>
            <Typography variant="caption">Suhu (°C) →</Typography>
            <Typography variant="caption">RH tinggi</Typography>
          </Stack>
        </Box>
        <Box
          role="img"
          aria-label={`Legenda jumlah pasangan skala logaritmik dari 0 sampai ${maximumCount}`}
          sx={{ minWidth: 0 }}
        >
          <Box
            sx={{
              background: `linear-gradient(90deg, ${colors.join(', ')})`,
              border: `${tokens.size.rule}px solid`,
              borderColor: 'divider',
              height: tokens.spacing.unit * 3,
            }}
          />
          <Stack direction="row" sx={{ justifyContent: 'space-between' }}>
            <Typography variant="caption" sx={{ fontFamily: tokens.font.data }}>0</Typography>
            <Typography variant="caption">Jumlah pasangan (skala log)</Typography>
            <Typography variant="caption" sx={{ fontFamily: tokens.font.data }}>
              {maximumCount.toLocaleString('id-ID')}
            </Typography>
          </Stack>
        </Box>
        <Button
          size="small"
          aria-label={`Lihat data ${title}`}
          onClick={() => setDialogOpen(true)}
          sx={{ mt: 'auto' }}
        >
          Lihat data
        </Button>
        <BoundedDataDialog<HeatmapRow>
          open={dialogOpen}
          title={`${title} — seluruh sel`}
          rows={rows}
          returnedCount={rows.length}
          columns={heatmapColumns}
          onClose={() => setDialogOpen(false)}
        />
      </Stack>
    </Paper>
  )
}
