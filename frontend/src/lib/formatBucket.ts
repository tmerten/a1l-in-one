const MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']

export function formatBucket(bucket: string, bucketSize: string): string {
  if (bucketSize === 'day') {
    // "2026-06-01"
    const [, m, d] = bucket.split('-')
    return `${MONTHS[parseInt(m, 10) - 1]} ${parseInt(d, 10)}`
  }
  if (bucketSize === 'week') {
    // "2026-23" (YYYY-WW from SQLite %Y-%W)
    const [year, week] = bucket.split('-')
    return parseInt(week, 10) === 0 ? `${year} W1` : `W${parseInt(week, 10)}`
  }
  if (bucketSize === 'month') {
    // "2026-06"
    const [year, m] = bucket.split('-')
    return `${MONTHS[parseInt(m, 10) - 1]} ${year}`
  }
  // quarter: "2026-2"
  const [year, q] = bucket.split('-')
  return `Q${q} ${year}`
}
