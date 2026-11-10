<script setup>
// 신호를 색과 모양으로 함께 보여준다. 색만으로 구분하지 않도록 (색약 사용자)
//   좋음 ✓ / 주의 ! / 위험 ⚠ / 자료 없음 -
import { PhCheck, PhExclamationMark, PhMinus, PhWarning } from '@phosphor-icons/vue'

const props = defineProps({
  level: { type: Number, default: null }, // 0 | 1 | 2 | null(자료 없음)
  size: { type: Number, default: 36 },
})

const KEYS = ['ok', 'caution', 'danger']
const ICONS = [PhCheck, PhExclamationMark, PhWarning]
</script>

<template>
  <span
    class="sig-icon"
    :class="KEYS[props.level] || 'none'"
    :style="{ width: `${size}px`, height: `${size}px` }"
    aria-hidden="true"
  >
    <component :is="ICONS[props.level] || PhMinus" :size="Math.round(size * 0.5)" weight="bold" />
  </span>
</template>

<style scoped>
.sig-icon {
  flex: none;
  display: grid;
  place-items: center;
  border-radius: 50%;
  background: var(--soft);
  color: var(--ink-3);
}

.sig-icon.ok { background: var(--ok-bg); color: var(--ok-text); }
.sig-icon.caution { background: var(--caution-bg); color: var(--caution-text); }
.sig-icon.danger { background: var(--danger-bg); color: var(--danger-text); }
</style>
