<script setup>
// 모바일: 지도 위에 뜬 바텀 시트 (내림·중간·올림 세 위치).
//   - 손잡이·상단 줄을 끌면 손가락과 1:1로 따라오고, 놓을 때 속도로 멈출 위치를 예측해 스프링으로 붙는다.
//   - 움직이는 중에도 다시 잡을 수 있고, 위·아래 끝을 넘겨 끌면 고무줄처럼 버틴다.
//   - 올린 상태에서는 내용이 스크롤되고, 맨 위에서 아래로 끌면 시트가 내려간다.
// 데스크톱: 지도 왼쪽에 떠 있는 패널. 끌기 동작은 없다.
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { project, reducedMotion, rubberband, spring, VelocityTracker } from '../lib/motion.js'
import { detentPositions } from '../lib/sheet.js'

const props = defineProps({
  detent: { type: String, default: 'half' },
  desktop: Boolean,
  vh: { type: Number, required: true },
})
const emit = defineEmits(['update:detent'])

const sheet = ref(null)
const scroller = ref(null)
const settled = ref(props.detent) // 멈춰 있거나 향하고 있는 위치
const dragging = ref(false)
const scrolled = ref(false)

const positions = computed(() => detentPositions(props.vh))
const scrollable = computed(() => props.desktop || (settled.value === 'full' && !dragging.value))

let pos = 0
let anim = null
let suppressClickUntil = 0
const tracker = new VelocityTracker()

function setPos(y) {
  pos = y
  if (sheet.value) sheet.value.style.transform = `translate3d(0, ${y}px, 0)`
}

function stopAnim() {
  const v = anim?.velocity ?? 0
  anim?.stop()
  anim = null
  return v
}

function snap(detent, releaseVelocity) {
  const target = positions.value[detent]
  // 움직이는 중에 목표가 바뀌면 지금 속도를 이어받아 끊김 없이 방향을 튼다
  const carried = stopAnim()
  const v0 = releaseVelocity ?? carried
  settled.value = detent
  if (detent !== props.detent) emit('update:detent', detent)
  if (reducedMotion()) {
    setPos(target)
    return
  }
  // 던졌을 때만 살짝 튕기고, 그 밖에는 넘침 없이 멈춘다
  const flick = Math.abs(v0) > 600
  anim = spring({
    from: pos,
    to: target,
    velocity: v0,
    damping: flick ? 0.82 : 1,
    response: flick ? 0.32 : 0.38,
    onUpdate: setPos,
    onDone: () => (anim = null),
  })
}

function nearest(y) {
  let best = 'half'
  for (const [key, p] of Object.entries(positions.value)) {
    if (Math.abs(p - y) < Math.abs(positions.value[best] - y)) best = key
  }
  return best
}

// ── 끌기 공통 ──
let dragFromPos = 0
let dragFromY = 0

function beginDrag(clientY, t) {
  stopAnim()
  dragging.value = true
  dragFromPos = pos
  dragFromY = clientY
  tracker.reset()
  tracker.add(clientY, t)
}

function moveDrag(clientY, t) {
  tracker.add(clientY, t)
  const { full, peek } = positions.value
  let next = dragFromPos + (clientY - dragFromY)
  if (next < full) next = full - rubberband(full - next, props.vh)
  else if (next > peek) next = peek + rubberband(next - peek, props.vh)
  setPos(next)
}

function endDrag(t) {
  dragging.value = false
  suppressClickUntil = performance.now() + 350
  const v = tracker.velocity(t)
  snap(nearest(pos + project(v)), v)
}

// 끌기 없이 손을 뗐는데 움직이던 시트를 붙잡아 멈춰 둔 경우, 가까운 위치로 마저 보낸다
function settleIfHalted() {
  if (!anim && Math.abs(pos - positions.value[settled.value]) > 0.5) snap(nearest(pos), 0)
}

// ── 손잡이·상단 줄: Pointer Events ──
let pointer = null

function onHeadDown(e) {
  if (props.desktop || e.button > 0) return
  pointer = { id: e.pointerId, x: e.clientX, y: e.clientY }
  stopAnim() // 움직이는 중이면 지금 자리에서 바로 잡는다
}

