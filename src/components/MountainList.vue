<script setup>
import { computed, ref, watch } from 'vue'
import { PhCaretRight, PhMagnifyingGlass, PhMoon, PhXCircle } from '@phosphor-icons/vue'
import { headline, hhmm, LEVEL_META } from '../lib/verdict.js'
import SignalIcon from './SignalIcon.vue'

const props = defineProps({
  mountains: { type: Array, required: true },
  verdicts: { type: Object, required: true },
  loading: Boolean,
  night: Boolean,
  nextSunrise: { type: Date, default: null },
  userPos: { type: Object, default: null },
  locateState: { type: String, default: 'idle' }, // idle | locating | denied | failed
})
const emit = defineEmits(['select', 'locate'])

const query = ref('')
const level = ref('all') // all | 0 | 1 | 2 (위 신호 칸으로 고른다)
const npOnly = ref(false) // 국립공원만. 신호 필터와 함께 쓸 수 있다
const sort = ref('signal') // signal | near | name
const locating = computed(() => props.locateState === 'locating')

const counts = computed(() => {
  const c = [0, 0, 0]
  for (const m of props.mountains) {
    const v = props.verdicts[m.id]
    if (v?.hasLive) c[v.level]++
  }
  return c
})

function distanceKm(a, b) {
  const r = Math.PI / 180
  const h = Math.sin(((b.lat - a.lat) * r) / 2) ** 2
    + Math.cos(a.lat * r) * Math.cos(b.lat * r) * Math.sin(((b.lng - a.lng) * r) / 2) ** 2
  return 2 * 6371 * Math.asin(Math.sqrt(h))
}

const rows = computed(() => {
  const q = query.value.trim().replace(/\s+/g, '')
  let list = props.mountains.map((m) => ({
    m,
    v: props.verdicts[m.id],
    km: props.userPos ? distanceKm(props.userPos, m) : null,
  }))
  if (q) list = list.filter(({ m }) => `${m.name}${m.region}`.replace(/\s+/g, '').includes(q))
  if (npOnly.value) list = list.filter(({ m }) => m.national_park)
  if (level.value !== 'all') list = list.filter(({ v }) => v?.hasLive && v.level === Number(level.value))
  const byName = (a, b) => a.m.name.localeCompare(b.m.name, 'ko')
  if (sort.value === 'near' && props.userPos) list.sort((a, b) => a.km - b.km)
  else if (sort.value === 'name') list.sort(byName)
  else list.sort((a, b) => (b.v?.level ?? -1) - (a.v?.level ?? -1) || (b.v?.reasons.length ?? 0) - (a.v?.reasons.length ?? 0) || byName(a, b))
  return list
})

function toggleLevel(key) {
  level.value = level.value === key ? 'all' : key
}

// 목록을 내려도 필터가 걸려 있는 줄 알 수 있게, 도구 줄 아래에 지금 조건을 적는다
const filterSummary = computed(() => {
  const parts = []
  if (query.value.trim()) parts.push(`'${query.value.trim()}'`)
  if (level.value !== 'all') parts.push(LEVEL_META[Number(level.value)].label)
  if (npOnly.value) parts.push('국립공원')
  return parts.length ? `${parts.join(', ')} ${rows.value.length}곳` : ''
})

function clearFilters() {
  query.value = ''
  level.value = 'all'
  npOnly.value = false
}

// 이유가 여러 개면 목록에서는 가장 나쁜 것 하나와 나머지 개수만 보여준다
function moreCount(v) {
  return Math.max(0, v.reasons.filter((r) => r.level > 0).length - 1)
}

function nearMe() {
  if (locating.value) return
  emit('locate')
}

watch(() => props.userPos, (pos) => {
  if (pos) sort.value = 'near'
})
</script>

