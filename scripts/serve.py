"""Railway용 서버: 빌드된 사이트(dist/)를 내주고, 매시 7분에 산림청 실시간 데이터를 새로 모은다.

GitHub Pages에서는 GitHub Actions가 매시간 fetch_live.py를 돌려 다시 배포하지만,
Railway에서는 이 서버가 같은 스크립트를 직접 돌려 live/snapshot.json만 바꿔 끼운다.

환경변수
  PORT                Railway가 넣어 준다 (기본 8080)
  PUBLIC_SERVICE_KEY  공공데이터포털 일반 인증키(Encoding). 없으면 수집을 건너뛴다.
  LIVE_DIR            스냅샷을 둘 폴더 (기본 /tmp/san-signal-live)
"""
import datetime as dt
import gzip
import mimetypes
import os
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
DIST = (ROOT / "dist").resolve()
LIVE_DIR = Path(os.environ.get("LIVE_DIR") or "/tmp/san-signal-live")
LIVE_FILE = LIVE_DIR / "snapshot.json"
FETCH_MINUTE = 7  # GitHub Actions와 같은 매시 7분. 정각 혼잡을 피한다.
FETCH_TIMEOUT = 300

mimetypes.add_type("application/json", ".json")
mimetypes.add_type("image/svg+xml", ".svg")
mimetypes.add_type("text/javascript", ".js")
COMPRESSIBLE = ("text/", "application/json", "image/svg+xml")


def log(*args):
    print(dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), *args, flush=True)


# ── 실시간 데이터 수집 ────────────────────────────────────────────────────
def fetch_once():
    if not os.environ.get("PUBLIC_SERVICE_KEY", "").strip():
        log("PUBLIC_SERVICE_KEY가 없어 실시간 데이터 수집을 건너뜁니다.")
        return
    LIVE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = LIVE_DIR / "snapshot.next.json"
    env = dict(os.environ, LIVE_PATH=str(tmp), PYTHONUTF8="1")
    if LIVE_FILE.exists():
        env["PREVIOUS_SNAPSHOT"] = str(LIVE_FILE)  # 한 API가 실패하면 직전 값을 이어 쓴다
    try:
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "fetch_live.py")],
            env=env, capture_output=True, text=True, timeout=FETCH_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        log("실시간 데이터 수집이 시간 안에 끝나지 않았습니다.")
        return
    out = (result.stdout + result.stderr).strip().splitlines()
    if result.returncode == 0 and tmp.exists():
        os.replace(tmp, LIVE_FILE)  # 요청 중에 반쯤 쓴 파일이 나가지 않도록 한 번에 바꾼다
        log("스냅샷 갱신:", out[-1] if out else "")
    else:
        log("스냅샷 수집 실패, 직전 값 유지:", " | ".join(out[-3:]))


def seconds_until_next_run(now=None):
    now = now or dt.datetime.now()
    target = now.replace(minute=FETCH_MINUTE, second=0, microsecond=0)
    if target <= now:
        target += dt.timedelta(hours=1)
    return (target - now).total_seconds()


def fetch_loop():
    fetch_once()  # 새로 뜬 서버도 바로 최신 값을 갖도록
    while True:
        time.sleep(seconds_until_next_run())
        fetch_once()


# ── 정적 파일 ─────────────────────────────────────────────────────────────
_gzip_cache = {}
_gzip_lock = threading.Lock()


def gzipped(path, mtime, raw):
    key = str(path)
    with _gzip_lock:
        hit = _gzip_cache.get(key)
        if hit and hit[0] == mtime:
            return hit[1]
    body = gzip.compress(raw, compresslevel=6)
    with _gzip_lock:
        _gzip_cache[key] = (mtime, body)
    return body


def resolve(url_path):
    """요청 경로 → 파일. dist 밖으로 나가는 경로는 막는다."""
    path = unquote(urlsplit(url_path).path)
    if path in ("", "/"):
        path = "/index.html"
    if path == "/live/snapshot.json":
        return LIVE_FILE, "no-cache"
    target = (DIST / path.lstrip("/")).resolve()
    if DIST not in target.parents or not target.is_file():
        return None, None
    if path.startswith("/assets/"):
        return target, "public, max-age=31536000, immutable"  # 파일 이름에 해시가 들어 있다
    if path.startswith("/data/"):
        return target, "public, max-age=3600"
    return target, "no-cache"


class Handler(BaseHTTPRequestHandler):
    server_version = "san-signal"
    sys_version = ""

    def do_GET(self):
        self.respond(send_body=True)

    def do_HEAD(self):
        self.respond(send_body=False)

    def respond(self, send_body):
        target, cache = resolve(self.path)
        if target is None or not target.is_file():
            self.send_error(404)
            return
        stat = target.stat()
        raw = target.read_bytes()
        ctype = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        body, encoding = raw, None
        if ctype.startswith(COMPRESSIBLE) and len(raw) > 1024 and "gzip" in self.headers.get("Accept-Encoding", ""):
            body, encoding = gzipped(target, stat.st_mtime_ns, raw), "gzip"
        self.send_response(200)
        self.send_header("Content-Type", f"{ctype}; charset=utf-8" if ctype.startswith("text/") or ctype == "application/json" else ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", cache)
        self.send_header("Vary", "Accept-Encoding")
        self.send_header("X-Content-Type-Options", "nosniff")
        if encoding:
            self.send_header("Content-Encoding", encoding)
        self.end_headers()
        if send_body:
            self.wfile.write(body)

    def log_message(self, fmt, *args):  # 정적 파일 요청 로그는 남기지 않는다
        pass


def main():
    if not (DIST / "index.html").exists():
        sys.exit(f"{DIST}/index.html이 없습니다. 먼저 npm run build를 실행하세요.")
    threading.Thread(target=fetch_loop, daemon=True).start()
    port = int(os.environ.get("PORT", "8080"))
    log(f"산행 신호등 서버 시작: 0.0.0.0:{port}")
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
