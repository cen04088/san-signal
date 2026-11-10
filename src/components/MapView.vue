<script setup>
import { markRaw, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import L from 'leaflet'
import { decodePolyline } from '../lib/polyline.js'
import { reducedMotion } from '../lib/motion.js'

const props = defineProps({
  mountains: { type: Array, required: true },
  verdicts: { type: Object, required: true },
  selectedId: { type: String, default: null },
  trail: { type: Object, default: null },
  userPos: { type: Object, default: null },
  // 패널에 가려지는 지도 영역(px). 산·등산로는 이 영역을 피해서 보여준다.
  insets: { type: Object, default: () => ({ top: 0, right: 0, bottom: 0, left: 0 }) },
  desktop: Boolean,
})
const emit = defineEmits(['select'])

// Leaflet SVG 속성에는 CSS 변수를 못 쓰므로 hex로 둔다 (styles.css와 같은 값)
// 등산로는 Uber의 경로선처럼 검은 선(어두운 화면에서는 흰 선)으로 그리고, 색은 위험·통제에만 쓴다
const LIGHT = {
  signal: ['#1f9d55', '#e0a100', '#d9423b'],
  noData: '#9a9a9a',
  ring: '#ffffff',
  activeRing: '#141414',
  trail: '#141414',
  risk: '#e07a00',
  ctrl: '#d9423b',
  closed: '#8a8a8a',
}
const DARK = {
  signal: ['#34b46a', '#f0b429', '#ef5b52'],
  noData: '#6f6f6f',
  ring: '#141414',
  activeRing: '#ffffff',
  trail: '#f2f2f2',
  risk: '#ff9a2e',
  ctrl: '#ef5b52',
  closed: '#8f8f8f',
}
const KOREA = [[33.0, 125.0], [38.7, 129.7]]
const EDGE = 24 // 가려지는 영역 밖으로 더 띄울 여백

const darkMq = matchMedia('(prefers-color-scheme: dark)')
let palette = darkMq.matches ? DARK : LIGHT

const el = ref(null)
let map
let markerLayer
let trailLayer
let userLayer
const markers = new Map()

function colorFor(id) {
  const v = props.verdicts[id]
  if (!v || !v.hasLive) return palette.noData
  return palette.signal[v.level]
}

function styleFor(id) {
  const active = id === props.selectedId
  return {
    radius: active ? 11 : 7,
    color: active ? palette.activeRing : palette.ring,
    weight: active ? 3 : 2,
    fillColor: colorFor(id),
    fillOpacity: 1,
  }
}

function fitOptions(maxZoom) {
  const i = props.insets
  const size = map.getSize()
  const tl = [i.left + EDGE, i.top + EDGE]
  const br = [i.right + EDGE, i.bottom + EDGE]
  // 가려지는 영역을 빼고 남는 지도가 너무 작으면(창이 아주 작을 때) 그 방향 여백은 무시한다
  if (size.x - tl[0] - br[0] < 120) tl[0] = br[0] = EDGE
  if (size.y - tl[1] - br[1] < 120) tl[1] = br[1] = EDGE
  return { paddingTopLeft: tl, paddingBottomRight: br, maxZoom }
}

// 지도 영역 크기가 0이면(숨은 탭 등) Leaflet이 좌표를 NaN으로 계산해 예외를 던진다.
// 그때는 목적지만 기억해 두고, 크기가 생기면(ResizeObserver) 바로 맞춘다.
let pending = null

function sized() {
  const size = map.getSize()
  return size.x >= 50 && size.y >= 50
}

function flushPending() {
  if (!pending || !sized()) return
  const [bounds, maxZoom] = pending
  pending = null
  map.fitBounds(bounds, { ...fitOptions(maxZoom), animate: false })
}

// 산을 고르거나 목록으로 돌아올 때 지도가 그 자리로 날아간다. 움직임 줄이기 설정이면 바로 바꾼다.
function moveTo(bounds, maxZoom, animate = true) {
  if (!sized()) {
    pending = [bounds, maxZoom]
    return
  }
  pending = null
  try {
    if (!animate || reducedMotion()) map.fitBounds(bounds, { ...fitOptions(maxZoom), animate: false })
    else map.flyToBounds(bounds, { ...fitOptions(maxZoom), duration: 0.6 })
  } catch {
    pending = [bounds, maxZoom]
  }
}

function drawMarkers() {
  markerLayer.clearLayers()
  markers.clear()
  for (const m of props.mountains) {
    // 점을 직접 누르면 지도 click으로 번지지 않게 한다 (아래 nearestTap과 겹치지 않도록)
    const marker = L.circleMarker([m.lat, m.lng], { ...styleFor(m.id), bubblingMouseEvents: false })
      .bindTooltip(m.name, { direction: 'top', offset: [0, -8], className: 'mountain-tip' })
      .on('click', () => emit('select', m.id))
    marker.addTo(markerLayer)
    markers.set(m.id, marker)
  }
}

// 산 점은 지름 14px라 손가락으로 정확히 누르기 어렵다.
// 점 밖을 눌러도 이 거리 안에 산이 있으면 가장 가까운 산을 고른다.
const TAP_SLOP = { touch: 24, mouse: 10 }

function nearestTap(e) {
  const slop = props.desktop ? TAP_SLOP.mouse : TAP_SLOP.touch
  let best = null
  let bestD = slop
  for (const m of props.mountains) {
    const p = map.latLngToContainerPoint([m.lat, m.lng])
    const d = p.distanceTo(e.containerPoint)
    if (d <= bestD) {
      best = m
      bestD = d
    }
  }
  if (best) emit('select', best.id)
}

function restyle() {
  for (const [id, marker] of markers) {
    marker.setStyle(styleFor(id))
    if (id === props.selectedId) marker.bringToFront()
  }
}

function segmentStyle(s) {
  if (s.closed) return { color: palette.closed, weight: 3, dashArray: '4 6', opacity: 0.9 }
  if (s.ctrl) return { color: palette.ctrl, weight: 3, dashArray: '6 5', opacity: 0.95 }
  if (s.risk) return { color: palette.risk, weight: 4, opacity: 0.95 }
  return { color: palette.trail, weight: 3, opacity: 0.8 }
}

function escapeHtml(text) {
  return String(text).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c])
}

