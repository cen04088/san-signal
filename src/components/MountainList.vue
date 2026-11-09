<script setup>
import { computed, ref, watch } from 'vue'
import { headline, hhmm, LEVEL_META } from '../lib/verdict.js'

const props = defineProps({
  mountains: { type: Array, required: true },
  verdicts: { type: Object, required: true },
  loading: Boolean,
  night: Boolean,
  nextSunrise: { type: Date, default: null },
  userPos: { type: Object, default: null },
})
const emit = defineEmits(['select', 'locate'])

const query = ref('')
const filter = ref('all') // all | 0 | 1 | 2 | np
const sort = ref('signal') // signal | near | name
const locating = ref(false)

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
  if (filter.value === 'np') list = list.filter(({ m }) => m.national_park)
  else if (filter.value !== 'all') list = list.filter(({ v }) => v?.hasLive && v.level === Number(filter.value))
  const byName = (a, b) => a.m.name.localeCompare(b.m.name, 'ko')
  if (sort.value === 'near' && props.userPos) list.sort((a, b) => a.km - b.km)
  else if (sort.value === 'name') list.sort(byName)
  else list.sort((a, b) => (b.v?.level ?? -1) - (a.v?.level ?? -1) || (b.v?.reasons.length ?? 0) - (a.v?.reasons.length ?? 0) || byName(a, b))
  return list
})

function toggleFilter(key) {
  filter.value = filter.value === key ? 'all' : key
}

function nearMe() {
  locating.value = true
  emit('locate')
}

watch(() => props.userPos, (pos) => {
  locating.value = false
  if (pos) sort.value = 'near'
})
</script>

<template>
  <div class="list-view">
    <section class="hero">
      <h1>오늘, 이 산 가도 될까?</h1>
      <div class="tally" role="group" aria-label="신호별로 보기">
        <button
          v-for="(meta, level) in LEVEL_META"
          :key="meta.key"
          type="button"
          :class="['tally-btn', meta.key, { on: filter === String(level) }]"
          :aria-pressed="filter === String(level)"
          @click="toggleFilter(String(level))"
        >
          <span class="n">{{ loading ? '–' : counts[level] }}</span>
          <span class="l">{{ meta.label }}</span>
        </button>
      </div>
      <p v-if="night" class="night">
        지금은 해가 진 시간이라 일몰 항목은 빼고 판정했어요. 일출 {{ hhmm(nextSunrise) }} 이후에 출발하세요.
      </p>
      <p class="lead">
        산림청 산불위험예보, 산사태예측, 산악기상 관측값을 매시간 받아
        전국 {{ mountains.length || 138 }}개 산을 좋음·주의·위험으로 나눠요.
      </p>
    </section>

    <div class="tools">
      <input
        v-model="query"
        type="search"
        enterkeyhint="search"
        placeholder="산 이름이나 지역 (예: 북한산, 가평)"
        aria-label="산 검색"
      />
      <div class="chips">
        <button type="button" :class="{ on: filter === 'np' }" :aria-pressed="filter === 'np'" @click="toggleFilter('np')">국립공원</button>
        <button type="button" :class="{ on: sort === 'signal' }" :aria-pressed="sort === 'signal'" @click="sort = 'signal'">위험 먼저</button>
        <button type="button" :class="{ on: sort === 'name' }" :aria-pressed="sort === 'name'" @click="sort = 'name'">가나다</button>
        <button type="button" :class="{ on: sort === 'near' }" :aria-pressed="sort === 'near'" @click="userPos ? (sort = 'near') : nearMe()">
          {{ locating ? '위치 확인 중' : '내 주변' }}
        </button>
      </div>
    </div>

    <p v-if="loading" class="empty">불러오는 중</p>
    <p v-else-if="!rows.length" class="empty">조건에 맞는 산이 없어요.</p>

    <ul class="rows">
      <li v-for="{ m, v, km } in rows" :key="m.id">
        <button type="button" class="row" @click="emit('select', m.id)">
          <span class="sig" :class="v?.hasLive ? LEVEL_META[v.level].key : 'none'" aria-hidden="true" />
          <span class="main">
            <span class="name">
              {{ m.name }}
              <em v-if="m.national_park">국립공원</em>
            </span>
            <span class="sub">
              {{ m.region }}<template v-if="km != null"> · {{ km < 10 ? km.toFixed(1) : Math.round(km) }}km</template>
            </span>
            <span v-if="v" class="why" :class="LEVEL_META[v.level].key">{{ headline(v) }}</span>
          </span>
          <span class="elev" v-if="m.elevation_m">{{ m.elevation_m.toLocaleString() }}m</span>
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
  margin: 4px 0 12px;
  font-size: var(--fs-title);
  font-weight: 750;
  line-height: 1.2;
  letter-spacing: var(--tr-title);
}

.tally {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
}

.tally-btn {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 1px;
  padding: 10px 12px 9px;
  border-radius: var(--radius);
  border: 0;
  box-shadow: inset 0 0 0 2px transparent;
  text-align: left;
  transition: var(--press), box-shadow 120ms ease;
}

.tally-btn:active {
  transform: scale(0.97);
}

