const shortMonthNames = [
  'Jan',
  'Feb',
  'Mar',
  'Apr',
  'May',
  'Jun',
  'Jul',
  'Aug',
  'Sep',
  'Oct',
  'Nov',
  'Dec',
] as const

export function formatWibDateTime(value: string): string {
  const year = value.slice(0, 4)
  const month = value.slice(5, 7)
  const day = value.slice(8, 10)
  const time = value.slice(11)
  const monthName = shortMonthNames[Number(month) - 1] ?? month

  return `${day} ${monthName} ${year}, ${time}`
}
