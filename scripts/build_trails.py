"""산림청 등산로(1:25,000) SHP → 산별 등산로 JSON (public/data/trails/<id>.json)

원본: 산림청 산림공간정보 '등산로' (TB_FGDI_WG_MT_WAY, SHP, UTM-K)
  - 등산로 구간마다 산코드·산명·구간명·길이·상하행 시간·통제/폐쇄 여부·위험구간 내용이 있다.
  - 원본은 약 150MB라 웹에서 바로 쓸 수 없어서, 산별로 잘라 좌표를 단순화해 둔다.

사용법
  python scripts/build_trails.py <WG_MT_WAY 폴더 경로>
"""
import math
import sys
from collections import Counter
from pathlib import Path

from common import PUBLIC_DATA, write_json
import json
from shp import encode_polyline, read_dbf, read_polylines, simplify, utmk_to_wgs84

CODE_MATCH_KM = 20   # 산코드가 같을 때 허용 거리 (같은 코드가 다른 지역에 쓰인 경우 방지)
NAME_MATCH_KM = 12   # 산 이름만 같을 때 허용 거리 (동명이산 방지)
TOLERANCE_DEG = 0.00004  # 약 4m

# 산과 이어진 구간이 이 기준을 못 넘으면 지도에 그리지 않는다.
# 다른 산(같은 이름, 같은 산코드)의 등산로이거나, 정상에 닿지 않는 조각뿐인 경우다.
SUMMIT_KM = 1.0    # 가장 가까운 구간이 정상에서 이만큼 안에 있어야 한다
MIN_SEGMENTS = 8   # 구간이 이보다 적으면 조각뿐이다


def km(lat1, lng1, lat2, lng2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    h = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lng2 - lng1) / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(h))


