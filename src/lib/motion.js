// 손으로 끄는 UI를 위한 작은 물리 도구 (Apple, Designing Fluid Interfaces 2018 기준)
//
// - spring: 감쇠비(damping)와 응답 시간(response, 초)으로 정하는 스프링. 고정된 길이가 없고
//   언제든 멈추고 다른 목표로 다시 보낼 수 있다. 다시 보낼 때는 지금 속도를 그대로 넘긴다.
// - project: 손을 뗀 속도로 '어디에 멈출지'를 미리 계산한다 (스크롤 감속과 같은 지수 감쇠식).
// - rubberband: 경계를 넘겨 끌면 멀리 갈수록 덜 따라오게 한다.

export function reducedMotion() {
  return typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches
}

export function spring({ from, to, velocity = 0, damping = 1, response = 0.35, onUpdate, onDone }) {
  const stiffness = ((2 * Math.PI) / response) ** 2
  const friction = (4 * Math.PI * damping) / response
  let x = from
  let v = velocity
  let last = null
  let frame = 0
  let stopped = false

  const step = (now) => {
    if (stopped) return
    const dt = last == null ? 1 / 60 : Math.min((now - last) / 1000, 1 / 20)
    last = now
    // 240Hz로 쪼개 적분해 프레임이 들쭉날쭉해도 움직임이 같게 나온다
    const n = Math.max(1, Math.ceil(dt * 240))
    const h = dt / n
    for (let i = 0; i < n; i++) {
      const a = -stiffness * (x - to) - friction * v
      v += a * h
      x += v * h
    }
    if (Math.abs(x - to) < 0.25 && Math.abs(v) < 4) {
      x = to
      v = 0
      onUpdate(x)
      onDone?.()
      return
    }
    onUpdate(x)
    frame = requestAnimationFrame(step)
  }
  frame = requestAnimationFrame(step)

  return {
    stop() {
      stopped = true
      cancelAnimationFrame(frame)
    },
    get velocity() {
      return v
    },
  }
}

// decelerationRate 0.998은 일반 스크롤, 0.99는 빠르게 멈추는 느낌. 시트는 그 사이 값을 쓴다.
export function project(velocity, decelerationRate = 0.995) {
  return ((velocity / 1000) * decelerationRate) / (1 - decelerationRate)
}

export function rubberband(overshoot, dimension, constant = 0.55) {
  return (overshoot * dimension * constant) / (dimension + constant * Math.abs(overshoot))
}

// 최근 100ms의 위치 기록으로 손을 뗄 때의 속도(px/s)를 구한다.
export class VelocityTracker {
  constructor() {
    this.samples = []
  }

  reset() {
    this.samples = []
  }

  add(y, t) {
    this.samples.push({ y, t })
    while (this.samples.length > 2 && t - this.samples[0].t > 100) this.samples.shift()
  }

  velocity(releaseTime) {
    const s = this.samples
    if (s.length < 2) return 0
    const first = s[0]
    const lastSample = s[s.length - 1]
    // 손가락을 멈췄다가 떼면 던진 게 아니다
    if (releaseTime != null && releaseTime - lastSample.t > 80) return 0
    const dt = lastSample.t - first.t
    return dt > 0 ? ((lastSample.y - first.y) / dt) * 1000 : 0
  }
}
