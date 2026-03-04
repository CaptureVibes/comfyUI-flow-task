/**
 * 日期时间工具函数
 */

export function formatTime(value) {
  if (!value) return '-'
  return new Date(value).toLocaleString()
}

export function formatTimeShort(value) {
  if (!value) return '-'
  return new Date(value).toLocaleTimeString()
}

export function defaultScheduleAt() {
  const base = new Date()
  base.setSeconds(0, 0)
  base.setMinutes(base.getMinutes() + 5)
  return base
}

export function scheduleAtFromLegacyTime(value) {
  const raw = String(value || '').trim()
  if (!raw) return null
  const parts = raw.split(':').map((item) => Number(item))
  if (parts.length !== 2 || Number.isNaN(parts[0]) || Number.isNaN(parts[1])) return null
  const dt = new Date()
  dt.setSeconds(0, 0)
  dt.setHours(parts[0], parts[1], 0, 0)
  return dt
}
