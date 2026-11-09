<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import MapView from './components/MapView.vue'
import MountainList from './components/MountainList.vue'
import MountainDetail from './components/MountainDetail.vue'
import SheetPanel from './components/SheetPanel.vue'
import { evaluate, hhmm, sunTimes } from './lib/verdict.js'
import { DESKTOP_QUERY, GAP, PANEL_W, detentPositions } from './lib/sheet.js'

const BASE = import.meta.env.BASE_URL

const mountains = ref([])
const quality = ref(null)
const stationNames = ref({})
const snapshot = ref(null)
const loadError = ref('')
const loading = ref(true)
const now = ref(new Date())
const selectedId = ref(readHash())
const trails = ref({})
const userPos = ref(null)

// 화면 배치
const desktopMq = matchMedia(DESKTOP_QUERY)
const desktop = ref(desktopMq.matches)
const vh = ref(window.innerHeight)
const detent = ref('half')
const sheet = ref(null)
const navAnim = ref('') // push: 상세로 들어감, pop: 목록으로 돌아옴. 첫 화면은 움직이지 않는다.
let listScroll = 0

// 지도에서 패널에 가려지는 영역. 지도는 이 영역을 빼고 산·등산로를 맞춰 보여준다.
const occlusion = computed(() => {
  if (desktop.value) return { top: 0, right: 0, bottom: 0, left: PANEL_W + GAP * 2 }
  return { top: 0, right: 0, bottom: vh.value - detentPositions(vh.value)[detent.value], left: 0 }
})

