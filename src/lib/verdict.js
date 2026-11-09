// 산행 신호등 판정 규칙.
// 점수를 합산하지 않고 '가장 나쁜 신호'를 따른다. 하나라도 위험이면 위험.
// 기준값은 README의 '판정 기준'과 같게 유지한다.
import { sunTimes, hhmm } from './sun.js'

export const OK = 0
export const CAUTION = 1
export const DANGER = 2

export const LEVEL_META = [
  { key: 'ok', label: '좋음', title: '산행하기 좋아요', color: 'var(--ok)' },
  { key: 'caution', label: '주의', title: '주의하면서 다녀오세요', color: 'var(--caution)' },
  { key: 'danger', label: '위험', title: '오늘은 쉬어가세요', color: 'var(--danger)' },
]

export const SOURCES = {
  fire: '산림청 산불위험예보',
  slide: '산림청 산사태예측',
  weather: '산림청 산악기상',
  sun: '일출·일몰 계산',
  trail: '산림청 등산로',
}

// 산림청 산불위험지수 단계: 낮음(~50) 보통(51~65) 높음(66~85) 매우높음(86~)
export function fireStage(index) {
  if (index >= 86) return { label: '매우높음', level: DANGER }
  if (index >= 66) return { label: '높음', level: CAUTION }
  if (index >= 51) return { label: '보통', level: OK }
  return { label: '낮음', level: OK }
}

// 기상청 겨울철 체감온도식 (기온 10℃ 이하, 풍속 1.3m/s 이상에서 유효)
export function windChill(t, ws) {
  if (t == null || ws == null || t > 10 || ws < 1.3) return t
  const v = (ws * 3.6) ** 0.16
  return 13.12 + 0.6215 * t - 11.37 * v + 0.3965 * v * t
}

const avg = (xs) => (xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : null)
const median = (xs) => {
  if (!xs.length) return null
  const s = [...xs].sort((a, b) => a - b)
  const mid = Math.floor(s.length / 2)
  return s.length % 2 ? s[mid] : (s[mid - 1] + s[mid]) / 2
}
const pick = (obs, key) => obs.map((o) => o[key]).filter((v) => v != null)

export function hoursText(minutes) {
  const h = minutes / 60
  return Number.isInteger(h) ? `${h}` : h.toFixed(1)
}

export function fireFor(m, snapshot) {
  const byCode = snapshot?.fire?.by_code
  if (!byCode) return null
  const rows = m.fire_codes
    .map((code, i) => ({ code, region: m.regions[i], v: byCode[code] }))
    .filter((r) => r.v)
  if (!rows.length) return null
  const worst = rows.reduce((a, b) => (b.v[0] > a.v[0] ? b : a))
  return {
    mean: worst.v[0],
    max: Math.max(...rows.map((r) => r.v[1])),
    region: worst.region,
    regions: rows.length,
    stage: fireStage(worst.v[0]),
    analdate: snapshot.fire.analdate,
  }
}

export function slideFor(m, snapshot) {
  const ls = snapshot?.landslide
  if (!ls?.ok) return null
  const hits = m.regions.map((r) => ({ region: r, ...ls.active?.[r] })).filter((h) => h.level)
  const worst = hits.find((h) => h.level === '경보') || hits[0] || null
  return { active: worst, latestAny: ls.latest_any }
}

export function weatherFor(m, snapshot, stationNames) {
  const by = snapshot?.weather?.by_station
  if (!by) return null
  const obs = m.stations
    .map((id) => ({ id, name: stationNames[id] || `관측소 ${id}`, ...by[id] }))
    .filter((o) => o.t != null)
  if (!obs.length) return null
  if (m.station_match === 'name') {
    const o = obs[0]
    return { ...o, wind: o.ws10 ?? o.ws, how: 'name', label: o.name, count: 1 }
  }
  // 같은 시군구(또는 인근) 관측소 여러 곳: 관측소 좌표가 없어 어느 곳이 가장 가까운지 모른다.
  // 한 곳의 국지적인 값에 끌려가지 않도록 기온·습도는 평균, 바람·비는 중앙값을 쓴다.
  return {
    t: avg(pick(obs, 't')),
    hm: avg(pick(obs, 'hm')),
    wind: median(obs.map((o) => o.ws10 ?? o.ws).filter((x) => x != null)),
    windMax: Math.max(0, ...obs.map((o) => o.ws10 ?? o.ws ?? 0)),
    rn: median(pick(obs, 'rn')) ?? 0,
    rnMax: Math.max(0, ...pick(obs, 'rn')),
    cprn: median(pick(obs, 'cprn')) ?? 0,
    at: obs[0].at,
    how: m.station_match,
    label: obs.length > 1 ? `${obs[0].name} 외 ${obs.length - 1}곳` : obs[0].name,
    names: obs.map((o) => o.name),
    count: obs.length,
  }
}

