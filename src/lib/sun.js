// NOAA 근사식으로 일출·일몰 시각을 계산한다(오차 ±2분 내외). 외부 API 없이 브라우저에서 계산.
const RAD = Math.PI / 180
const KST_OFFSET = 9 * 3600e3

export function sunTimes(date, lat, lng) {
  const kst = new Date(date.getTime() + KST_OFFSET)
  const y = kst.getUTCFullYear()
  const m = kst.getUTCMonth()
  const d = kst.getUTCDate()
  const dayOfYear = Math.floor((Date.UTC(y, m, d) - Date.UTC(y, 0, 1)) / 86400e3) + 1
  const g = ((2 * Math.PI) / 365) * (dayOfYear - 1)
  const eqTime = 229.18 * (0.000075 + 0.001868 * Math.cos(g) - 0.032077 * Math.sin(g)
    - 0.014615 * Math.cos(2 * g) - 0.040849 * Math.sin(2 * g))
  const decl = 0.006918 - 0.399912 * Math.cos(g) + 0.070257 * Math.sin(g)
    - 0.006758 * Math.cos(2 * g) + 0.000907 * Math.sin(2 * g)
    - 0.002697 * Math.cos(3 * g) + 0.00148 * Math.sin(3 * g)
  const cosHa = Math.cos(90.833 * RAD) / (Math.cos(lat * RAD) * Math.cos(decl)) - Math.tan(lat * RAD) * Math.tan(decl)
  const ha = Math.acos(Math.min(1, Math.max(-1, cosHa))) / RAD
  // 결과는 'KST 날짜의 UTC 자정'에서 몇 분 뒤인지로 나온다. 음수면 전날 UTC = 당일 KST 오전.
  const base = Date.UTC(y, m, d)
  return {
    sunrise: new Date(base + (720 - 4 * (lng + ha) - eqTime) * 60e3),
    sunset: new Date(base + (720 - 4 * (lng - ha) - eqTime) * 60e3),
  }
}

export function hhmm(date) {
  if (!date) return '-'
  const kst = new Date(date.getTime() + KST_OFFSET)
  return `${String(kst.getUTCHours()).padStart(2, '0')}:${String(kst.getUTCMinutes()).padStart(2, '0')}`
}