<template>
  <div class="list-view">
    <section class="hero">
      <h1>오늘, 이 산 가도 될까?</h1>
      <div class="tally" role="group" aria-label="신호별로 보기">
        <button
          v-for="(meta, i) in LEVEL_META"
          :key="meta.key"
          type="button"
          :class="['tally-btn', meta.key, { on: level === String(i) }]"
          :aria-pressed="level === String(i)"
          @click="toggleLevel(String(i))"
        >
          <span class="n">{{ loading ? '-' : counts[i] }}</span>
          <span class="l"><i class="swatch" aria-hidden="true" />{{ meta.label }}</span>
        </button>
      </div>
      <p v-if="night" class="night">
        <PhMoon :size="18" weight="bold" aria-hidden="true" />
        <span>지금은 해가 진 시간이라 일몰 항목은 빼고 판정했어요. 일출 {{ hhmm(nextSunrise) }} 이후에 출발하세요.</span>
      </p>
      <p class="lead">
        산림청 산불위험예보, 산사태예측, 산악기상 관측값을 매시간 받아
        전국 {{ mountains.length || 138 }}개 산을 좋음·주의·위험으로 나눠요.
      </p>
    </section>

    <div class="tools">
      <div class="search">
        <PhMagnifyingGlass class="search-icon" :size="18" weight="bold" aria-hidden="true" />
        <input
          v-model="query"
          type="search"
          enterkeyhint="search"
          placeholder="산 이름이나 지역 (예: 북한산, 가평)"
          aria-label="산 검색"
        />
        <button v-if="query" type="button" class="clear" aria-label="검색어 지우기" @click="query = ''">
          <PhXCircle :size="20" weight="fill" aria-hidden="true" />
        </button>
      </div>
      <div class="chips">
        <button type="button" :class="{ on: npOnly }" :aria-pressed="npOnly" @click="npOnly = !npOnly">국립공원</button>
        <span class="sep" aria-hidden="true" />
        <span class="chip-label">정렬</span>
        <button type="button" :class="{ on: sort === 'signal' }" :aria-pressed="sort === 'signal'" @click="sort = 'signal'">위험 먼저</button>
        <button type="button" :class="{ on: sort === 'near' }" :aria-pressed="sort === 'near'" :aria-busy="locating" @click="userPos ? (sort = 'near') : nearMe()">
          {{ locating ? '위치 확인 중' : '가까운 순' }}
        </button>
        <button type="button" :class="{ on: sort === 'name' }" :aria-pressed="sort === 'name'" @click="sort = 'name'">가나다</button>
      </div>
      <p v-if="locateState === 'denied'" class="tool-note" role="status">
        위치 권한이 꺼져 있어요. 브라우저 설정에서 이 사이트의 위치를 허용하면 가까운 산부터 보여드려요.
      </p>
      <p v-else-if="locateState === 'failed'" class="tool-note" role="status">
        지금 위치를 확인하지 못했어요. 잠시 후 다시 눌러 주세요.
      </p>
      <p v-if="filterSummary" class="filter-line" role="status">
        <span>{{ filterSummary }}</span>
        <button type="button" class="btn-soft" @click="clearFilters">전체 보기</button>
      </p>
    </div>

    <ul v-if="loading" class="rows skeleton" aria-label="불러오는 중">
      <li v-for="n in 6" :key="n"><span class="row"><span class="sk-icon" /><span class="sk-lines"><i /><i /></span></span></li>
    </ul>
    <div v-else-if="!rows.length && mountains.length" class="empty">
      <p>조건에 맞는 산이 없어요.</p>
      <button type="button" class="btn-soft" @click="clearFilters">조건 지우기</button>
    </div>

    <ul v-else class="rows">
      <li v-for="{ m, v, km } in rows" :key="m.id">
        <button type="button" class="row" @click="emit('select', m.id)">
          <SignalIcon :level="v?.hasLive ? v.level : null" />
          <span class="main">
            <span class="name">
              {{ m.name }}
              <em v-if="m.national_park">국립공원</em>
              <span class="sr-only">, {{ v?.hasLive ? LEVEL_META[v.level].label : '자료 없음' }}</span>
            </span>
            <span v-if="v" class="why" :class="v.hasLive ? LEVEL_META[v.level].key : 'none'">
              {{ headline(v) }}<b v-if="moreCount(v)" class="more"> 외 {{ moreCount(v) }}가지</b>
            </span>
            <span class="sub">
              {{ m.region }}<template v-if="m.elevation_m">, {{ m.elevation_m.toLocaleString() }}m</template><template v-if="km != null">, {{ km < 10 ? km.toFixed(1) : Math.round(km) }}km</template>
            </span>
          </span>
          <PhCaretRight class="chev" :size="18" weight="bold" aria-hidden="true" />
        </button>
      </li>
    </ul>

    <footer class="foot">
      <p>
        데이터 출처: 산림청 국립산림과학원 산불위험예보정보, 산림청 산사태예측정보, 산림청 국립산림과학원 산악기상정보,
        산림청 산정보 서비스, 산림청 등산로(1:25,000) 공간정보. 지도는 OpenStreetMap.
      </p>
      <p>
        신호등은 참고용이에요. 입산 통제나 기상 특보가 있으면 그 안내를 따르세요. 응급 상황에는 <b>119</b>에 전화하세요.
        <a href="https://github.com/cen04088/san-signal" target="_blank" rel="noopener">소스 코드</a>
      </p>
    </footer>
  </div>
