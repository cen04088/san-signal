<script setup>
import { computed } from 'vue'
import { hhmm, hoursText, LEVEL_META, OK } from '../lib/verdict.js'

const props = defineProps({
  mountain: { type: Object, required: true },
  verdict: { type: Object, required: true },
  trail: { type: Object, default: null },
  quality: { type: Object, default: null },
})
const emit = defineEmits(['back'])

const meta = computed(() => LEVEL_META[props.verdict.level])
const m = computed(() => props.mountain)
const v = computed(() => props.verdict)

const walkText = computed(() => {
  const { walk_min: a, walk_max: b } = m.value
  if (!a) return ''
  return b && b !== a ? `일반 코스 ${hoursText(a)}~${hoursText(b)}시간` : `일반 코스 약 ${hoursText(a)}시간`
})

// 판정에 실제로 쓴 데이터 이름. 빠진 데이터가 있으면 함께 알린다.
const basis = computed(() => {
  const used = [['산불위험', v.value.fire], ['산사태', v.value.slide], ['산악기상', v.value.weather]]
  const have = used.filter(([, x]) => x).map(([name]) => name)
  const miss = used.filter(([, x]) => !x).map(([name]) => name)
  if (!have.length) return '실시간 자료를 받지 못했어요'
  return `${have.join('·')} 기준` + (miss.length ? ` (${miss.join('·')} 자료 없음)` : '')
})

const fireTile = computed(() => {
  const f = v.value.fire
  if (!f) return { state: 'none', value: '자료 없음', note: '' }
  const state = f.stage.level === 2 ? 'danger' : f.stage.level === 1 ? 'caution' : 'ok'
  return {
    state,
    value: f.stage.label,
    note: `${f.region} 평균 ${f.mean} · 최고 ${f.max}`,
    foot: f.analdate ? `${f.analdate.slice(5).replace('-', '/')}시 분석` : '',
  }
})

const slideTile = computed(() => {
  const s = v.value.slide
  if (!s) return { state: 'none', value: '자료 없음', note: '' }
  if (s.active) {
    return {
      state: s.active.level === '경보' ? 'danger' : 'caution',
      value: `${s.active.level} 발령`,
      note: `${s.active.region} · ${s.active.time.slice(5)}`,
    }
  }
  return {
    state: 'ok',
    value: '발령 없음',
    note: m.value.regions.slice(0, 2).join(', ') + (m.value.regions.length > 2 ? ` 외 ${m.value.regions.length - 2}곳` : ''),
    foot: s.latestAny ? `최근 발령 ${s.latestAny.slice(0, 10)}` : '',
  }
})

const weatherTile = computed(() => {
  const w = v.value.weather
  if (!w) return { state: 'none', value: '자료 없음', note: '가까운 산악기상관측소가 없어요' }
  const worst = v.value.reasons.filter((r) => r.source.includes('산악기상')).reduce((x, r) => Math.max(x, r.level), OK)
  const parts = []
  if (w.feels != null && w.t != null && Math.abs(w.feels - w.t) >= 1) parts.push(`체감 ${w.feels.toFixed(0)}℃`)
  if (w.wind != null) parts.push(`바람 ${w.wind.toFixed(1)}m/s`)
  if (w.hm != null) parts.push(`습도 ${Math.round(w.hm)}%`)
  if (w.rn > 0) parts.push(`강수 ${w.rn}mm`)
  const how = w.how === 'nearby' ? ' (인근 지역)' : ''
  return {
    state: ['ok', 'caution', 'danger'][worst],
    value: w.t != null ? `${w.t.toFixed(1)}℃` : '-',
    note: parts.join(' · '),
    foot: `${w.label}${how} · ${w.at || ''} 관측`,
  }
})

const sunTile = computed(() => {
  const s = v.value.sun
  if (s.night) {
    return { state: 'night', value: `일출 ${hhmm(s.nextSunrise)}`, note: '해가 진 시간이에요. 야간 산행은 피하세요.' }
  }
  const late = s.minutesLeft < 30 ? 'danger' : new Date() > s.latestStart ? 'caution' : 'ok'
  return {
    state: late,
    value: `일몰 ${hhmm(s.sunset)}`,
    note: `늦어도 ${hhmm(s.latestStart)}까지 출발`,
    foot: `일반 코스 왕복 ${hoursText(s.walk)}시간에 30분을 더한 기준`,
  }
})