def to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def main(shp_dir):
    shp_dir = Path(shp_dir)
    payload = json.loads((PUBLIC_DATA / "mountains.json").read_text(encoding="utf-8"))
    mountains = payload["mountains"]
    rows = read_dbf(shp_dir / "WG_MT_WAY.dbf")
    shapes = read_polylines(shp_dir / "WG_MT_WAY.shp")
    print(f"등산로 구간 {len(rows)}개 / 도형 {len(shapes)}개")

    # 데이터 품질 통계 (개선 의견 근거)
    quality = {
        "segments": len(rows),
        "data_date": Counter(r.get("DATA_STDR_") or "(없음)" for r in rows).most_common(5),
        "difficulty": Counter(r.get("PMNTN_DFFL") or "(없음)" for r in rows).most_common(8),
        "closed_Y": sum(r.get("PMNTN_CLS_") == "Y" for r in rows),
        "control_Y": sum(r.get("PMNTN_CNRL") == "Y" for r in rows),
        "risk_text": sum(bool(r.get("PMNTN_RISK")) for r in rows),
    }

    by_code = {}
    for m in mountains:
        for code in m["codes"]:
            by_code.setdefault(code, []).append(m)
    by_name = {}
    for m in mountains:
        aliases = {m["name"]}
        # '봉화청량산', '문경황장산'처럼 지역명을 붙여 구분한 이름 → '청량산', '황장산'
        for region in m["regions"]:
            short = region.split(" ", 1)[1][:2]
            if m["name"].startswith(short) and len(m["name"]) > len(short) + 1:
                aliases.add(m["name"][len(short):])
        for alias in aliases:
            by_name.setdefault(alias, []).append(m)

    segments = {m["id"]: [] for m in mountains}
    nearest = {m["id"]: math.inf for m in mountains}  # 정상에서 가장 가까운 구간까지 거리(km)
    for row, parts in zip(rows, shapes):
        if row["_deleted"] or not parts or not parts[0]:
            continue
        x, y = parts[0][len(parts[0]) // 2]
        lat, lng = utmk_to_wgs84(x, y)
        target = None
        for m in by_code.get(row.get("MNTN_CODE"), []):
            if km(lat, lng, m["lat"], m["lng"]) <= CODE_MATCH_KM:
                target = m
                break
        if target is None:
            # '청량산_의상봉', '오대산_노인봉' → 앞·뒤 이름 모두 후보
            raw = row.get("MNTN_NM") or ""
            for name in dict.fromkeys([raw, *raw.split("_")]):
                for m in by_name.get(name, []):
                    if km(lat, lng, m["lat"], m["lng"]) <= NAME_MATCH_KM:
                        target = m
                        break
                if target:
                    break
        if target is None:
            continue

        lines = []
        near = math.inf
        for part in parts:
            pts = simplify([utmk_to_wgs84(px, py) for px, py in part], TOLERANCE_DEG)
            if len(pts) >= 2:
                lines.append(encode_polyline(pts))
                near = min(near, *(km(plat, plng, target["lat"], target["lng"]) for plat, plng in pts))
        if not lines:
            continue
        nearest[target["id"]] = min(nearest[target["id"]], near)
        length = to_float(row.get("PMNTN_LT")) or 0
        segment = {
            "n": row.get("PMNTN_NM") or "",
            "km": round(length, 2),
            "up": int(to_float(row.get("PMNTN_UPPL")) or 0),
            "dn": int(to_float(row.get("PMNTN_GODN")) or 0),
            "p": lines,
        }
        if row.get("PMNTN_CLS_") == "Y":
            segment["closed"] = 1
        if row.get("PMNTN_CNRL") == "Y":
            segment["ctrl"] = 1
        if row.get("PMNTN_RISK"):
            segment["risk"] = row["PMNTN_RISK"]
        if row.get("PMNTN_MTRQ"):
            segment["mat"] = row["PMNTN_MTRQ"]
        segments[target["id"]].append(segment)

    trail_dir = PUBLIC_DATA / "trails"
    for old in trail_dir.glob("*.json"):
        old.unlink()
    total_bytes = 0
    for m in mountains:
        segs = segments[m["id"]]
        near = nearest[m["id"]]
        if not segs:
            status = "none"
        elif near > SUMMIT_KM:
            status = "far"
        elif len(segs) < MIN_SEGMENTS:
            status = "few"
        else:
            status = "ok"
        if status != "ok":
            # 그리지 않는 산: 화면에서 이유를 한 줄로 알려줄 수 있게 원본 구간 수와 거리만 남긴다
            m["trails"] = {"segments": 0, "status": status, "found": len(segs)}
            if segs:
                m["trails"]["nearest_km"] = round(near, 1)
            continue
        m["trails"] = {
            "segments": len(segs),
            "km": round(sum(s["km"] for s in segs), 1),
            "closed": sum(1 for s in segs if s.get("closed")),
            "ctrl": sum(1 for s in segs if s.get("ctrl")),
            "risk": sum(1 for s in segs if s.get("risk")),
            "status": status,
        }
        path = write_json(trail_dir / f"{m['id']}.json", {"id": m["id"], "segments": segs})
        total_bytes += path.stat().st_size

    payload["trail_quality"] = quality
    write_json(PUBLIC_DATA / "mountains.json", payload)
    by_status = Counter(m["trails"]["status"] for m in mountains)
    print(f"지도에 그리는 산 {by_status['ok']}/{len(mountains)}개, 파일 합계 {total_bytes / 1e6:.1f}MB")
    print("품질:", json.dumps(quality, ensure_ascii=False))
    for m in sorted(mountains, key=lambda m: -m["trails"]["segments"])[:8]:
        print(" ", m["name"], m["trails"])
    labels = {"far": f"정상 {SUMMIT_KM:g}km 안에 닿는 구간 없음", "few": f"구간 {MIN_SEGMENTS}개 미만", "none": "구간 없음"}
    for status, label in labels.items():
        rows_ = [m for m in mountains if m["trails"]["status"] == status]
        detail = ", ".join(
            m["name"] + (f"({m['trails']['found']}구간 {m['trails'].get('nearest_km')}km)" if m["trails"]["found"] else "")
            for m in rows_
        )
        print(f"{label} {len(rows_)}: {detail}")


if __name__ == "__main__":
    main(sys.argv[1])