</template>

<style scoped>
.hero h1 {
  margin: 4px 0 16px;
  font-size: var(--fs-title);
  font-weight: 700;
  line-height: 1.25;
}

/* 신호별 개수: 회색 칸. 누르면 그 신호만 보며, 고른 칸은 검게 뒤집힌다 (Uber의 선택 표시) */
.tally {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
}

.tally-btn {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
  padding: 12px 14px;
  border: 0;
  border-radius: var(--radius);
  background: var(--soft);
  color: var(--ink);
  text-align: left;
  transition: var(--press), background-color 120ms ease, color 120ms ease;
}

.tally-btn:active {
  transform: scale(0.97);
}

.tally-btn.on {
  background: var(--ink);
  color: var(--on-ink);
}

.tally-btn .n {
  font-size: var(--fs-title);
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  line-height: 1.15;
}

.tally-btn .l {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: var(--fs-caption);
  font-weight: 600;
}

.swatch {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.tally-btn.ok .swatch { background: var(--ok); }
.tally-btn.caution .swatch { background: var(--caution); }
.tally-btn.danger .swatch { background: var(--danger); }

.night {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  margin: 12px 0 0;
  padding: 12px 14px;
  border-radius: var(--radius);
  background: var(--soft);
  font-size: var(--fs-callout);
  line-height: 1.5;
}

.night svg {
  flex: none;
  margin-top: 1px;
}

.lead {
  margin: 14px 0 0;
  font-size: var(--fs-callout);
  line-height: 1.6;
  color: var(--ink-2);
}

/* 검색·필터 줄: 목록을 내려도 위에 붙어 있다 */
.tools {
  position: sticky;
  top: 0;
  z-index: 3;
  margin: 16px calc(-1 * var(--pad)) 0;
  padding: 8px var(--pad) 10px;
  background: var(--bg);
}

.search {
  position: relative;
}

.search-icon {
  position: absolute;
  top: 50%;
  left: 16px;
  transform: translateY(-50%);
  color: var(--ink);
  pointer-events: none;
}

/* Uber의 'Where to?' 막대처럼 회색 알약 */
.tools input {
  width: 100%;
  min-height: 48px;
  padding: 0 44px;
  border: 0;
  border-radius: var(--pill);
  background: var(--soft);
  font-size: 1rem; /* 16px 미만이면 iOS가 입력할 때 화면을 확대한다 */
  font-weight: 500;
  outline: none;
  transition: box-shadow 120ms ease;
}

.tools input::placeholder {
  color: var(--ink-3);
  font-weight: 400;
}

.tools input:focus {
  box-shadow: inset 0 0 0 2px var(--ink);
}

/* 브라우저 기본 지우기 버튼 대신 아래 버튼을 쓴다 (iOS에는 기본 버튼이 없다) */
.tools input::-webkit-search-cancel-button {
  -webkit-appearance: none;
  appearance: none;
}

.clear {
  position: absolute;
  top: 0;
  right: 2px;
  width: 44px;
  height: 100%;
  display: grid;
  place-items: center;
  padding: 0;
  border: 0;
  background: none;
  color: var(--ink-3);
}

.clear:active {
  opacity: 0.6;
}

.chips {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 10px;
  overflow-x: auto;
  scrollbar-width: none;
}

.chips::-webkit-scrollbar {
  display: none;
}

.chips button {
  flex: none;
  min-height: 40px; /* 손가락으로 누르기 쉬운 높이 */
  padding: 0 14px;
  border-radius: var(--pill);
  border: 0;
  background: var(--soft);
  font-size: var(--fs-callout);
  font-weight: 600;
  color: var(--ink);
  transition: var(--press), background-color 120ms ease, color 120ms ease;
}

.chips button:active {
  transform: scale(0.96);
}

.chips button.on {
  background: var(--ink);
  color: var(--on-ink);
}

.sep {
  flex: none;
  width: 1px;
  height: 20px;
  margin: 0 2px;
  background: var(--line);
}

.chip-label {
  flex: none;
  font-size: var(--fs-caption);
  font-weight: 600;
  color: var(--ink-3);
}

.tool-note {
  margin: 10px 0 0;
  font-size: var(--fs-caption);
  line-height: 1.5;
  color: var(--caution-text);
}

.filter-line {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin: 10px 0 0;
  font-size: var(--fs-callout);
  font-weight: 600;
}

.filter-line .btn-soft {
  min-height: 32px;
  padding: 0 12px;
  font-size: var(--fs-caption);
}

.empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 32px 0;
  color: var(--ink-2);
  font-size: var(--fs-body);
}

