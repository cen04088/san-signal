<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import MapView from './components/MapView.vue'
import MountainList from './components/MountainList.vue'
import MountainDetail from './components/MountainDetail.vue'
import { evaluate, hhmm, sunTimes } from './lib/verdict.js'

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
const panel = ref(null)

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

let clock
let refresher
onMounted(async () => {
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
  window.addEventListener('hashchange', onHash)
})

onBeforeUnmount(() => {
  clearInterval(clock)
  clearInterval(refresher)
  window.removeEventListener('hashchange', onHash)
})

function onHash() {
  selectedId.value = readHash()
}

const verdicts = computed(() => {
  const ctx = { snapshot: snapshot.value, stationNames: stationNames.value, now: now.value }
  return Object.fromEntries(mountains.value.map((m) => [m.id, evaluate(m, ctx)]))
})

const selected = computed(() => mountains.value.find((m) => m.id === selectedId.value) || null)

function select(id) {
  if (id === selectedId.value) return
  if (id) location.hash = id
  else history.pushState('', document.title, location.pathname + location.search)
  selectedId.value = id
  panel.value?.scrollTo?.({ top: 0 })
}

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
  <div class="app">
    <header class="top">
      <button class="brand" type="button" @click="select(null)" aria-label="산행 신호등 처음으로">
        <span class="lamp" aria-hidden="true"><i /><i /><i /></span>
        <span class="brand-text">
          <strong>산행 신호등</strong>
          <small>산림청 공공데이터로 보는 오늘의 산</small>
        </span>
      </button>
      <div class="stamp" v-if="generatedAt">
        <span class="dot" :class="{ stale: staleHours > 3 }" />
        {{ hhmm(generatedAt) }} 기준
      </div>
    </header>

    <main class="body">
      <section class="panel" ref="panel">
        <p v-if="loadError" class="notice danger">{{ loadError }}</p>
        <p v-else-if="!loading && !snapshot" class="notice">
          실시간 산림 데이터를 불러오지 못했어요. 등산로·산 정보만 보여드려요.
        </p>
        <p v-else-if="staleHours > 3" class="notice">
          실시간 데이터가 {{ Math.floor(staleHours) }}시간 전 것이에요. 공공데이터 API 응답이 늦어지고 있어요.
        </p>

        <MountainDetail
          v-if="selected"
          :mountain="selected"
          :verdict="verdicts[selected.id]"
          :trail="trails[selected.id]"
          :quality="quality"
          @back="select(null)"
        />
        <MountainList
          v-else
          :mountains="mountains"
          :verdicts="verdicts"
          :loading="loading"
          :night="isNight"
          :next-sunrise="nextSunrise"
          :user-pos="userPos"
          @select="select"
          @locate="locate"
        />
      </section>

      <section class="map-wrap">
        <MapView
          :mountains="mountains"
          :verdicts="verdicts"
          :selected-id="selectedId"
          :trail="selected ? trails[selected.id] : null"
          :user-pos="userPos"
          @select="select"
        />
      </section>
    </main>
  </div>
</template>

<style scoped>
.app {
  min-height: 100dvh;
  display: flex;
  flex-direction: column;
}

.top {
  position: sticky;
  top: 0;
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 16px;
  background: var(--ink);
  color: #fff;
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  background: none;
  border: 0;
  padding: 0;
  color: inherit;
  text-align: left;
}

.lamp {
  display: inline-flex;
  flex-direction: column;
  gap: 2px;
  padding: 4px 3px;
  border-radius: 8px;
  background: #0b130e;
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
  line-height: 1.2;
}

.brand-text strong {
  font-size: 17px;
  letter-spacing: -0.02em;
}

.brand-text small {
  font-size: 11.5px;
  color: #b9c6bd;
}

.stamp {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12.5px;
  color: #d5ded8;
  white-space: nowrap;
}

.dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--ok);
  box-shadow: 0 0 0 3px rgba(31, 157, 85, 0.25);
}

.dot.stale {
  background: var(--caution);
  box-shadow: 0 0 0 3px rgba(224, 161, 0, 0.25);
}

.body {
  flex: 1;
  display: flex;
  flex-direction: column-reverse;
}

.map-wrap {
  height: 40vh;
  min-height: 260px;
  position: sticky;
  top: 54px;
  z-index: 1;
}

.panel {
  position: relative;
  z-index: 2;
  background: var(--bg);
  padding: 14px 16px 40px;
}

.notice {
  margin: 0 0 12px;
  padding: 10px 12px;
  border-radius: 10px;
  font-size: 13px;
  background: var(--caution-bg);
  color: #6b4e00;
}

.notice.danger {
  background: var(--danger-bg);
  color: #8a201b;
}

@media (min-width: 900px) {
  .app {
    height: 100dvh;
  }

  .body {
    flex-direction: row;
    min-height: 0;
  }

  .panel {
    width: 430px;
    flex: none;
    overflow-y: auto;
    border-right: 1px solid var(--line);
    padding: 18px 20px 40px;
  }

  .map-wrap {
    position: relative;
    top: 0;
    flex: 1;
    height: auto;
  }
}
</style>
