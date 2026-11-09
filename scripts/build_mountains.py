"""산 목록(public/data/mountains.json)을 만든다. 한 번만 돌리고 결과를 커밋한다.

입력
  - 기존 '올라' 프로젝트의 산 목록(이름·좌표·고도·난이도·소요시간) : mountain_data.py 경로
  - 산림청_산정보 서비스(cultureInfoService2)      : 산코드, 소재지 주소, 산 소개
  - 산림청 국립산림과학원_산불위험예보정보(시군구)    : 시군구 코드표
  - 산림청 국립산림과학원_산악기상정보               : 관측소 목록

사용법
  PUBLIC_SERVICE_KEY=... python scripts/build_mountains.py <forest>/backend/recommendations/mountain_data.py
"""
import math
import re
import runpy
import sys
import time
from collections import Counter

from common import (
    FIRE_SIGUNGU_URL, MOUNTAIN_INFO_URL, MOUNTAIN_WEATHER_URL, PUBLIC_DATA,
    fetch_items, fetch_text, now_kst, parse_address, region_key, sido_short, write_json,
)

METRO = {"서울", "부산", "대구", "인천", "대전", "울산", "세종"}
NOT_MOUNTAIN = {"한려해상", "다도해해상", "태안해안", "변산반도"}  # 해상·해안 국립공원은 제외

# 여러 시군구에 걸친 산. 산정보 서비스는 좌표가 없고 같은 이름의 산이 전국에 흩어져 있어
# 주소만으로는 '어느 지리산'인지 가릴 수 없다. → 국립공원·경계 산은 직접 지정한다.
REGION_OVERRIDES = {
    "지리산": ["경남 산청군", "경남 함양군", "경남 하동군", "전남 구례군", "전북 남원시"],
    "설악산": ["강원 속초시", "강원 양양군", "강원 인제군", "강원 고성군"],
    "한라산": ["제주 제주시", "제주 서귀포시"],
    "북한산": ["서울 강북구", "서울 도봉구", "서울 은평구", "서울 종로구", "서울 성북구",
             "경기 고양시", "경기 양주시", "경기 의정부시"],
    "도봉산": ["서울 도봉구", "경기 의정부시", "경기 양주시"],
    "오대산": ["강원 평창군", "강원 강릉시", "강원 홍천군"],
    "소백산": ["충북 단양군", "경북 영주시"],
    "태백산": ["강원 태백시", "강원 영월군", "경북 봉화군"],
    "치악산": ["강원 원주시", "강원 횡성군"],
    "월악산": ["충북 제천시", "충북 충주시", "충북 단양군", "경북 문경시"],
    "속리산": ["충북 보은군", "충북 괴산군", "경북 상주시"],
    "계룡산": ["충남 공주시", "충남 계룡시", "대전 유성구"],
    "덕유산": ["전북 무주군", "전북 장수군", "경남 거창군", "경남 함양군"],
    "남덕유산": ["경남 함양군", "경남 거창군", "전북 장수군"],
    "가야산": ["경남 합천군", "경북 성주군"],
    "내장산": ["전북 정읍시", "전북 순창군", "전남 장성군"],
    "무등산": ["전남 동구", "전남 북구", "전남 화순군", "전남 담양군"],
    "주왕산": ["경북 청송군"],
    "월출산": ["전남 영암군", "전남 강진군"],
    "팔공산": ["대구 동구", "대구 군위군", "경북 칠곡군", "경북 영천시", "경북 경산시"],
    "황매산": ["경남 합천군", "경남 산청군"],
    "일월산": ["경북 영양군", "경북 봉화군"],
    "청계산": ["서울 서초구", "경기 과천시", "경기 성남시", "경기 의왕시"],
    "관악산": ["서울 관악구", "경기 과천시", "경기 안양시"],
    "수락산": ["서울 노원구", "경기 의정부시", "경기 남양주시"],
    "불암산": ["서울 노원구", "경기 남양주시"],
    "금정산": ["부산 금정구", "경남 양산시"],
    "가지산": ["울산 울주군", "경남 밀양시"],
    "재약산": ["경남 밀양시", "울산 울주군"],
    "신불산": ["울산 울주군", "경남 양산시"],
    "영축산": ["경남 양산시", "울산 울주군"],
    "운문산": ["경북 청도군", "경남 밀양시"],
    "화악산": ["경기 가평군", "강원 화천군"],
    "대둔산": ["충남 논산시", "충남 금산군", "전북 완주군"],
    "모악산": ["전북 김제시", "전북 완주군", "전북 전주시"],
    "희양산": ["충북 괴산군", "경북 문경시"],
    "대야산": ["경북 문경시", "충북 괴산군"],
    "두타산": ["강원 동해시", "강원 삼척시"],
}
NEAREST_STATION_KM = 25


def load_base_mountains(path):
    return [m for m in runpy.run_path(path)["MOUNTAINS"] if m["name"] not in NOT_MOUNTAIN]


def fire_region_table():
    items, _ = fetch_items(FIRE_SIGUNGU_URL, {"pageNo": 1, "numOfRows": 400})
    return {region_key(i["doname"], i["sigun"]): int(i["sigucode"]) for i in items}


def station_list():
    tm = now_kst().replace(minute=0, second=0, microsecond=0).strftime("%Y%m%d%H%M")
    items, _ = fetch_items(MOUNTAIN_WEATHER_URL, {"pageNo": 1, "numOfRows": 700, "tm": tm})
    return [{"id": int(i["obsid"]), "name": " ".join(str(i["obsname"]).split())} for i in items]