function onHeadMove(e) {
  if (!pointer || e.pointerId !== pointer.id) return
  if (!dragging.value) {
    const dx = e.clientX - pointer.x
    const dy = e.clientY - pointer.y
    if (Math.hypot(dx, dy) < 8) return // 손 떨림과 탭을 끌기로 오해하지 않도록
    if (Math.abs(dx) > Math.abs(dy)) {
      pointer = null
      settleIfHalted()
      return
    }
    // 끌기가 확실해진 뒤에만 캡처한다. 그래야 그냥 누른 버튼의 click이 살아 있다.
    try {
      e.currentTarget.setPointerCapture(e.pointerId)
    } catch {
      // 이미 끝난 포인터면 캡처 없이 이어간다
    }
    beginDrag(e.clientY, e.timeStamp)
  }
  moveDrag(e.clientY, e.timeStamp)
}

function onHeadUp(e) {
  if (!pointer || e.pointerId !== pointer.id) return
  pointer = null
  if (dragging.value) endDrag(e.timeStamp)
  else settleIfHalted()
}

// ── 내용 영역: Touch Events (스크롤과 시트 끌기를 나눠야 해서) ──
let touch = null

function onTouchStart(e) {
  if (props.desktop || e.touches.length > 1) {
    touch = null
    return
  }
  const t = e.touches[0]
  const chips = e.target.closest?.('.chips')
  touch = { x: t.clientX, y: t.clientY, mode: null, chips, chipsLeft: chips?.scrollLeft ?? 0 }
  if (anim) stopAnim()
}

function onTouchMove(e) {
  if (!touch) return
  const t = e.touches[0]
  const dx = t.clientX - touch.x
  const dy = t.clientY - touch.y

  if (touch.mode === null) {
    if (settled.value === 'full') {
      // 올린 상태: 맨 위에서 아래로 끌 때만 시트를 움직이고, 나머지는 브라우저 스크롤에 맡긴다
      const pullDown = dy > 0 && Math.abs(dy) >= Math.abs(dx) && scroller.value.scrollTop <= 0
      touch.mode = pullDown ? 'drag' : 'native'
      if (pullDown) beginDrag(t.clientY, e.timeStamp)
    } else {
      // 내린·중간 상태: 이 영역은 touch-action: none이라 방향이 정해질 때까지 기다릴 수 있다
      if (Math.hypot(dx, dy) < 8) return
      if (Math.abs(dx) > Math.abs(dy)) touch.mode = touch.chips ? 'chips' : 'none'
      else {
        touch.mode = 'drag'
        beginDrag(t.clientY, e.timeStamp)
      }
    }
  }

  if (touch.mode === 'drag') {
    if (e.cancelable) e.preventDefault()
    moveDrag(t.clientY, e.timeStamp)
  } else if (touch.mode === 'chips') {
    touch.chips.scrollLeft = touch.chipsLeft - dx
  }
}

function onTouchEnd(e) {
  if (!touch) return
  const mode = touch.mode
  touch = null
  if (mode === 'drag') endDrag(e.timeStamp)
  else settleIfHalted()
}

// 마우스 휠: 시트가 덜 올라와 있으면 먼저 끝까지 올린다
function onWheel(e) {
  if (props.desktop || settled.value === 'full' || e.deltaY <= 0) return
  e.preventDefault()
  snap('full')
}

function onScroll() {
  scrolled.value = scroller.value.scrollTop > 4
}

function onFocusIn(e) {
  if (!props.desktop && e.target.matches('input, textarea') && settled.value !== 'full') snap('full')
}

// 끌고 난 직후의 click은 버린다 (끌다가 놓은 자리의 항목이 열리지 않게)
function onClickCapture(e) {
  if (performance.now() < suppressClickUntil) {
    e.stopPropagation()
    e.preventDefault()
  }
}

function cycle() {
  snap(settled.value === 'full' ? 'half' : settled.value === 'half' ? 'full' : 'half')
}

function layout(animateIn = false) {
  if (!sheet.value) return
  if (props.desktop) {
    stopAnim()
    sheet.value.style.transform = ''
    return
  }
  if (animateIn && !reducedMotion()) {
    // 처음 열릴 때는 아래에서 올라온다 (내릴 때 사라지는 방향과 같은 길)
    setPos(props.vh)
    snap(settled.value)
  } else {
    stopAnim()
    setPos(positions.value[settled.value])
  }
}