export function sunFor(m, now) {
  const today = sunTimes(now, m.lat, m.lng)
  const tomorrow = sunTimes(new Date(now.getTime() + 86400e3), m.lat, m.lng)
  const walk = m.walk_min || 180
  const latestStart = new Date(today.sunset.getTime() - (walk + 30) * 60e3)
  const night = now < today.sunrise || now > today.sunset
  return {
    ...today,
    nextSunrise: now > today.sunset ? tomorrow.sunrise : today.sunrise,
    latestStart,
    walk,
    night,
    minutesLeft: Math.round((today.sunset - now) / 60e3),
  }
}

export function evaluate(m, { snapshot, stationNames, now }) {
  const reasons = []
  const add = (level, text, source) => reasons.push({ level, text, source })

  const fire = fireFor(m, snapshot)
  if (fire) {
    if (fire.stage.level > OK) {
      add(fire.stage.level, `산불위험 '${fire.stage.label}' (${fire.region} 평균 지수 ${fire.mean})`, SOURCES.fire)
    } else if (fire.max >= 66) {
      add(OK, `일부 지역은 산불위험지수가 ${fire.max}까지 올라가요. 화기를 가져가지 마세요`, SOURCES.fire)
    }
  }

  const slide = slideFor(m, snapshot)
  if (slide?.active) {
    const level = slide.active.level === '경보' ? DANGER : CAUTION
    add(level, `산사태 ${slide.active.level} 발령 중 (${slide.active.region}, ${slide.active.time.slice(11)})`, SOURCES.slide)
  }

  const w = weatherFor(m, snapshot, stationNames)
  if (w) {
    const feels = windChill(w.t, w.wind)
    w.feels = feels
    if (w.wind >= 14) add(DANGER, `강풍 ${w.wind.toFixed(1)}m/s, 능선에서 넘어지거나 물건이 떨어질 수 있어요`, SOURCES.weather)
    else if (w.wind >= 8) add(CAUTION, `바람이 강해요 (${w.wind.toFixed(1)}m/s)`, SOURCES.weather)
    else if (w.windMax >= 14) add(CAUTION, `근처 관측소 일부에 강풍 (최대 ${w.windMax.toFixed(1)}m/s)`, SOURCES.weather)
    if (w.rn >= 10) add(DANGER, `강한 비 ${w.rn}mm, 계곡이 불어나고 길이 미끄러워요`, SOURCES.weather)
    else if (w.rn > 0) add(CAUTION, `비가 오고 있어요 (${w.rn}mm)`, SOURCES.weather)
    else if (w.rnMax >= 10) add(CAUTION, `근처 관측소 일부에 강한 비 (최대 ${w.rnMax}mm)`, SOURCES.weather)
    else if (w.rnMax > 0) add(OK, `근처 관측소 일부에 약한 비 (최대 ${w.rnMax}mm)`, SOURCES.weather)
    if (feels != null && feels <= -25) add(DANGER, `체감온도 ${feels.toFixed(0)}℃, 저체온증 위험`, SOURCES.weather)
    else if (feels != null && feels <= -10) add(CAUTION, `체감온도 ${feels.toFixed(0)}℃, 방한 장비를 챙기세요`, SOURCES.weather)
    else if (w.t != null && w.t <= 0 && (w.rn > 0 || w.hm >= 95)) add(CAUTION, `영하에 습도가 높아 길이 얼 수 있어요`, SOURCES.weather)
    if (w.t >= 35) add(DANGER, `기온 ${w.t.toFixed(0)}℃, 열사병 위험`, SOURCES.weather)
    else if (w.t >= 33) add(CAUTION, `기온 ${w.t.toFixed(0)}℃, 폭염 수준`, SOURCES.weather)
  }

  const sun = sunFor(m, now)
  if (!sun.night) {
    if (sun.minutesLeft < 30) add(DANGER, `해 지기까지 ${sun.minutesLeft}분, 지금 오르면 어두워진 뒤에 내려와요`, SOURCES.sun)
    else if (now > sun.latestStart) {
      add(CAUTION, `지금 출발하면 하산 전에 해가 질 수 있어요 (일반 코스 ${hoursText(sun.walk)}시간 기준)`, SOURCES.sun)
    }
  }

  const level = reasons.reduce((max, r) => Math.max(max, r.level), OK)
  reasons.sort((a, b) => b.level - a.level)
  const hasLive = Boolean(fire || w || slide)
  return { level, reasons, fire, slide, weather: w, sun, hasLive }
}

export function headline(v) {
  const top = v.reasons.find((r) => r.level === v.level && r.level > OK)
  if (top) return top.text
  if (v.sun.night) return '위험 신호 없음, 지금은 해가 진 시간'
  return '산불·산사태·기상 위험 신호 없음'
}

export { hhmm, sunTimes }