.tally-btn .n {
  font-size: var(--fs-title);
  font-weight: 750;
  letter-spacing: var(--tr-title);
  font-variant-numeric: tabular-nums;
  line-height: 1.1;
}

.tally-btn .l {
  font-size: var(--fs-caption);
  font-weight: 650;
  letter-spacing: var(--tr-caption);
}

.tally-btn.ok { background: var(--ok-bg); color: var(--ok-ink); }
.tally-btn.caution { background: var(--caution-bg); color: var(--caution-ink); }
.tally-btn.danger { background: var(--danger-bg); color: var(--danger-ink); }
.tally-btn.on { box-shadow: inset 0 0 0 2px currentColor; }

.night {
  margin: 10px 0 0;
  padding: 9px 12px;
  border-radius: 12px;
  background: var(--night-bg);
  color: var(--night-ink);
  font-size: var(--fs-callout);
  line-height: 1.5;
}

.lead {
  margin: 12px 0 0;
  font-size: var(--fs-callout);
  line-height: 1.6;
  color: var(--ink-2);
}

/* 내용이 이 줄 밑으로 흐려지며 지나간다 (구분선 대신) */
.tools {
  position: sticky;
  top: 0;
  z-index: 3;
  margin: 14px calc(-1 * var(--pad)) 4px;
  padding: 8px var(--pad);
  background: var(--material);
  -webkit-backdrop-filter: blur(20px) saturate(180%);
  backdrop-filter: blur(20px) saturate(180%);
}

.tools input {
  width: 100%;
  padding: 10px 14px;
  border: 0;
  border-radius: 12px;
  background: var(--surface);
  box-shadow: 0 0 0 1px var(--line);
  font-size: 1rem; /* 16px 미만이면 iOS가 입력할 때 화면을 확대한다 */
  outline: none;
  transition: box-shadow 120ms ease;
}

.tools input::placeholder {
  color: var(--ink-3);
}

.tools input:focus {
  box-shadow: 0 0 0 2px var(--brand);
}

.chips {
  display: flex;
  gap: 6px;
  margin-top: 8px;
  overflow-x: auto;
  scrollbar-width: none;
}

.chips::-webkit-scrollbar {
  display: none;
}

.chips button {
  flex: none;
  padding: 6px 12px;
  border-radius: 999px;
  border: 0;
  background: var(--surface);
  box-shadow: inset 0 0 0 1px var(--line);
  font-size: var(--fs-callout);
  font-weight: 550;
  color: var(--ink-2);
  transition: var(--press), background-color 120ms ease, color 120ms ease;
}

.chips button:active {
  transform: scale(0.95);
}

.chips button.on {
  background: var(--ink);
  box-shadow: none;
  color: var(--on-ink);
}

.empty {
  color: var(--ink-3);
  font-size: var(--fs-body);
  text-align: center;
  padding: 24px 0;
}

.rows {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.row {
  width: 100%;
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 12px 14px;
  border: 0;
  border-radius: var(--radius);
  background: var(--surface);
  box-shadow: 0 0 0 1px var(--line);
  text-align: left;
  transition: var(--press), box-shadow 120ms ease;
}

/* 넓은 면은 덜 줄어든다 */
.row:active {
  transform: scale(0.985);
}

@media (hover: hover) {
  .row:hover {
    box-shadow: 0 0 0 1px var(--ink-3);
  }
}

.sig {
  flex: none;
  width: 14px;
  height: 14px;
  margin-top: 4px;
  border-radius: 50%;
  box-shadow: 0 0 0 4px var(--surface-2);
}

.sig.ok { background: var(--ok); box-shadow: 0 0 0 4px var(--ok-bg); }
.sig.caution { background: var(--caution); box-shadow: 0 0 0 4px var(--caution-bg); }
.sig.danger { background: var(--danger); box-shadow: 0 0 0 4px var(--danger-bg); }
.sig.none { background: var(--ink-3); }

.main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.name {
  font-size: var(--fs-headline);
  font-weight: 700;
  line-height: 1.35;
  letter-spacing: var(--tr-headline);
}

.name em {
  margin-left: 4px;
  padding: 1px 6px;
  border-radius: 6px;
  background: var(--surface-2);
  box-shadow: inset 0 0 0 1px var(--line);
  font-size: var(--fs-footnote);
  font-style: normal;
  font-weight: 600;
  letter-spacing: var(--tr-footnote);
  color: var(--ink-2);
  vertical-align: 2px;
}

.sub {
  font-size: var(--fs-caption);
  letter-spacing: var(--tr-caption);
  color: var(--ink-3);
}

.why {
  margin-top: 3px;
  font-size: var(--fs-callout);
  line-height: 1.45;
  color: var(--ink-2);
}

.why.caution { color: var(--caution-text); }
.why.danger { color: var(--danger-text); font-weight: 600; }

.elev {
  flex: none;
  margin-top: 3px;
  font-size: var(--fs-caption);
  color: var(--ink-3);
  font-variant-numeric: tabular-nums;
}

.foot {
  margin-top: 28px;
  padding-top: 16px;
  border-top: 1px solid var(--line);
  font-size: var(--fs-caption);
  letter-spacing: var(--tr-caption);
  line-height: 1.6;
  color: var(--ink-3);
}

.foot p {
  margin: 0 0 8px;
}
</style>