const tiles = computed(() => [
  { key: 'fire', title: '산불위험', src: '산림청 산불위험예보', ...fireTile.value },
  { key: 'slide', title: '산사태', src: '산림청 산사태예측', ...slideTile.value },
  { key: 'weather', title: '산악기상', src: '산림청 산악기상관측', ...weatherTile.value },
  { key: 'sun', title: '해·하산', src: '일출·일몰 계산', ...sunTile.value },
])

const riskNotes = computed(() => {
  const counts = new Map()
  for (const s of props.trail?.segments || []) {
    if (!s.risk) continue
    const text = s.risk.trim()
    counts.set(text, (counts.get(text) || 0) + 1)
  }
  return [...counts.entries()].sort((a, b) => b[1] - a[1]).slice(0, 5)
})

const trailDate = computed(() => props.quality?.data_date?.[0]?.[0] || '')

// 등산로를 그리지 않는 산: 산림청 등산로 공간정보에 없거나, 찾은 구간이 이 산 것으로 보기 어려운 경우
const noTrailText = computed(() => {
  const t = m.value.trails || {}
  if (t.status === 'far') {
    return `산림청 등산로 공간정보에서 찾은 구간 중 정상에 가장 가까운 것도 ${t.nearest_km}km 떨어져 있어요. 이 산 등산로로 보기 어려워 지도에 그리지 않았어요.`
  }
  if (t.status === 'few') {
    return `산림청 등산로 공간정보에 이 산 구간이 ${t.found}개뿐이라 지도에 그리지 않았어요.`
  }
  return '산림청 등산로 공간정보에 이 산의 등산로가 없어요.'
})
</script>

<template>
  <article class="detail">
    <button type="button" class="back" @click="emit('back')">
      <svg viewBox="0 0 12 20" width="9" height="15" aria-hidden="true">
        <path d="M10 2 2 10l8 8" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" />
      </svg>
      전체 산
    </button>

    <header class="head">
      <h1>
        {{ m.name }}
        <em v-if="m.national_park">국립공원</em>
      </h1>
      <p>
        {{ m.region }}<template v-if="m.elevation_m"> · {{ m.elevation_m.toLocaleString() }}m</template><template v-if="walkText"> · {{ walkText }}</template>
      </p>
    </header>

    <section class="signal" :class="v.hasLive ? meta.key : 'none'" :aria-label="`산행 신호 ${v.hasLive ? meta.label : '자료 없음'}`">
      <div class="lights" aria-hidden="true">
        <i class="r" :class="{ on: v.hasLive && v.level === 2 }" />
        <i class="y" :class="{ on: v.hasLive && v.level === 1 }" />
        <i class="g" :class="{ on: v.hasLive && v.level === 0 }" />
      </div>
      <div class="msg">
        <strong>{{ v.hasLive ? meta.title : '실시간 자료가 없어요' }}</strong>
        <span>{{ basis }}</span>
      </div>
    </section>

    <ul class="reasons" v-if="v.reasons.length">
      <li v-for="(r, i) in v.reasons" :key="i" :class="LEVEL_META[r.level].key">
        <span class="txt">{{ r.text }}</span>
        <span class="src">{{ r.source }}</span>
      </li>
    </ul>
    <p class="calm" v-else-if="v.hasLive">
      지금은 산불·산사태·기상 위험 신호가 없어요. 그래도 물과 간식, 보온 옷은 챙기세요.
    </p>

    <section class="tiles">
      <div v-for="t in tiles" :key="t.key" class="tile" :class="t.state">
        <span class="t-title">{{ t.title }}</span>
        <strong class="t-value">{{ t.value }}</strong>
        <span class="t-note" v-if="t.note">{{ t.note }}</span>
        <span class="t-foot" v-if="t.foot">{{ t.foot }}</span>
        <span class="t-src">{{ t.src }}</span>
      </div>
    </section>

    <section class="block">
      <h2>등산로</h2>
      <template v-if="m.trails?.segments">
        <p class="trail-sum">
          <b>{{ m.trails.segments }}</b>개 구간 · 총 <b>{{ m.trails.km }}</b>km
          <template v-if="m.trails.risk"> · 위험구간 <b class="warn">{{ m.trails.risk }}</b></template>
          <template v-if="m.trails.closed"> · 폐쇄 <b>{{ m.trails.closed }}</b></template>
          <template v-if="m.trails.ctrl"> · 통제 <b class="warn">{{ m.trails.ctrl }}</b></template>
        </p>
        <ul v-if="riskNotes.length" class="risks">
          <li v-for="[text, n] in riskNotes" :key="text">
            <span>{{ text }}</span><small>{{ n }}구간</small>
          </li>
        </ul>
        <p class="hint">지도에서 등산로 선을 누르면 구간 이름, 소요 시간, 위험 정보가 나와요.</p>
        <p class="src-line">산림청 등산로(1:25,000) 공간정보<template v-if="trailDate"> · 자료 기준일 {{ trailDate }}</template></p>
      </template>
      <template v-else>
        <p class="hint">{{ noTrailText }}</p>
        <p v-if="m.national_park" class="hint">국립공원 탐방로는 국립공원공단 안내를 확인하세요.</p>
      </template>
    </section>

    <section class="block" v-if="m.description">
      <h2>산 소개</h2>
      <p class="desc">{{ m.description }}</p>
      <p class="src-line">{{ m.description_source === 'olla' ? '이전 프로젝트(올라)에서 정리한 자료' : '산림청 산정보 서비스' }}</p>
    </section>

    <p class="disclaimer">
      신호등은 참고용이에요. 입산 통제나 기상 특보가 있으면 그 안내를 따르세요. 응급 상황에는 119에 전화하세요.
    </p>
  </article>
