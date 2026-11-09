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
      <p>
        산림청 <b>산불위험예보 · 산사태예측 · 산악기상</b> 실시간 데이터와 <b>등산로</b> 공간정보를 묶어
        전국 {{ mountains.length || 138 }}개 산의 산행 안전을 신호등으로 알려드려요.
      </p>
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
        지금은 해가 진 시간이에요. 신호등은 산불·산사태·기상만 반영해요 — 일출 {{ hhmm(nextSunrise) }} 이후 출발하세요.
      </p>
    </section>

    <div class="tools">
      <input
        v-model="query"
        type="search"
        placeholder="산 이름이나 지역 검색 (예: 북한산, 가평)"
        aria-label="산 검색"
      />
      <div class="chips">
        <button type="button" :class="{ on: filter === 'np' }" @click="toggleFilter('np')">국립공원</button>
        <button type="button" :class="{ on: sort === 'signal' }" @click="sort = 'signal'">위험 먼저</button>
        <button type="button" :class="{ on: sort === 'name' }" @click="sort = 'name'">가나다</button>
        <button type="button" :class="{ on: sort === 'near' }" @click="userPos ? (sort = 'near') : nearMe()">
          {{ locating ? '위치 확인 중…' : '내 주변' }}
        </button>
      </div>
    </div>

    <p v-if="loading" class="empty">불러오는 중…</p>
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
        활용 데이터: 산림청 국립산림과학원 산불위험예보정보 · 산림청 산사태예측정보 · 산림청 국립산림과학원 산악기상정보 ·
        산림청 산정보 서비스 · 산림청 등산로(산림공간정보). 각 데이터의 이용조건에 따라 출처를 표시합니다.
      </p>
      <p>
        신호등은 참고 정보예요. 현장 통제·기상 특보를 우선 확인하세요. 응급 상황은 <b>119</b>.
        · <a href="https://github.com/cen04088/san-signal" target="_blank" rel="noopener">소스 코드</a>
      </p>
    </footer>
  </div>
</template>

<style scoped>
.hero h1 {
  margin: 2px 0 6px;
  font-size: 24px;
  letter-spacing: -0.03em;
}

.hero p {
  margin: 0 0 14px;
  font-size: 14px;
  line-height: 1.6;
  color: var(--ink-2);
}

.hero b {
  color: var(--ink);
  font-weight: 650;
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
  gap: 2px;
  padding: 10px 12px;
  border-radius: var(--radius);
  border: 2px solid transparent;
  text-align: left;
}

.tally-btn .n {
  font-size: 24px;
  font-weight: 750;
  font-variant-numeric: tabular-nums;
  line-height: 1.1;
}

.tally-btn .l {
  font-size: 12.5px;
  font-weight: 600;
}

.tally-btn.ok { background: var(--ok-bg); color: #10613a; }
.tally-btn.caution { background: var(--caution-bg); color: #6b4e00; }
.tally-btn.danger { background: var(--danger-bg); color: #8a201b; }
.tally-btn.on { border-color: currentColor; }

.night {
  margin: 12px 0 0 !important;
  padding: 9px 12px;
  border-radius: 10px;
  background: #e6ebf3;
  color: #2a3a55 !important;
  font-size: 13px !important;
}

.tools {
  position: sticky;
  top: 54px;
  z-index: 3;
  margin: 16px -16px 6px;
  padding: 8px 16px;
  background: var(--bg);
}

.tools input {
  width: 100%;
  padding: 11px 14px;
  border: 1px solid var(--line);
  border-radius: 12px;
  background: var(--surface);
  font-size: 15px;
  outline: none;
}

.tools input:focus {
  border-color: var(--brand);
  box-shadow: 0 0 0 3px rgba(31, 107, 71, 0.15);
}

.chips {
  display: flex;
  gap: 6px;
  margin-top: 8px;
  overflow-x: auto;
}

.chips button {
  flex: none;
  padding: 6px 11px;
  border-radius: 999px;
  border: 1px solid var(--line);
  background: var(--surface);
  font-size: 13px;
  color: var(--ink-2);
}

.chips button.on {
  background: var(--ink);
  border-color: var(--ink);
  color: #fff;
}

.empty {
  color: var(--ink-3);
  font-size: 14px;
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
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: var(--surface);
  text-align: left;
  transition: border-color 0.15s, transform 0.15s;
}

.row:hover {
  border-color: #c5cfc7;
}

.row:active {
  transform: scale(0.99);
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
.sig.none { background: #9aa59e; }

.main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.name {
  font-size: 16px;
  font-weight: 700;
  letter-spacing: -0.02em;
}

.name em {
  margin-left: 4px;
  padding: 1px 6px;
  border-radius: 6px;
  background: var(--surface-2);
  border: 1px solid var(--line);
  font-size: 11px;
  font-style: normal;
  font-weight: 600;
  color: var(--ink-2);
  vertical-align: 2px;
}

.sub {
  font-size: 12.5px;
  color: var(--ink-3);
}

.why {
  margin-top: 3px;
  font-size: 13px;
  color: var(--ink-2);
}

.why.caution { color: #8a6400; }
.why.danger { color: #b2302a; font-weight: 600; }

.elev {
  flex: none;
  font-size: 12.5px;
  color: var(--ink-3);
  font-variant-numeric: tabular-nums;
  margin-top: 3px;
}

.foot {
  margin-top: 28px;
  padding-top: 16px;
  border-top: 1px solid var(--line);
  font-size: 12px;
  line-height: 1.6;
  color: var(--ink-3);
}

.foot p {
  margin: 0 0 8px;
}

@media (min-width: 900px) {
  .tools {
    top: -18px;
    margin: 16px -20px 6px;
    padding: 10px 20px;
  }
}
</style>