function readHash() {
  return decodeURIComponent(location.hash.replace(/^#\/?/, '')) || null
}

async function getJson(path) {
  const res = await fetch(BASE + path)
  if (!res.ok) throw new Error(`${path}: ${res.status}`)
  return res.json()
}

async function loadSnapshot() {
  try {
    // 10분 단위 캐시 버스터: 매시간 갱신되는 스냅샷을 브라우저가 오래 들고 있지 않게
    snapshot.value = await getJson(`live/snapshot.json?v=${Math.floor(Date.now() / 600000)}`)
  } catch {
    snapshot.value = null
  }
}

function onResize() {
  vh.value = window.innerHeight
  desktop.value = desktopMq.matches
}

function onKey(e) {
  if (e.key === 'Escape' && selectedId.value && !e.target.matches?.('input, textarea')) select(null)
}

let clock
let refresher
onMounted(async () => {
  window.addEventListener('hashchange', onHash)
  window.addEventListener('resize', onResize)
  window.addEventListener('keydown', onKey)
  try {
    const [m, s] = await Promise.all([getJson('data/mountains.json'), getJson('data/stations.json')])
    mountains.value = m.mountains
    quality.value = m.trail_quality
    stationNames.value = s
  } catch {
    loadError.value = '산 목록을 불러오지 못했어요. 잠시 후 다시 열어 주세요.'
  }
  await loadSnapshot()
  loading.value = false
  clock = setInterval(() => (now.value = new Date()), 60e3)
  refresher = setInterval(loadSnapshot, 15 * 60e3)
})

onBeforeUnmount(() => {
  clearInterval(clock)
  clearInterval(refresher)
  window.removeEventListener('hashchange', onHash)
  window.removeEventListener('resize', onResize)
  window.removeEventListener('keydown', onKey)
})

// 선택 바꾸기: 화면 전환 방향, 목록 스크롤 위치 복원, 모바일 시트 높이를 함께 처리한다
function applySelection(id) {
  if (id === selectedId.value) return
  const scroller = sheet.value?.scroller
  if (!selectedId.value && scroller) listScroll = scroller.scrollTop
  navAnim.value = id ? 'push' : 'pop'
  selectedId.value = id
  // 산을 고르면 지도에 등산로가 보이도록 시트를 중간 높이로
  if (id && !desktop.value) detent.value = 'half'
  nextTick(() => {
    if (scroller) scroller.scrollTop = id ? 0 : listScroll
  })
}

function select(id) {
  if (id === selectedId.value) return
  if (id) location.hash = id
  else history.pushState('', document.title, location.pathname + location.search)
  applySelection(id)
}

function onHash() {
  applySelection(readHash())
}

const verdicts = computed(() => {
  const ctx = { snapshot: snapshot.value, stationNames: stationNames.value, now: now.value }
  return Object.fromEntries(mountains.value.map((m) => [m.id, evaluate(m, ctx)]))
})

const selected = computed(() => mountains.value.find((m) => m.id === selectedId.value) || null)

watch(selected, async (m) => {
  if (!m || !m.trails?.segments || trails.value[m.id]) return
  try {
    const data = await getJson(`data/trails/${m.id}.json`)
    trails.value = { ...trails.value, [m.id]: data }
  } catch {
    trails.value = { ...trails.value, [m.id]: { segments: [] } }
  }
}, { immediate: true })

const generatedAt = computed(() => (snapshot.value ? new Date(snapshot.value.generated_at) : null))
const staleHours = computed(() => (generatedAt.value ? (now.value - generatedAt.value) / 3600e3 : null))
const seoulSun = computed(() => sunTimes(now.value, 37.57, 126.98))
const isNight = computed(() => now.value < seoulSun.value.sunrise || now.value > seoulSun.value.sunset)
const nextSunrise = computed(() => {
  const tomorrow = sunTimes(new Date(now.value.getTime() + 86400e3), 37.57, 126.98)
  return now.value > seoulSun.value.sunset ? tomorrow.sunrise : seoulSun.value.sunrise
})

function locate() {
  if (!navigator.geolocation) return
  navigator.geolocation.getCurrentPosition(
    (pos) => (userPos.value = { lat: pos.coords.latitude, lng: pos.coords.longitude }),
    () => (userPos.value = null),
    { enableHighAccuracy: false, timeout: 8000, maximumAge: 600000 },
  )
}
</script>

<template>
  <div class="map-layer">
    <MapView
      :mountains="mountains"
      :verdicts="verdicts"
      :selected-id="selectedId"
      :trail="selected ? trails[selected.id] : null"
      :user-pos="userPos"
      :insets="occlusion"
      :desktop="desktop"
      @select="select"
    />
  </div>

  <SheetPanel ref="sheet" v-model:detent="detent" :desktop="desktop" :vh="vh">
    <template #header>
      <button class="brand" type="button" @click="select(null)" aria-label="산행 신호등, 전체 산 목록으로">
        <span class="lamp" aria-hidden="true"><i /><i /><i /></span>
        <span class="brand-text">
          <strong>산행 신호등</strong>
          <small>산림청 공공데이터로 보는 오늘의 산</small>
        </span>
      </button>
      <div v-if="generatedAt" class="stamp" :class="{ stale: staleHours > 3 }">
        <span class="dot" aria-hidden="true" />
        {{ hhmm(generatedAt) }} 기준
      </div>
    </template>

    <p v-if="loadError" class="notice danger">{{ loadError }}</p>
    <p v-else-if="!loading && !snapshot" class="notice">
      실시간 산림 데이터를 불러오지 못했어요. 등산로와 산 정보만 보여드려요.
    </p>
    <p v-else-if="staleHours > 3" class="notice">
      실시간 데이터가 {{ Math.floor(staleHours) }}시간 전 것이에요. 공공데이터 API 응답이 늦어지고 있어요.
    </p>

    <MountainDetail
      v-if="selected"
      :key="selected.id"
      class="view"
      :class="navAnim"
      :mountain="selected"
      :verdict="verdicts[selected.id]"
      :trail="trails[selected.id]"
      :quality="quality"
      @back="select(null)"
    />
    <MountainList
      v-show="!selected"
      class="view"
      :class="navAnim"
      :mountains="mountains"
      :verdicts="verdicts"
      :loading="loading"
      :night="isNight"
      :next-sunrise="nextSunrise"
      :user-pos="userPos"
      @select="select"
      @locate="locate"
    />
  </SheetPanel>
</template>

<style scoped>
.map-layer {
  position: fixed;
  inset: 0;
  z-index: 0;
  isolation: isolate;
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
  padding: 4px 6px 4px 0;
  border: 0;
  border-radius: 12px;
  background: none;
  text-align: left;
  transition: var(--press);
}

.brand:active {
  transform: scale(0.97);
}

.lamp {
  flex: none;
  display: inline-flex;
  flex-direction: column;
  gap: 2px;
  padding: 4px 3px;
  border-radius: 8px;
  background: var(--housing);
}

.lamp i {
  width: 7px;
  height: 7px;
  border-radius: 50%;
}

.lamp i:nth-child(1) { background: var(--danger); }
.lamp i:nth-child(2) { background: var(--caution); }
.lamp i:nth-child(3) { background: var(--ok); }

.brand-text {
  display: flex;
  flex-direction: column;
  min-width: 0;
  line-height: 1.25;
}

.brand-text strong {
  font-size: var(--fs-headline);
  font-weight: 750;
  letter-spacing: var(--tr-headline);
}

.brand-text small {
  font-size: var(--fs-footnote);
  letter-spacing: var(--tr-footnote);
  color: var(--ink-3);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.stamp {
  flex: none;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px 10px;
  border-radius: 999px;
  background: var(--surface);
  box-shadow: 0 0 0 1px var(--line);
  font-size: var(--fs-caption);
  font-weight: 600;
  letter-spacing: var(--tr-caption);
  font-variant-numeric: tabular-nums;
  color: var(--ink-2);
}

.dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--ok);
  box-shadow: 0 0 0 3px var(--ok-bg);
}

.stamp.stale .dot {
  background: var(--caution);
  box-shadow: 0 0 0 3px var(--caution-bg);
}

.notice {
  margin: 0 0 12px;
  padding: 10px 12px;
  border-radius: 12px;
  font-size: var(--fs-callout);
  background: var(--caution-bg);
  color: var(--caution-ink);
}

.notice.danger {
  background: var(--danger-bg);
  color: var(--danger-ink);
}
</style>
