// 패널 배치 상수. App(지도 가림 영역 계산)과 SheetPanel(끌기)이 같은 값을 쓴다.
export const DESKTOP_QUERY = '(min-width: 900px)'
export const PANEL_W = 420 // 데스크톱 떠 있는 패널 폭 (styles.css의 --panel-w와 같게)
export const GAP = 12 // 데스크톱 패널 바깥 여백 (--gap)
export const SHEET_TOP = 52 // 모바일 시트를 끝까지 올렸을 때 위에 남기는 지도 높이
export const PEEK_H = 196 // 모바일 시트를 내렸을 때 보이는 높이: 손잡이·상단 줄·집계까지

// 모바일 시트가 멈출 수 있는 위치(화면 위에서부터 px)
export function detentPositions(vh) {
  const full = SHEET_TOP
  const half = Math.round(vh * 0.48)
  const peek = Math.max(half + 72, vh - PEEK_H)
  return { full, half, peek }
}
