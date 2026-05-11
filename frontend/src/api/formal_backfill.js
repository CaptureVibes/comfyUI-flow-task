import http from './http'

export async function generateFormalBackfill({ targetTotal, startDate, endDate, seed }) {
  const { data } = await http.post('/formal-backfill/generate', {
    target_total: targetTotal,
    start_date: startDate,
    end_date: endDate,
    seed: seed ?? null,
  })
  return data
}

export async function clearFormalBackfill() {
  const { data } = await http.delete('/formal-backfill')
  return data
}

export async function fetchFormalBackfillSummary({ startDate, endDate } = {}) {
  const params = {}
  if (startDate) params.start_date = startDate
  if (endDate) params.end_date = endDate
  const { data } = await http.get('/formal-backfill/summary', { params })
  return data
}

export async function exportFormalBackfillTaskIds() {
  const { data } = await http.get('/formal-backfill/export')
  return data
}