</template>

<style scoped>
.back {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-left: -4px;
  padding: 6px 10px 6px 6px;
  border: 0;
  border-radius: 10px;
  background: none;
  font-size: var(--fs-body);
  font-weight: 650;
  color: var(--brand);
  transition: var(--press), background-color 120ms ease;
}

.back:active {
  transform: scale(0.96);
  background: var(--surface);
}

.head h1 {
  margin: 6px 0 4px;
  font-size: var(--fs-large);
  font-weight: 750;
  line-height: 1.15;
  letter-spacing: var(--tr-large);
}

.head h1 em {
  margin-left: 6px;
  padding: 2px 8px;
  border-radius: 8px;
  background: var(--surface);
  box-shadow: inset 0 0 0 1px var(--line);
  font-size: var(--fs-caption);
  font-style: normal;
  font-weight: 600;
  letter-spacing: var(--tr-caption);
  color: var(--ink-2);
  vertical-align: 5px;
}

.head p {
  margin: 0 0 16px;
  font-size: var(--fs-body);
  color: var(--ink-2);
}

.signal {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px;
  border-radius: 20px;
  background: var(--surface-2);
}

.signal.ok { background: var(--ok-bg); }
.signal.caution { background: var(--caution-bg); }
.signal.danger { background: var(--danger-bg); }

.lights {
  flex: none;
  display: flex;
  gap: 6px;
  padding: 8px 10px;
  border-radius: 999px;
  background: var(--housing);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.08);
}

.lights i {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  opacity: 0.18;
}

.lights .r { background: var(--danger); color: var(--danger); }
.lights .y { background: var(--caution); color: var(--caution); }
.lights .g { background: var(--ok); color: var(--ok); }

.lights i.on {
  opacity: 1;
  box-shadow: 0 0 14px 1px currentColor;
  animation: lamp-on 420ms ease-out;
}

@keyframes lamp-on {
  from {
    opacity: 0.18;
    box-shadow: 0 0 0 0 transparent;
  }
}

