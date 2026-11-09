"""데이터 수집 스크립트 공통 유틸.

인증키는 환경변수 PUBLIC_SERVICE_KEY(공공데이터포털 일반 인증키, Encoding 값)로만 받는다.
"""
import datetime as dt
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_DATA = ROOT / "public" / "data"
KST = dt.timezone(dt.timedelta(hours=9))

DATA_GO_KR = "http://apis.data.go.kr"
FIRE_SIGUNGU_URL = f"{DATA_GO_KR}/1400377/forestPointV2/forestPointListSigunguSearchV2"
LANDSLIDE_URL = f"{DATA_GO_KR}/1400000/predictionInfoService/predictionInfoList"
MOUNTAIN_WEATHER_URL = f"{DATA_GO_KR}/1400377/mtweather/mountListSearch"
MOUNTAIN_INFO_URL = "https://apis.data.go.kr/1400000/service/cultureInfoService2/mntInfoOpenAPI2"


def service_key():
    key = os.environ.get("PUBLIC_SERVICE_KEY", "").strip()
    if not key:
        sys.exit("PUBLIC_SERVICE_KEY 환경변수가 없습니다.")
    return key


def now_kst():
    return dt.datetime.now(KST)


def fetch_text(url, params, retries=3, timeout=25):
    # 공공데이터포털 Encoding 키는 이미 % 인코딩돼 있으므로 다시 인코딩하지 않는다.
    query = urllib.parse.urlencode(params)
    full = f"{url}?serviceKey={service_key()}&{query}"
    last_error = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(full, timeout=timeout) as resp:
                return resp.read().decode("utf-8")
        except Exception as exc:  # 네트워크 오류는 재시도
            last_error = exc
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"요청 실패 {url}: {last_error}")


def fetch_items(url, params):
    """data.go.kr JSON 응답에서 item 목록과 totalCount를 꺼낸다."""
    text = fetch_text(url, {**params, "_type": "json"})
    payload = json.loads(text)
    header = payload.get("response", {}).get("header", {})
    if str(header.get("resultCode")) not in ("00", "0"):
        raise RuntimeError(f"API 오류 {url}: {header}")
    body = payload["response"].get("body", {})
    items = (body.get("items") or {}).get("item") if isinstance(body.get("items"), dict) else []
    if isinstance(items, dict):
        items = [items]
    return items or [], int(body.get("totalCount") or 0)


def num(value):
    """'-', '', None → None. 쉼표 섞인 숫자도 처리."""
    if value in (None, "", "-"):
        return None
    try:
        return float(str(value).replace(",", "").strip())
    except ValueError:
        return None


# ── 행정구역 정규화 ────────────────────────────────────────────────────────
# 산불위험예보(doname), 산사태예측(sgg), 산정보(mntiadd)가 시도 표기를 서로 다르게 쓴다.
SIDO_SHORT = [
    # 2026년 전남·광주 통합(전남광주통합특별시) 이후 산불위험예보는 광주 구를 전남 아래에 둔다.
    ("서울", "서울"), ("부산", "부산"), ("대구", "대구"), ("인천", "인천"), ("광주", "전남"),
    ("대전", "대전"), ("울산", "울산"), ("세종", "세종"), ("경기", "경기"),
    ("강원", "강원"), ("충청북", "충북"), ("충북", "충북"), ("충청남", "충남"), ("충남", "충남"),
    ("전라북", "전북"), ("전북", "전북"), ("전라남", "전남"), ("전남", "전남"),
    ("경상북", "경북"), ("경북", "경북"), ("경상남", "경남"), ("경남", "경남"), ("제주", "제주"),
]


def sido_short(name):
    name = (name or "").strip()
    for prefix, short in SIDO_SHORT:
        if name.startswith(prefix):
            return short
    return name[:2]


def region_key(sido, sigungu):
    """('경상북도', '안동시') → '경북 안동시'"""
    sigungu = re.sub(r"\s+", "", sigungu or "")
    return f"{sido_short(sido)} {sigungu}".strip()


def parse_address(address):
    """'서울특별시  강북구 우이동' → '서울 강북구'. 시군구가 없으면 None."""
    tokens = (address or "").split()
    if len(tokens) < 2:
        return None
    sido = sido_short(tokens[0])
    sigungu = tokens[1]
    # '수원시 장안구'처럼 시+구 → 산불위험예보는 시 단위라 시까지만 쓴다.
    if not re.search(r"[시군구]$", sigungu):
        return None
    if sido == "세종":
        return "세종 세종특별자치시"
    return f"{sido} {sigungu}"


def write_json(path, payload, compact=True):
    path.parent.mkdir(parents=True, exist_ok=True)
    kwargs = {"separators": (",", ":")} if compact else {"indent": 1}
    path.write_text(json.dumps(payload, ensure_ascii=False, **kwargs), encoding="utf-8")
    return path