function popupFor(s) {
  const rows = [`<strong>${escapeHtml(s.n || '등산로 구간')}</strong>`]
  const facts = []
  if (s.km) facts.push(`${s.km}km`)
  if (s.up) facts.push(`오르막 ${s.up}분`)
  if (s.dn) facts.push(`내리막 ${s.dn}분`)
  if (facts.length) rows.push(facts.join(', '))
  if (s.closed) rows.push('<span class="pp closed">폐쇄 구간</span>')
  if (s.ctrl) rows.push('<span class="pp ctrl">통제 구간</span>')
  if (s.risk) rows.push(`<span class="pp risk">위험: ${escapeHtml(s.risk)}</span>`)
  if (s.mat) rows.push(`노면: ${escapeHtml(s.mat)}`)
  return rows.join('<br>')
}

function drawTrail(fly = true) {
  trailLayer.clearLayers()
  const m = props.mountains.find((x) => x.id === props.selectedId)
  if (!m) return
  const bounds = L.latLngBounds([[m.lat, m.lng]])
  // 위험·폐쇄 구간이 일반 구간 위에 오도록 일반 구간부터 그린다
  const segments = [...(props.trail?.segments || [])].sort((a, b) => Number(!!(a.risk || a.closed || a.ctrl)) - Number(!!(b.risk || b.closed || b.ctrl)))
  for (const s of segments) {
    for (const encoded of s.p) {
      const latlngs = decodePolyline(encoded)
      L.polyline(latlngs, { ...segmentStyle(s), bubblingMouseEvents: false }).bindPopup(popupFor(s)).addTo(trailLayer)
      latlngs.forEach((p) => bounds.extend(p))
    }
  }
  if (!fly) return
  if (segments.length) moveTo(bounds.pad(0.04), 14)
  else moveTo(L.latLng(m.lat, m.lng).toBounds(7000), 12)
}

function drawUser() {
  userLayer.clearLayers()
  if (!props.userPos) return
  L.circleMarker([props.userPos.lat, props.userPos.lng], {
    radius: 6, color: '#ffffff', weight: 2, fillColor: '#2f6fed', fillOpacity: 1,
  }).bindTooltip('내 위치', { direction: 'top', className: 'mountain-tip' }).addTo(userLayer)
}

function onScheme() {
  palette = darkMq.matches ? DARK : LIGHT
  restyle()
  if (props.selectedId) drawTrail(false)
}

