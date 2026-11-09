"""산 소개 글 정리.

산림청 산정보 서비스(mntidetails)와 올라 데이터의 산 설명은 HTML 엔티티, 빈 값 표시('( - )'),
산행 안내문 조각, 같은 이름의 다른 산 설명이 섞여 있다(docs/description-audit.md).
여기서 글을 고르고, 기계적으로 다듬고, 산별 수정(description_fixes.json)을 적용한다.
원문에 없는 내용은 쓰지 않는다. 문장을 지우거나 글자를 고치기만 한다.
"""
import html
import json
import re
from pathlib import Path

LIMIT = 420
FIXES_PATH = Path(__file__).with_name("description_fixes.json")

HANJA = r"[㐀-䶿一-鿿豈-﫿]"
FULLWIDTH = str.maketrans({**{chr(0xFF10 + i): str(i) for i in range(10)}, "ｍ": "m", "．": ".", "，": ",", "：": ":"})
QUOTES = str.maketrans({c: "'" for c in "`´‘’“”「」『』〈〉《》"})
JUNK = re.compile(r"^[\s()\-–—.]*$")


def load_fixes():
    return json.loads(FIXES_PATH.read_text(encoding="utf-8")) if FIXES_PATH.exists() else {}


def _strip_hanja_in_parens(match):
    inner = re.sub(rf"{HANJA}+\s*[:：]?\s*", "", match.group(1))
    inner = re.sub(r"\s*,\s*,", ",", inner).strip(" ,·:;")
    return f"({inner})" if inner else ""


def normalize(text):
    """엔티티·태그·따옴표·전각 문자·괄호 한자를 정리한다. 글의 내용은 바꾸지 않는다."""
    text = text or ""
    for _ in range(3):  # '&amp;nbsp;'처럼 두 번 감싼 엔티티도 있다
        unescaped = html.unescape(text)
        if unescaped == text:
            break
        text = unescaped
    text = re.sub(r"</?[a-zA-Z][^>]*>", " ", text)  # 진짜 HTML 태그만 (한글로 시작하는 <책 이름>은 남긴다)
    text = re.sub(r"<([^<>]{1,40})>", r"'\1'", text)
    text = text.translate(FULLWIDTH).translate(QUOTES)
    text = re.sub(r"\(([^()]*)\)", lambda m: _strip_hanja_in_parens(m) if re.search(HANJA, m.group(1)) else m.group(0), text)
    text = " ".join(text.replace("\xa0", " ").split())
    text = re.sub(r"\s+([.,])", r"\1", text)  # ' .' → '.'
    text = re.sub(r"(?<=[가-힣])\.(?=[가-힣])", ". ", text)  # '산이다.철원군' → '산이다. 철원군'
    text = re.sub(r"\.{2,}$", ".", text)
    return text.strip()


def is_junk(text):
    return not text or JUNK.match(text) or text.endswith("위치 명산.") or len(text) < 20


def sentences(text):
    return [s for s in re.split(r"(?<=[.!?])\s+", text) if s]


def is_complete(sentence):
    return bool(re.search(r"[.!?]['\")]?$", sentence))


def finish(text, drop=(), replace=(), limit=LIMIT):
    """산별 수정 적용 → 끝난 문장까지만 limit 안에서 자른다. 끝난 문장이 없으면 빈 값."""
    for old, new in replace:
        if old not in text:
            raise ValueError(f"수정할 구절을 찾지 못했습니다: {old!r}")
        text = text.replace(old, new)
    kept = []
    for s in sentences(text):
        if any(d in s for d in drop):
            continue
        if not is_complete(s):
            break  # 원본이 잘린 자리. 뒤는 버린다.
        if len(" ".join(kept + [s])) > limit:
            break
        kept.append(s)
    return " ".join(kept)


def candidates(records, olla_text):
    """(출처, 지역, 글) 후보. 같은 산이 지자체마다 다른 레코드로 들어 있다."""
    out = [("info", rec.get("_region", ""), normalize(rec.get("mntidetails"))) for rec in records]
    out.append(("olla", "", normalize(olla_text)))
    return [c for c in out if not is_junk(c[2])]


def pick(name, names, regions, records, olla_text, fix):
    """후보 중 이 산 이름이 들어 있고, 대표 지역(첫 지역) 레코드이고, 긴 글을 고른다."""
    if fix.get("clear"):
        return "", "none"
    pool = candidates(records, olla_text)
    if fix.get("source"):
        pool = [c for c in pool if c[0] == fix["source"] or c[1] == fix["source"]]

    def score(c):
        head = c[2][:120]
        return (
            any(n in head for n in names) * 4
            + (c[1] == (regions[0] if regions else None)) * 2
            + min(len(c[2]), 400) / 200
        )

    if not pool:
        return "", "none"
    source, _, text = max(pool, key=score)
    text = finish(text, fix.get("drop", ()), fix.get("replace", ()))
    if is_junk(text):
        return "", "none"
    return text, source