.empty p {
  margin: 0;
}

/* 목록: 상자 없이 줄과 구분선만 (Uber의 목록 줄) */
.rows {
  list-style: none;
  margin: 4px 0 0;
  padding: 0;
}

.rows li + li .row::before {
  content: '';
  position: absolute;
  top: 0;
  left: 52px;
  right: 0;
  border-top: 1px solid var(--line);
}

.row {
  position: relative;
  width: 100%;
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 14px 0;
  border: 0;
  background: none;
  text-align: left;
  transition: var(--press);
}

.row:active {
  transform: scale(0.985);
}

@media (hover: hover) {
  .row:hover .name {
    text-decoration: underline;
    text-underline-offset: 3px;
  }
}

.main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.name {
  font-size: var(--fs-headline);
  font-weight: 600;
  line-height: 1.35;
}

.name em {
  margin-left: 6px;
  padding: 2px 8px;
  border-radius: var(--pill);
  background: var(--soft);
  font-size: var(--fs-footnote);
  font-style: normal;
  font-weight: 600;
  color: var(--ink-2);
  vertical-align: 2px;
}

.why {
  font-size: var(--fs-callout);
  line-height: 1.45;
  color: var(--ink-2);
}

.why.caution { color: var(--caution-text); }
.why.danger { color: var(--danger-text); font-weight: 600; }

.more {
  font-weight: 600;
  white-space: nowrap;
}

.sub {
  font-size: var(--fs-caption);
  color: var(--ink-3);
  font-variant-numeric: tabular-nums;
}

.chev {
  flex: none;
  color: var(--ink-3);
}

/* 불러오는 동안: 실제 줄과 같은 모양의 빈 자리 */
.skeleton .row {
  pointer-events: none;
}

.sk-icon {
  flex: none;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: var(--soft);
}

.sk-lines {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.sk-lines i {
  display: block;
  height: 12px;
  border-radius: var(--pill);
  background: var(--soft);
}

.sk-lines i:first-child { width: 40%; }
.sk-lines i:last-child { width: 70%; }

.foot {
  margin-top: 28px;
  padding-top: 16px;
  border-top: 1px solid var(--line);
  font-size: var(--fs-caption);
  line-height: 1.6;
  color: var(--ink-3);
}

.foot p {
  margin: 0 0 8px;
}

.foot a {
  color: var(--ink-2);
}
</style>
