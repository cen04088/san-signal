"""실시간 산림 데이터 스냅샷(public/live/snapshot.json). GitHub Actions가 매시간 실행한다.

  1. 산림청 국립산림과학원_산불위험예보정보  : 시군구 230곳의 산불위험지수(평균·최대)
  2. 산림청_산사태예측정보                  : 최근 발령된 산사태 주의보·경보(시군구)
  3. 산림청 국립산림과학원_산악기상정보      : 전국 산악기상관측소 실측(기온·풍속·습도·강수)

한 API가 실패해도 나머지는 그대로 내보내고, 실패한 항목은 ok=false로 표시한다.
"""
import datetime as dt
import json
import os
import traceback

from common import (
    FIRE_SIGUNGU_URL, KST, LANDSLIDE_URL, MOUNTAIN_WEATHER_URL, ROOT,
    fetch_items, now_kst, num, region_key, write_json,
)

LIVE_PATH = ROOT / "public" / "live" / "snapshot.json"
LANDSLIDE_ACTIVE_HOURS = 3  # 산사태예측은 매시 발령분만 올라온다 → 최근 3시간 안의 발령을 '진행 중'으로 본다


def fetch_fire():
    items, _ = fetch_items(FIRE_SIGUNGU_URL, {"pageNo": 1, "numOfRows": 400})
    by_code = {}
    for i in items:
        by_code[int(i["sigucode"])] = [
            int(num(i.get("meanavg")) or 0), int(num(i.get("maxi")) or 0),
            # d1~d4: 낮음·보통·높음·매우높음 단계 면적 비율(%)
            int(num(i.get("d1")) or 0), int(num(i.get("d2")) or 0),
            int(num(i.get("d3")) or 0), int(num(i.get("d4")) or 0),
        ]
    analdate = max((i.get("analdate") or "" for i in items), default="")
    return {"ok": bool(by_code), "analdate": analdate, "by_code": by_code}


def fetch_landslide(now):
    items, total = fetch_items(LANDSLIDE_URL, {"pageNo": 1, "numOfRows": 200})
    cutoff = now - dt.timedelta(hours=LANDSLIDE_ACTIVE_HOURS)
    active, latest_any = {}, ""
    for i in items:  # 최신순
        stamp = i.get("prctnInfoAnlssDt") or ""
        latest_any = max(latest_any, stamp)
        try:
            when = dt.datetime.strptime(stamp, "%Y-%m-%d %H:%M:%S").replace(tzinfo=KST)
        except ValueError:
            continue
        level = i.get("lndslFrcstNm") or ""
        tokens = (i.get("sgg") or "").split()
        if when < cutoff or level not in ("주의보", "경보") or len(tokens) < 2:
            continue
        key = region_key(tokens[0], tokens[1])
        prev = active.get(key)
        if not prev or (level == "경보" and prev["level"] != "경보"):
            active[key] = {"level": level, "time": stamp[:16]}
    return {"ok": True, "total_records": total, "latest_any": latest_any[:16], "active": active}


def fetch_weather(now):
    """tm(관측시각)을 넣지 않으면 모든 값이 '-'로 온다. 10분 단위로 내려 맞춘다."""
    base = now.replace(second=0, microsecond=0)
    candidates = [
        base - dt.timedelta(minutes=base.minute % 10 + 10),
        base.replace(minute=0) - dt.timedelta(hours=1),
    ]
    best = None
    for tm in candidates:
        items, _ = fetch_items(MOUNTAIN_WEATHER_URL, {"pageNo": 1, "numOfRows": 700, "tm": tm.strftime("%Y%m%d%H%M")})
        by_station = {}
        for i in items:
            t = num(i.get("tm2m"))
            if t is None:
                continue
            by_station[int(i["obsid"])] = {
                "t": t,
                "ws": num(i.get("ws2m")),
                "ws10": num(i.get("ws10m")),
                "hm": num(i.get("hm2m")),
                "rn": num(i.get("rn")),
                "cprn": num(i.get("cprn")),
                "at": (i.get("tm") or "")[11:16],
            }
        result = {"ok": bool(by_station), "tm": tm.strftime("%Y-%m-%d %H:%M"), "stations": len(items), "by_station": by_station}
        if len(by_station) >= 300:
            return result
        best = result if not best or len(by_station) > len(best["by_station"]) else best
    return best


def safe(name, func, *args):
    try:
        return func(*args)
    except Exception as exc:
        traceback.print_exc()
        return {"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:160]}"}


def load_previous():
    """배포 중인 직전 스냅샷(워크플로가 PREVIOUS_SNAPSHOT 경로로 내려받아 둠)."""
    path = os.environ.get("PREVIOUS_SNAPSHOT")
    if not path or not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as fp:
            return json.load(fp)
    except (OSError, ValueError):
        return {}


def main():
    now = now_kst()
    snapshot = {
        "generated_at": now.isoformat(timespec="minutes"),
        "fire": safe("fire", fetch_fire),
        "landslide": safe("landslide", fetch_landslide, now),
        "weather": safe("weather", fetch_weather, now),
    }
    # 한 API만 일시적으로 실패했다면, 직전 값을 '지연' 표시와 함께 이어서 쓴다(빈 화면 방지).
    previous = load_previous()
    for key in ("fire", "landslide", "weather"):
        old = previous.get(key) or {}
        if not snapshot[key].get("ok") and old.get("ok"):
            snapshot[key] = {**old, "stale": True, "error": snapshot[key].get("error")}
    write_json(LIVE_PATH, snapshot)
    summary = {
        "fire": len(snapshot["fire"].get("by_code", {})),
        "landslide_active": len(snapshot["landslide"].get("active", {})),
        "weather_stations": len(snapshot["weather"].get("by_station", {})),
    }
    print(snapshot["generated_at"], summary)
    if not any(snapshot[k].get("ok") for k in ("fire", "landslide", "weather")):
        raise SystemExit("모든 API 호출이 실패했습니다.")


if __name__ == "__main__":
    main()
