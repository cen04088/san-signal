<script setup>
import { markRaw, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import L from 'leaflet'
import { decodePolyline } from '../lib/polyline.js'

const props = defineProps({
  mountains: { type: Array, required: true },
  verdicts: { type: Object, required: true },
  selectedId: { type: String, default: null },
  trail: { type: Object, default: null },
  userPos: { type: Object, default: null },
})
const emit = defineEmits(['select'])

// Leaflet SVG 속성에는 CSS 변수를 못 쓰므로 hex로 둔다 (styles.css와 같은 값)
const COLORS = ['#1f9d55', '#e0a100', '#d9423b']
const NO_DATA = '#9aa59e'
const KOREA = [[33.0, 125.0], [38.7, 129.7]]

const el = ref(null)
let map
let markerLayer
let trailLayer
let userLayer
const markers = new Map()

function colorFor(id) {
  const v = props.verdicts[id]
  if (!v || !v.hasLive) return NO_DATA
  return COLORS[v.level]
}

function styleFor(id) {
  const active = id === props.selectedId
  return {
    radius: active ? 11 : 7,
    color: active ? '#15211a' : '#ffffff',
    weight: active ? 3 : 2,
    fillColor: colorFor(id),
    fillOpacity: 1,
  }
}

function drawMarkers() {
  markerLayer.clearLayers()
  markers.clear()
  for (const m of props.mountains) {
    const marker = L.circleMarker([m.lat, m.lng], styleFor(m.id))
      .bindTooltip(m.name, { direction: 'top', offset: [0, -8], className: 'mountain-tip' })
      .on('click', () => emit('select', m.id))
    marker.addTo(markerLayer)
    markers.set(m.id, marker)
  }
}

function restyle() {
  for (const [id, marker] of markers) {
    marker.setStyle(styleFor(id))
    if (id === props.selectedId) marker.bringToFront()
  }
}

function segmentStyle(s) {
  if (s.closed) return { color: '#6b746e', weight: 3, dashArray: '4 6', opacity: 0.9 }
  if (s.ctrl) return { color: '#d9423b', weight: 3, dashArray: '6 5', opacity: 0.95 }
  if (s.risk) return { color: '#e07a00', weight: 4, opacity: 0.95 }
  return { color: '#1f6b47', weight: 3, opacity: 0.85 }
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
  if (facts.length) rows.push(facts.join(' · '))
  if (s.closed) rows.push('<span style="color:#6b746e">폐쇄 구간</span>')
  if (s.ctrl) rows.push('<span style="color:#d9423b">통제 구간</span>')
  if (s.risk) rows.push(`<span style="color:#b35f00">위험: ${escapeHtml(s.risk)}</span>`)
  if (s.mat) rows.push(`노면: ${escapeHtml(s.mat)}`)
  return rows.join('<br>')
}

function drawTrail() {
  trailLayer.clearLayers()
  const m = props.mountains.find((x) => x.id === props.selectedId)
  if (!m) return
  const bounds = L.latLngBounds([[m.lat, m.lng]])
  // 위험·폐쇄 구간이 일반 구간 위에 오도록 일반 구간부터 그린다
  const segments = [...(props.trail?.segments || [])].sort((a, b) => Number(!!(a.risk || a.closed || a.ctrl)) - Number(!!(b.risk || b.closed || b.ctrl)))
  for (const s of segments) {
    for (const encoded of s.p) {
      const latlngs = decodePolyline(encoded)
      L.polyline(latlngs, segmentStyle(s)).bindPopup(popupFor(s)).addTo(trailLayer)
      latlngs.forEach((p) => bounds.extend(p))
    }
  }
  if (segments.length) map.flyToBounds(bounds.pad(0.08), { duration: 0.6, maxZoom: 14 })
  else map.flyTo([m.lat, m.lng], 12, { duration: 0.6 })
}

function drawUser() {
  userLayer.clearLayers()
  if (!props.userPos) return
  L.circleMarker([props.userPos.lat, props.userPos.lng], {
    radius: 6, color: '#ffffff', weight: 2, fillColor: '#2f6fed', fillOpacity: 1,
  }).bindTooltip('내 위치', { direction: 'top', className: 'mountain-tip' }).addTo(userLayer)
}

let resizeObserver
onMounted(() => {
  map = markRaw(L.map(el.value, { zoomControl: false, preferCanvas: false, minZoom: 6, maxBounds: [[31, 122], [40.5, 133]] }))
  map.fitBounds(KOREA)
  L.control.zoom({ position: 'topright' }).addTo(map)
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 17,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
  }).addTo(map)
  trailLayer = markRaw(L.layerGroup().addTo(map))
  markerLayer = markRaw(L.layerGroup().addTo(map))
  userLayer = markRaw(L.layerGroup().addTo(map))
  drawMarkers()
  if (props.selectedId) drawTrail()
  resizeObserver = new ResizeObserver(() => map.invalidateSize())
  resizeObserver.observe(el.value)
})

onBeforeUnmount(() => {
  resizeObserver?.disconnect()
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
    map.flyToBounds(KOREA, { duration: 0.6 })
  }
})
watch(() => props.trail, () => map && props.selectedId && drawTrail())
watch(() => props.userPos, () => map && drawUser())
</script>

<template>
  <div ref="el" class="map" role="application" aria-label="전국 산 신호등 지도" />
  <div v-if="selectedId && trail?.segments?.length" class="legend" aria-label="등산로 범례">
    <span><i class="ln normal" />등산로</span>
    <span><i class="ln risk" />위험구간</span>
    <span><i class="ln closed" />폐쇄</span>
  </div>
  <div v-else-if="!selectedId" class="legend">
    <span><i class="pt" style="background: #1f9d55" />좋음</span>
    <span><i class="pt" style="background: #e0a100" />주의</span>
    <span><i class="pt" style="background: #d9423b" />위험</span>
  </div>
</template>

<style scoped>
.map {
  position: absolute;
  inset: 0;
}

.legend {
  position: absolute;
  left: 10px;
  bottom: 22px;
  z-index: 500;
  display: flex;
  gap: 10px;
  padding: 6px 10px;
  font-size: 12px;
  font-weight: 600;
  background: rgba(255, 255, 255, 0.94);
  border-radius: 10px;
  box-shadow: var(--shadow);
}

.legend span {
  display: inline-flex;
  align-items: center;
  gap: 5px;
}

.pt {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  border: 2px solid #fff;
  box-shadow: 0 0 0 1px rgba(0, 0, 0, 0.12);
}

.ln {
  width: 18px;
  height: 0;
  border-top: 3px solid #1f6b47;
}

.ln.risk {
  border-top: 4px solid #e07a00;
}

.ln.closed {
  border-top: 3px dashed #6b746e;
}
</style>