watch(() => props.detent, (d) => {
  if (!props.desktop && d !== settled.value) snap(d)
})
watch(() => [props.vh, props.desktop], () => layout())

onMounted(() => {
  const el = scroller.value
  el.addEventListener('touchstart', onTouchStart, { passive: true })
  el.addEventListener('touchmove', onTouchMove, { passive: false })
  el.addEventListener('touchend', onTouchEnd)
  el.addEventListener('touchcancel', onTouchEnd)
  el.addEventListener('wheel', onWheel, { passive: false })
  layout(true)
})

onBeforeUnmount(() => stopAnim())

defineExpose({ scroller })
</script>

<template>
  <aside
    ref="sheet"
    class="sheet"
    :class="{ desktop, dragging, edge: scrolled }"
    :style="desktop ? null : { height: `${vh - positions.full}px` }"
    @click.capture="onClickCapture"
  >
    <div
      class="sheet-head"
      @pointerdown="onHeadDown"
      @pointermove="onHeadMove"
      @pointerup="onHeadUp"
      @pointercancel="onHeadUp"
    >
      <button v-if="!desktop" type="button" class="grabber" aria-label="패널 크기 바꾸기" @click="cycle">
        <span />
      </button>
      <div class="head-row"><slot name="header" /></div>
    </div>
    <div
      ref="scroller"
      class="sheet-body"
      :class="{ scrollable, locked: !desktop && !scrollable }"
      @scroll.passive="onScroll"
      @focusin="onFocusIn"
    >
      <slot />
    </div>
  </aside>
</template>

<style scoped>
.sheet {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 10;
  display: flex;
  flex-direction: column;
  background: var(--bg);
  border-radius: var(--radius) var(--radius) 0 0;
  box-shadow: var(--shadow-sheet);
  will-change: transform;
  transform: translate3d(0, 100vh, 0);
}

/* 위로 튕기거나 끝을 넘겨 끌 때 시트 아래가 비어 보이지 않게 */
.sheet:not(.desktop)::after {
  content: '';
  position: absolute;
  top: 100%;
  left: 0;
  right: 0;
  height: 60vh;
  background: var(--bg);
}

.sheet.desktop {
  top: var(--gap);
  left: var(--gap);
  bottom: var(--gap);
  right: auto;
  width: var(--panel-w);
  border-radius: var(--radius);
  box-shadow: var(--shadow-lg);
  transform: none;
  will-change: auto;
}

.sheet-head {
  position: relative;
  z-index: 4;
  flex: none;
  padding: 0 var(--pad);
  touch-action: none;
  user-select: none;
  -webkit-user-select: none;
}

.sheet.desktop .sheet-head {
  touch-action: auto;
  padding-top: 6px;
}

/* 스크롤 경계: 선 대신, 내용이 상단 줄 밑으로 들어갈 때만 옅게 흐려진다 */
.sheet-head::after {
  content: '';
  position: absolute;
  top: 100%;
  left: 0;
  right: 0;
  height: 10px;
  background: linear-gradient(var(--material), transparent);
  opacity: 0;
  transition: opacity 160ms ease;
  pointer-events: none;
}

.sheet.edge .sheet-head::after {
  opacity: 1;
}

.grabber {
  display: block;
  width: 100%;
  height: 18px;
  padding: 0;
  border: 0;
  background: none;
  cursor: grab;
}

.grabber span {
  display: block;
  width: 36px;
  height: 4px;
  margin: 8px auto 0;
  border-radius: var(--pill);
  background: var(--ink-3);
  opacity: 0.35;
  transition: opacity 120ms ease, transform 120ms ease;
}

.grabber:active span,
.sheet.dragging .grabber span {
  opacity: 0.7;
  transform: scaleX(1.1);
}

.head-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 4px 0 10px;
}

.sheet-body {
  position: relative;
  flex: 1;
  min-height: 0;
  overflow: hidden;
  padding: 2px var(--pad) calc(36px + env(safe-area-inset-bottom));
  overscroll-behavior: contain;
}

.sheet-body.scrollable {
  overflow-y: auto;
  touch-action: pan-y;
}

/* 덜 올라온 시트에서는 세로 끌기가 시트를 움직인다 (브라우저 스크롤 대신) */
.sheet-body.locked {
  touch-action: none;
}

@media (prefers-contrast: more) {
  .sheet {
    border: 1px solid var(--ink-3);
  }
}
</style>