// 데스크톱: 확대 버튼 + 오른쪽 아래 출처. 휴대폰: 두 손가락 확대, 시트가 아래를 덮으므로 출처는 위로.
// 창 크기가 바뀌어 화면 형태가 달라지면 다시 놓는다.
let zoomControl = null
let attribution = null
function placeControls() {
  zoomControl?.remove()
  attribution?.remove()
  zoomControl = props.desktop ? L.control.zoom({ position: 'topright' }).addTo(map) : null
  attribution = L.control.attribution({ position: props.desktop ? 'bottomright' : 'topright', prefix: false })
    .addAttribution('&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>')
    .addTo(map)
}

let resizeObserver
onMounted(() => {
  map = markRaw(L.map(el.value, {
    zoomControl: false,
    attributionControl: false,
    zoomSnap: 0.5,
    minZoom: 5,
    // 시트가 지도 아래 절반을 덮어도 한반도를 위쪽에 맞출 수 있게 넉넉히 잡는다
    maxBounds: [[18, 108], [48, 146]],
  }))
  map.setView([36.2, 127.8], 7) // 크기를 알기 전 임시 위치
  placeControls()
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 17 }).addTo(map)
  trailLayer = markRaw(L.layerGroup().addTo(map))
  markerLayer = markRaw(L.layerGroup().addTo(map))
  userLayer = markRaw(L.layerGroup().addTo(map))
  drawMarkers()
  map.on('click', nearestTap)
  if (props.selectedId) drawTrail()
  else moveTo(L.latLngBounds(KOREA), undefined, false)
  resizeObserver = new ResizeObserver(() => {
    map.invalidateSize()
    flushPending()
  })
  resizeObserver.observe(el.value)
  darkMq.addEventListener('change', onScheme)
})

onBeforeUnmount(() => {
  resizeObserver?.disconnect()
  darkMq.removeEventListener('change', onScheme)
  map?.remove()
})

watch(() => props.mountains, () => {
  if (!map) return
  drawMarkers()
  if (props.selectedId) drawTrail() // 주소(#m003)로 바로 들어온 경우
})
watch(() => props.verdicts, () => map && restyle())
watch(() => props.selectedId, (id, old) => {
  if (!map) return
  restyle()
  if (id) drawTrail()
  else if (old) {
    trailLayer.clearLayers()
    moveTo(L.latLngBounds(KOREA))
  }
})
watch(() => props.trail, () => map && props.selectedId && drawTrail())
watch(() => props.userPos, () => map && drawUser())
watch(() => props.desktop, () => map && placeControls())
</script>

<template>
  <div ref="el" class="map" role="application" aria-label="전국 산 신호등 지도" />
  <div v-if="selectedId && trail?.segments?.length" class="legend" aria-label="등산로 범례">
    <span><i class="ln normal" />등산로</span>
    <span><i class="ln risk" />위험구간</span>
    <span><i class="ln closed" />폐쇄</span>
  </div>
  <div v-else-if="!selectedId" class="legend" aria-label="신호 범례">
    <span><i class="pt ok" />좋음</span>
    <span><i class="pt caution" />주의</span>
    <span><i class="pt danger" />위험</span>
  </div>
</template>

<style scoped>
.map {
  position: absolute;
  inset: 0;
}

/* 지도 위에 뜬 흰 알약 */
.legend {
  position: absolute;
  top: calc(12px + env(safe-area-inset-top));
  left: 12px;
  z-index: 500;
  display: flex;
  align-items: center;
  gap: 12px;
  min-height: 36px;
  padding: 0 14px;
  font-size: var(--fs-caption);
  font-weight: 600;
  color: var(--ink);
  background: var(--surface);
  border-radius: var(--pill);
  box-shadow: var(--shadow-sm);
  pointer-events: none;
}

@media (min-width: 900px) {
  .legend {
    top: auto;
    bottom: 24px;
    left: calc(var(--panel-w) + var(--gap) * 3);
  }
}

.legend span {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.pt {
  width: 10px;
  height: 10px;
  border-radius: 50%;
}

.pt.ok { background: var(--ok); }
.pt.caution { background: var(--caution); }
.pt.danger { background: var(--danger); }

.ln {
  width: 18px;
  height: 0;
  border-top: 3px solid var(--trail);
}

.ln.risk {
  border-top: 4px solid var(--risk);
}

.ln.closed {
  border-top: 3px dashed var(--closed);
}
</style>