.msg {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.msg strong {
  font-size: var(--fs-title2);
  font-weight: 750;
  line-height: 1.3;
  letter-spacing: var(--tr-title2);
}

.signal.ok .msg strong { color: var(--ok-ink); }
.signal.caution .msg strong { color: var(--caution-ink); }
.signal.danger .msg strong { color: var(--danger-ink); }

.msg span {
  font-size: var(--fs-caption);
  letter-spacing: var(--tr-caption);
  color: var(--ink-2);
}

.reasons {
  list-style: none;
  margin: 12px 0 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.reasons li {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 10px 12px 10px 14px;
  border-radius: 12px;
  background: var(--surface);
  box-shadow: inset 4px 0 0 var(--ok), inset 0 0 0 1px var(--line);
}

.reasons li.caution { box-shadow: inset 4px 0 0 var(--caution), inset 0 0 0 1px var(--line); }
.reasons li.danger { box-shadow: inset 4px 0 0 var(--danger), inset 0 0 0 1px var(--line); }

.reasons .txt {
  font-size: var(--fs-body);
  font-weight: 650;
  line-height: 1.45;
}

.reasons .src {
  font-size: var(--fs-footnote);
  letter-spacing: var(--tr-footnote);
  color: var(--ink-3);
}

.calm {
  margin: 12px 0 0;
  font-size: var(--fs-body);
  line-height: 1.6;
  color: var(--ink-2);
}

.tiles {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  margin-top: 16px;
}

.tile {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 13px 12px 10px;
  border-radius: var(--radius);
  background: var(--surface);
  box-shadow: 0 0 0 1px var(--line);
  overflow: hidden;
}

.tile::before {
  content: '';
  position: absolute;
  inset: 0 0 auto 0;
  height: 3px;
  background: var(--line);
}

.tile.ok::before { background: var(--ok); }
.tile.caution::before { background: var(--caution); }
.tile.danger::before { background: var(--danger); }
.tile.night::before { background: var(--night); }

.t-title {
  font-size: var(--fs-caption);
  font-weight: 650;
  letter-spacing: var(--tr-caption);
  color: var(--ink-2);
}

.t-value {
  font-size: var(--fs-title2);
  font-weight: 750;
  line-height: 1.3;
  letter-spacing: var(--tr-title2);
  font-variant-numeric: tabular-nums;
}

.tile.caution .t-value { color: var(--caution-text); }
.tile.danger .t-value { color: var(--danger-text); }

.t-note {
  font-size: var(--fs-caption);
  line-height: 1.45;
  color: var(--ink-2);
}

.t-foot,
.t-src {
  font-size: var(--fs-footnote);
  letter-spacing: var(--tr-footnote);
  line-height: 1.4;
  color: var(--ink-3);
}

.t-src {
  margin-top: 4px;
}

.block {
  margin-top: 26px;
}

.block h2 {
  margin: 0 0 8px;
  font-size: var(--fs-title2);
  font-weight: 750;
  line-height: 1.3;
  letter-spacing: var(--tr-title2);
}

.trail-sum {
  margin: 0 0 8px;
  font-size: var(--fs-body);
  color: var(--ink-2);
  font-variant-numeric: tabular-nums;
}

.trail-sum b {
  color: var(--ink);
}

.trail-sum b.warn {
  color: var(--warn-text);
}

.risks {
  list-style: none;
  margin: 0 0 8px;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.risks li {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  padding: 8px 11px;
  border-radius: 10px;
  background: var(--risk-bg);
  font-size: var(--fs-callout);
  color: var(--risk-ink);
}

.risks small {
  flex: none;
  font-size: var(--fs-caption);
  color: var(--risk-ink-2);
  font-variant-numeric: tabular-nums;
}

.hint {
  margin: 0;
  font-size: var(--fs-callout);
  line-height: 1.5;
  color: var(--ink-3);
}

.src-line {
  margin: 6px 0 0;
  font-size: var(--fs-footnote);
  letter-spacing: var(--tr-footnote);
  color: var(--ink-3);
}

.desc {
  margin: 0;
  font-size: var(--fs-body);
  line-height: 1.75;
  color: var(--ink-2);
}

.disclaimer {
  margin-top: 28px;
  padding-top: 14px;
  border-top: 1px solid var(--line);
  font-size: var(--fs-caption);
  letter-spacing: var(--tr-caption);
  line-height: 1.6;
  color: var(--ink-3);
}
</style>
