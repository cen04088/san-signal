<script setup>
import { computed, ref } from 'vue'
import { PhArrowLeft, PhExport } from '@phosphor-icons/vue'
import { hhmm, hoursText, LEVEL_META, OK } from '../lib/verdict.js'
import SignalIcon from './SignalIcon.vue'

const props = defineProps({
  mountain: { type: Object, required: true },
  verdict: { type: Object, required: true },
  trail: { type: Object, default: null },
})
const emit = defineEmits(['back'])

const meta = computed(() => LEVEL_META[props.verdict.level])
const m = computed(() => props.mountain)
const v = computed(() => props.verdict)

const walkText = computed(() => {
  const { walk_min: a, walk_max: b } = m.value
  if (!a) return ''
  return b && b !== a ? `${hoursText(a)}~${hoursText(b)}시간` : `약 ${hoursText(a)}시간`
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
    note: parts.join(', '),
    foot: `${w.label}${how} · ${w.at || ''} 관측`,
  }
})

const sunTile = computed(() => {
  const s = v.value.sun
  if (s.night) {
    return { state: 'night', value: `일출 ${hhmm(s.nextSunrise)}`, note: '해가 진 시간이에요. 야간 산행은 피하세요.' }
  }
  const late = s.minutesLeft < 30 ? 'danger' : s.startPassed ? 'caution' : 'ok'
  return {
    state: late,
    value: `일몰 ${hhmm(s.sunset)}`,
    note: s.startPassed ? `오늘 출발 권장 시각(${hhmm(s.latestStart)})이 지났어요` : `늦어도 ${hhmm(s.latestStart)}까지 출발`,
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

// 함께 갈 사람에게 이 산 주소를 보낸다. 공유 창이 없는 브라우저는 링크를 복사한다.
const copied = ref(false)
async function share() {
  const url = location.href
  const text = `${m.value.name} 오늘 산행 신호: ${v.value.hasLive ? meta.value.label : '자료 없음'}`
  if (navigator.share) {
    try {
      await navigator.share({ title: `${m.value.name} · 산행 신호등`, text, url })
    } catch {
      // 공유 창을 닫은 경우
    }
    return
  }
  const body = `${text}\n${url}`
  let ok = false
  try {
    await navigator.clipboard.writeText(body)
    ok = true
  } catch {
    ok = copyByTextarea(body) // 클립보드 권한이 없는 환경
  }
  copied.value = ok ? 'done' : 'fail'
  setTimeout(() => (copied.value = false), 2500)
}

function copyByTextarea(body) {
  const area = document.createElement('textarea')
  area.value = body
  area.setAttribute('readonly', '')
  area.style.cssText = 'position:fixed;top:0;left:0;opacity:0'
  document.body.appendChild(area)
  area.select()
  let ok = false
  try {
    ok = document.execCommand('copy')
  } catch {
    ok = false
  }
  area.remove()
  return ok
}

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
    <div class="topbar">
      <button type="button" class="btn-soft" @click="emit('back')">
        <PhArrowLeft :size="18" weight="bold" aria-hidden="true" />
        전체 산
      </button>
      <button type="button" class="btn-soft" @click="share">
        <PhExport :size="18" weight="bold" aria-hidden="true" />
        <span aria-live="polite">{{ copied === 'done' ? '링크 복사됨' : copied === 'fail' ? '주소창 링크를 복사하세요' : '공유' }}</span>
      </button>
    </div>

    <header class="head">
      <h1>{{ m.name }}</h1>
      <p class="region">
        {{ m.region }}
        <em v-if="m.national_park">국립공원</em>
      </p>
      <dl v-if="m.elevation_m || walkText" class="facts">
        <div v-if="m.elevation_m"><dt>높이</dt><dd>{{ m.elevation_m.toLocaleString() }}m</dd></div>
        <div v-if="walkText"><dt>일반 코스</dt><dd>{{ walkText }}</dd></div>
      </dl>
    </header>

    <!-- 신호: 신호등 몸체처럼 검은 카드에 불 하나만 켠다 -->
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
      <li v-for="(r, i) in v.reasons" :key="i">
        <SignalIcon :level="r.level" :size="28" />
        <span class="r-main">
          <span class="txt">{{ r.text }}</span>
          <span class="src">{{ r.source }}</span>
        </span>
      </li>
    </ul>
    <p class="calm" v-else-if="v.hasLive">
      지금은 산불·산사태·기상 위험 신호가 없어요. 그래도 물과 간식, 보온 옷은 챙기세요.
    </p>

    <section class="tiles">
      <div v-for="t in tiles" :key="t.key" class="tile" :class="t.state">
        <span class="t-title"><i class="swatch" aria-hidden="true" />{{ t.title }}</span>
        <strong class="t-value">{{ t.value }}</strong>
        <span class="t-note" v-if="t.note">{{ t.note }}</span>
        <span class="t-foot" v-if="t.foot">{{ t.foot }}</span>
        <span class="t-src">{{ t.src }}</span>
      </div>
    </section>

    <section class="block">
      <h2>등산로</h2>
      <template v-if="m.trails?.segments">
        <dl class="facts trail-facts">
          <div><dt>구간</dt><dd>{{ m.trails.segments }}개</dd></div>
          <div><dt>총 길이</dt><dd>{{ m.trails.km }}km</dd></div>
          <div v-if="m.trails.risk"><dt>위험구간</dt><dd class="warn">{{ m.trails.risk }}</dd></div>
          <div v-if="m.trails.closed"><dt>폐쇄</dt><dd>{{ m.trails.closed }}</dd></div>
          <div v-if="m.trails.ctrl"><dt>통제</dt><dd class="warn">{{ m.trails.ctrl }}</dd></div>
        </dl>
        <ul v-if="riskNotes.length" class="risks">
          <li v-for="[text, n] in riskNotes" :key="text">
            <span>{{ text }}</span><small>{{ n }}구간</small>
          </li>
        </ul>
        <p class="hint">지도에서 등산로 선을 누르면 구간 이름, 소요 시간, 위험 정보가 나와요.</p>
      </template>
      <template v-else>
        <p class="hint">{{ noTrailText }}</p>
        <p v-if="m.national_park" class="hint">국립공원 탐방로는 국립공원공단 안내를 확인하세요.</p>
      </template>
    </section>

    <section class="block" v-if="m.description">
      <h2>산 소개</h2>
      <p class="desc">{{ m.description }}</p>
      <p v-if="m.description_source !== 'olla'" class="src-line">산림청 산정보 서비스</p>
    </section>

    <p class="disclaimer">
      신호등은 참고용이에요. 입산 통제나 기상 특보가 있으면 그 안내를 따르세요. 응급 상황에는 119에 전화하세요.
    </p>
  </article>
</template>

<style scoped>
.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.topbar .btn-soft:first-child {
  padding-left: 12px;
}

/* ── 머리: 큰 이름, 그 아래 지역, 숫자는 이름표가 붙은 칸으로 ── */
.head h1 {
  margin: 16px 0 2px;
  font-size: var(--fs-large);
  font-weight: 700;
  line-height: 1.2;
}

.region {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0;
  font-size: var(--fs-body);
  color: var(--ink-2);
}

.region em {
  padding: 2px 10px;
  border-radius: var(--pill);
  background: var(--soft);
  font-size: var(--fs-footnote);
  font-style: normal;
  font-weight: 600;
  color: var(--ink);
}

.facts {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 28px;
  margin: 14px 0 0;
}

.facts div {
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.facts dt {
  font-size: var(--fs-caption);
  color: var(--ink-3);
}

.facts dd {
  margin: 0;
  font-size: var(--fs-headline);
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}

.facts dd.warn {
  color: var(--warn-text);
}

/* ── 신호 카드: 검은 신호등 몸체 ── */
.signal {
  display: flex;
  align-items: center;
  gap: 18px;
  margin-top: 20px;
  padding: 18px;
  border-radius: var(--radius);
  background: var(--housing);
  color: #ffffff;
}

.lights {
  flex: none;
  display: flex;
  gap: 8px;
  padding: 8px 10px;
  border-radius: var(--pill);
  background: #000000;
}

.lights i {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: #3a3a3a;
  transition: background-color 200ms ease, transform 200ms ease;
}

.lights i.on {
  animation: lamp-on 420ms cubic-bezier(0.2, 0.8, 0.2, 1);
}

.lights .r.on { background: #ef5b52; }
.lights .y.on { background: #f0b429; }
.lights .g.on { background: #34b46a; }

@keyframes lamp-on {
  from {
    transform: scale(0.6);
    opacity: 0.3;
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
  font-weight: 700;
  line-height: 1.3;
}

.msg span {
  font-size: var(--fs-caption);
  color: #bdbdbd;
  line-height: 1.45;
}

/* ── 판정 이유: 상자 없이 줄로 ── */
.reasons {
  list-style: none;
  margin: 8px 0 0;
  padding: 0;
}

.reasons li {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 12px 0;
}

.reasons li + li {
  border-top: 1px solid var(--line);
}

.r-main {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
  padding-top: 3px;
}

.txt {
  font-size: var(--fs-body);
  font-weight: 600;
  line-height: 1.45;
}

.src {
  font-size: var(--fs-caption);
  color: var(--ink-3);
}

.calm {
  margin: 12px 0 0;
  padding: 14px 16px;
  border-radius: var(--radius);
  background: var(--soft);
  font-size: var(--fs-callout);
  line-height: 1.55;
}

/* ── 4칸 요약: 회색 칸, 상태는 제목 앞 작은 색 점으로 ── */
.tiles {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  margin-top: 16px;
}

.tile {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 14px;
  border-radius: var(--radius);
  background: var(--soft);
  min-width: 0;
}

.t-title {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: var(--fs-caption);
  font-weight: 600;
  color: var(--ink-2);
}

.swatch {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--ink-3);
}

.tile.ok .swatch { background: var(--ok); }
.tile.caution .swatch { background: var(--caution); }
.tile.danger .swatch { background: var(--danger); }
.tile.none .swatch { background: transparent; box-shadow: inset 0 0 0 1.5px var(--ink-3); }
.tile.night .swatch { background: var(--ink); }

.t-value {
  margin-top: 4px;
  font-size: var(--fs-title2);
  font-weight: 700;
  line-height: 1.25;
  font-variant-numeric: tabular-nums;
}

.tile.caution .t-value { color: var(--caution-text); }
.tile.danger .t-value { color: var(--danger-text); }
.tile.none .t-value { color: var(--ink-3); }

.t-note {
  font-size: var(--fs-caption);
  line-height: 1.45;
  color: var(--ink-2);
}

.t-foot {
  font-size: var(--fs-footnote);
  line-height: 1.45;
  color: var(--ink-3);
}

.t-src {
  margin-top: 6px;
  font-size: var(--fs-footnote);
  color: var(--ink-3);
}

/* ── 아래 영역: 상자 없이 제목과 간격으로 나눈다 ── */
.block {
  margin-top: 28px;
}

.block h2 {
  margin: 0 0 8px;
  font-size: var(--fs-title2);
  font-weight: 700;
}

.trail-facts {
  margin: 0 0 4px;
}

.risks {
  list-style: none;
  margin: 12px 0 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.risks li {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 14px;
  border-radius: var(--radius);
  background: var(--soft);
  font-size: var(--fs-callout);
  font-weight: 600;
}

.risks small {
  flex: none;
  font-size: var(--fs-caption);
  font-weight: 600;
  color: var(--warn-text);
}

.hint {
  margin: 10px 0 0;
  font-size: var(--fs-callout);
  line-height: 1.55;
  color: var(--ink-2);
}

.desc {
  margin: 0;
  font-size: var(--fs-body);
  line-height: 1.7;
  white-space: pre-line;
}

.src-line {
  margin: 8px 0 0;
  font-size: var(--fs-caption);
  color: var(--ink-3);
}

.disclaimer {
  margin: 28px 0 0;
  padding-top: 16px;
  border-top: 1px solid var(--line);
  font-size: var(--fs-caption);
  line-height: 1.6;
  color: var(--ink-3);
}

@media (prefers-color-scheme: dark) {
  .signal {
    background: var(--housing-2);
  }
}

@media (prefers-reduced-motion: reduce) {
  .lights i.on {
    animation: none;
  }
}
</style>