def mountain_info_records(name):
    """산정보 서비스에서 이 산에 해당하는 레코드(지자체별로 여러 건일 수 있음)."""
    text = fetch_text(MOUNTAIN_INFO_URL, {"pageNo": 1, "numOfRows": 50, "searchWrd": name})
    records = []
    for raw in re.findall(r"<item>(.*?)</item>", text, re.S):
        fields = {k: v.strip() for k, v in re.findall(r"<(\w+)>(.*?)</\1>", raw, re.S)}
        title = fields.get("mntiname", "")
        if title == name or title.startswith(name + "_") or title.startswith(name + "("):
            records.append(fields)
    return records


def short_sigungu(key):
    sido, sigungu = key.split(" ", 1)
    if sido in METRO:
        return sido
    return re.sub(r"(시|군|구)$", "", sigungu) if len(sigungu) > 2 else sigungu


def match_stations(name, regions, stations):
    """산악기상정보 응답에는 관측소 좌표가 없다. 관측소 이름('양평 용문산')의
    앞머리(시군)와 뒤(산 이름)로만 산과 이어 붙일 수 있다."""
    prefixes = {short_sigungu(r) for r in regions}
    in_region = [s for s in stations if s["name"].split(" ", 1)[0] in prefixes]
    by_name = [s for s in in_region if name in s["name"].split(" ", 1)[-1]]
    if by_name:
        return [s["id"] for s in by_name][:3], "name"
    if in_region:
        return [s["id"] for s in in_region][:6], "region"
    return [], "none"


def haversine_km(a, b):
    lat1, lng1, lat2, lng2 = map(math.radians, (a["lat"], a["lng"], b["lat"], b["lng"]))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lng2 - lng1) / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(h))


def parse_regions(text):
    regions = []
    for part in re.split(r"[·,/]", text or ""):
        tokens = part.split()
        if len(tokens) >= 2:
            regions.append(f"{sido_short(tokens[0])} {tokens[1]}")
    return regions


def clean_text(text, limit=420):
    text = re.sub(r"<[^>]+>|&[a-z]+;", " ", text or "")
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    cut = text[:limit]
    return cut[: cut.rfind(".") + 1] if "." in cut[200:] else cut + "…"


def main(mountain_data_path):
    base = load_base_mountains(mountain_data_path)
    fire_codes = fire_region_table()
    stations = station_list()
    print(f"산 {len(base)}개, 산불 시군구 {len(fire_codes)}개, 산악기상 관측소 {len(stations)}곳")
    station_by_id = {s["id"]: s["name"] for s in stations}

    out, stats = [], Counter()
    for index, m in enumerate(base, start=1):
        regions = REGION_OVERRIDES.get(m["name"]) or parse_regions(m.get("region"))
        known = [r for r in regions if r in fire_codes]
        unknown = [r for r in regions if r not in fire_codes]
        if unknown:
            stats["region_unmatched"] += 1
            print(f"  ! {m['name']}: 산불위험예보 시군구표에 없는 지역 {unknown}")

        # 같은 이름의 산이 전국에 여러 개다(백운산·매봉산…). 산정보 서비스에는 좌표가 없어서
        # 소재지 주소가 이 산의 시군구와 같은 레코드만 같은 산으로 본다.
        records = [
            rec for rec in mountain_info_records(m["name"])
            if parse_address(rec.get("mntiadd")) in known
        ]
        time.sleep(0.15)
        stats["info_found" if records else "info_missing"] += 1

        station_ids, how = match_stations(m["name"], known, stations)
        stats[f"station_{how}"] += 1

        main_record = next((r for r in records if r.get("mntiname") == m["name"]), records[0] if records else {})
        description = clean_text(main_record.get("mntidetails")) or clean_text(m.get("description"))
        top = clean_text(main_record.get("mntitop"), 160)
        height = main_record.get("mntihigh")
        elevation = m.get("elevation_m") or (round(float(height)) if height and float(height) > 0 else None)

        out.append({
            "id": f"m{index:03d}",
            "name": m["name"],
            "region": m.get("region", ""),
            "lat": round(m["lat"], 5),
            "lng": round(m["lng"], 5),
            "elevation_m": elevation,
            "difficulty": m.get("difficulty", "medium"),
            "walk_min": m.get("walk_time_min"),
            "walk_max": m.get("walk_time_max"),
            "national_park": bool(m.get("national_park")),
            "description": description,
            "top": top,
            "codes": sorted({r["mntilistno"] for r in records if r.get("mntilistno")}),
            "regions": known,
            "fire_codes": [fire_codes[r] for r in known],
            "stations": station_ids,
            "station_match": how,
        })

    # 같은 시군구에 관측소가 없으면, 좌표가 가장 가까운 '관측소 있는 산'의 관측소를 빌려 쓴다.
    with_station = [m for m in out if m["station_match"] in ("name", "region")]
    for m in out:
        if m["station_match"] != "none":
            continue
        nearest = min(with_station, key=lambda other: haversine_km(m, other))
        distance = haversine_km(m, nearest)
        if distance <= NEAREST_STATION_KM:
            m["stations"] = nearest["stations"][:3]
            m["station_match"] = "nearby"
            stats["station_none"] -= 1
            stats["station_nearby"] += 1

    report = [
        f"{m['name']:<8} {','.join(m['regions']):<36} 산코드 {len(m['codes'])}개 "
        f"[{m['station_match']}] {', '.join(station_by_id[s] for s in m['stations'])}"
        for m in out
    ]
    write_json(PUBLIC_DATA / "mountains.json", {"built_at": now_kst().isoformat(timespec="minutes"), "mountains": out})
    write_json(PUBLIC_DATA / "stations.json", {s["id"]: s["name"] for s in stations})
    (PUBLIC_DATA.parent.parent / "scripts" / "match_report.txt").write_text("\n".join(report), encoding="utf-8")
    print("매칭 통계:", dict(stats))


if __name__ == "__main__":
    main(sys.argv[1])
