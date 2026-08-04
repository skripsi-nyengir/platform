import { Box, Button, Chip, Paper, Slider, Stack, Typography } from '@mui/material'
import type { SimInjectionEvent } from '../../contracts/injection'
import { tokens } from '../../theme/tokens'

const technicalTextSx = {
  fontFamily: tokens.font.data,
  fontVariantNumeric: 'tabular-nums',
} as const

interface DayBucket {
  date: string
  count: number
  firstIndex: number
}

function dayBuckets(events: readonly SimInjectionEvent[]): DayBucket[] {
  const buckets = new Map<string, DayBucket>()
  events.forEach((event, index) => {
    const date = event.start_ts.slice(0, 10)
    const bucket = buckets.get(date)
    if (bucket === undefined) {
      buckets.set(date, { date, count: 1, firstIndex: index })
    } else {
      bucket.count += 1
    }
  })
  return [...buckets.values()]
}

function formatDay(value: string): string {
  return new Date(`${value}T00:00:00+07:00`).toLocaleDateString('en-GB', {
    day: '2-digit',
    month: 'short',
    timeZone: 'Asia/Jakarta',
  })
}

export function InjectionEventNavigator({
  events,
  selectedIndex,
  onSelect,
}: {
  events: readonly SimInjectionEvent[]
  selectedIndex: number
  onSelect: (index: number) => void
}) {
  const selected = events[selectedIndex]
  const days = dayBuckets(events)
  const maximumDailyCount = Math.max(...days.map((day) => day.count), 1)
  if (selected === undefined) return null

  return (
    <Paper component="section" aria-labelledby="corpus-navigator-heading" variant="outlined" sx={{ p: 4 }}>
      <Stack spacing={3}>
        <Stack direction="row" spacing={1} useFlexGap sx={{ justifyContent: 'space-between', flexWrap: 'wrap' }}>
          <Stack spacing={0.5}>
            <Typography id="corpus-navigator-heading" variant="h2">Full corpus event navigator</Typography>
            <Typography variant="body2" color="text.secondary" sx={technicalTextSx}>
              {events[0]?.start_ts} – {events.at(-1)?.end_ts} WIB
            </Typography>
          </Stack>
          <Chip label={`${events.length.toLocaleString('id-ID')} injected events`} color="primary" />
        </Stack>

        <Box
          component="ul"
          aria-label="Injection events by corpus day"
          sx={{
            display: 'grid',
            gridTemplateColumns: `repeat(auto-fit, minmax(${tokens.size.sparkline}px, 1fr))`,
            gap: 1,
            listStyle: 'none',
            m: 0,
            p: 0,
          }}
        >
          {days.map((day) => {
            const selectedDay = selected.start_ts.startsWith(day.date)
            return (
              <Box component="li" key={day.date} sx={{ minWidth: 0 }}>
                <Button
                  variant={selectedDay ? 'contained' : 'outlined'}
                  aria-label={`${formatDay(day.date)}, ${day.count} injection events`}
                  aria-current={selectedDay ? 'date' : undefined}
                  onClick={() => onSelect(day.firstIndex)}
                  sx={{ display: 'block', width: '100%', height: '100%', minWidth: 0, p: 2, textAlign: 'left' }}
                >
                  <Stack spacing={1}>
                    <Typography variant="caption" color="inherit">{formatDay(day.date)}</Typography>
                    <Box sx={{ display: 'flex', height: tokens.size.control, alignItems: 'flex-end' }}>
                      <Box
                        aria-hidden="true"
                        sx={{
                          width: '100%',
                          minHeight: tokens.size.activeRule,
                          height: `${(day.count / maximumDailyCount) * 100}%`,
                          borderRadius: tokens.radius.sm,
                          backgroundColor: selectedDay ? 'primary.contrastText' : 'primary.main',
                          opacity: selectedDay ? 0.8 : 0.65,
                        }}
                      />
                    </Box>
                    <Typography variant="body2" color="inherit" sx={technicalTextSx}>{day.count}</Typography>
                  </Stack>
                </Button>
              </Box>
            )
          })}
        </Box>
        <Typography variant="caption" color="text.secondary">
          Bar height shows injection-event density per corpus day; select a day to jump to its first event.
        </Typography>

        <Stack spacing={1}>
          <Box sx={{ px: 1 }}>
            <Slider
              aria-label="Injection event"
              min={1}
              max={events.length}
              step={1}
              value={selectedIndex + 1}
              valueLabelDisplay="auto"
              valueLabelFormat={(value) => `Event ${value}`}
              marks={[
                { value: 1, label: '1' },
                { value: events.length, label: events.length.toLocaleString('id-ID') },
              ]}
              onChange={(_, value) => {
                if (typeof value === 'number') onSelect(value - 1)
              }}
            />
          </Box>
          <Stack direction="row" spacing={1} sx={{ justifyContent: 'space-between' }}>
            <Button
              variant="outlined"
              disabled={selectedIndex === 0}
              onClick={() => onSelect(selectedIndex - 1)}
            >
              Previous event
            </Button>
            <Button
              variant="outlined"
              disabled={selectedIndex === events.length - 1}
              onClick={() => onSelect(selectedIndex + 1)}
            >
              Next event
            </Button>
          </Stack>
        </Stack>

        <Paper variant="outlined" sx={{ p: 3, backgroundColor: 'app.offlineSoft' }}>
          <Stack spacing={2}>
            <Stack direction="row" spacing={1} useFlexGap sx={{ alignItems: 'center', flexWrap: 'wrap' }}>
              <Typography variant="h3">Event {selectedIndex + 1} of {events.length}</Typography>
              <Chip label={selected.family} size="small" />
              <Chip
                label={selected.severity}
                size="small"
                color={selected.severity === 'high' ? 'error' : selected.severity === 'medium' ? 'warning' : 'default'}
              />
            </Stack>
            <Box
              component="dl"
              sx={{
                display: 'grid',
                gridTemplateColumns: `repeat(auto-fit, minmax(${tokens.size.sidebarCompact * 2}px, 1fr))`,
                gap: 2,
                m: 0,
              }}
            >
              <Box sx={{ gridColumn: 'span 2' }}>
                <Typography component="dt" variant="caption" color="text.secondary">Time</Typography>
                <Typography component="dd" variant="body2" sx={{ ...technicalTextSx, m: 0, whiteSpace: 'nowrap' }}>
                  {selected.start_ts} – {selected.end_ts}
                </Typography>
              </Box>
              {[
                ['Channel', `${selected.channel} · index ${selected.channel_index}`],
                ['Frame span', `${selected.start_idx}–${selected.end_idx_exclusive - 1}`],
                ['Segment', String(selected.segment_index)],
              ].map(([label, value]) => (
                <Box key={label}>
                  <Typography component="dt" variant="caption" color="text.secondary">{label}</Typography>
                  <Typography component="dd" variant="body2" sx={{ ...technicalTextSx, m: 0 }}>{value}</Typography>
                </Box>
              ))}
            </Box>
          </Stack>
        </Paper>
      </Stack>
    </Paper>
  )
}
