"""의존성 없는 SHP(PolyLine)·DBF 리더와 UTM-K(EPSG:5179) → WGS84 변환."""
import math
import struct
from pathlib import Path


def read_polylines(path):
    data = Path(path).read_bytes()
    offset, shapes = 100, []
    while offset + 8 <= len(data):
        length = struct.unpack(">i", data[offset + 4: offset + 8])[0] * 2
        content = data[offset + 8: offset + 8 + length]
        offset += 8 + length
        if len(content) < 44 or struct.unpack("<i", content[0:4])[0] != 3:
            shapes.append([])
            continue
        num_parts, num_points = struct.unpack("<ii", content[36:44])
        parts = list(struct.unpack(f"<{num_parts}i", content[44: 44 + 4 * num_parts]))
        base = 44 + 4 * num_parts
        coords = [struct.unpack("<dd", content[base + 16 * i: base + 16 * i + 16]) for i in range(num_points)]
        parts.append(num_points)
        shapes.append([coords[parts[i]: parts[i + 1]] for i in range(num_parts)])
    return shapes


def read_dbf(path):
    data = Path(path).read_bytes()
    count = struct.unpack("<I", data[4:8])[0]
    header_len, record_len = struct.unpack("<HH", data[8:12])
    fields = []
    for i in range((header_len - 33) // 32):
        off = 32 + i * 32
        name = data[off: off + 11].split(b"\x00", 1)[0].decode("ascii", "ignore")
        fields.append((name, data[off + 16]))
    rows = []
    for r in range(count):
        off = header_len + r * record_len
        cursor, row = off + 1, {}
        for name, size in fields:
            row[name] = data[cursor: cursor + size].decode("cp949", "ignore").strip()
            cursor += size
        row["_deleted"] = data[off: off + 1] == b"*"
        rows.append(row)
    return rows


def utmk_to_wgs84(x, y):
    a, f = 6378137.0, 1 / 298.257222101
    e2 = f * (2 - f)
    ep2 = e2 / (1 - e2)
    k0, x0, y0 = 0.9996, 1000000.0, 2000000.0
    lon0, lat0 = math.radians(127.5), math.radians(38.0)

    def arc(phi):
        return a * ((1 - e2 / 4 - 3 * e2 ** 2 / 64 - 5 * e2 ** 3 / 256) * phi
                    - (3 * e2 / 8 + 3 * e2 ** 2 / 32 + 45 * e2 ** 3 / 1024) * math.sin(2 * phi)
                    + (15 * e2 ** 2 / 256 + 45 * e2 ** 3 / 1024) * math.sin(4 * phi)
                    - (35 * e2 ** 3 / 3072) * math.sin(6 * phi))

    mu = (arc(lat0) + (y - y0) / k0) / (a * (1 - e2 / 4 - 3 * e2 ** 2 / 64 - 5 * e2 ** 3 / 256))
    e1 = (1 - math.sqrt(1 - e2)) / (1 + math.sqrt(1 - e2))
    phi1 = (mu + (3 * e1 / 2 - 27 * e1 ** 3 / 32) * math.sin(2 * mu)
            + (21 * e1 ** 2 / 16 - 55 * e1 ** 4 / 32) * math.sin(4 * mu)
            + (151 * e1 ** 3 / 96) * math.sin(6 * mu)
            + (1097 * e1 ** 4 / 512) * math.sin(8 * mu))
    s, c, t = math.sin(phi1), math.cos(phi1), math.tan(phi1)
    n1 = a / math.sqrt(1 - e2 * s ** 2)
    r1 = a * (1 - e2) / (1 - e2 * s ** 2) ** 1.5
    t1, c1 = t ** 2, ep2 * c ** 2
    d = (x - x0) / (n1 * k0)
    lat = phi1 - (n1 * t / r1) * (d ** 2 / 2 - (5 + 3 * t1 + 10 * c1 - 4 * c1 ** 2 - 9 * ep2) * d ** 4 / 24
                                  + (61 + 90 * t1 + 298 * c1 + 45 * t1 ** 2 - 252 * ep2 - 3 * c1 ** 2) * d ** 6 / 720)
    lon = lon0 + (d - (1 + 2 * t1 + c1) * d ** 3 / 6
                  + (5 - 2 * c1 + 28 * t1 - 3 * c1 ** 2 + 8 * ep2 + 24 * t1 ** 2) * d ** 5 / 120) / c
    return math.degrees(lat), math.degrees(lon)


def simplify(points, tolerance):
    """Douglas–Peucker (평면 근사). points: [(lat, lng)]"""
    if len(points) < 3:
        return points
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        start, end = stack.pop()
        (ay, ax), (by, bx) = points[start], points[end]
        dx, dy = bx - ax, by - ay
        norm = dx * dx + dy * dy
        best, index = 0.0, None
        for i in range(start + 1, end):
            py, px = points[i]
            if norm == 0:
                dist = (px - ax) ** 2 + (py - ay) ** 2
            else:
                u = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / norm))
                dist = (px - ax - u * dx) ** 2 + (py - ay - u * dy) ** 2
            if dist > best:
                best, index = dist, i
        if index is not None and best > tolerance ** 2:
            keep[index] = True
            stack += [(start, index), (index, end)]
    return [p for p, k in zip(points, keep) if k]


def encode_polyline(points, precision=5):
    """[(lat, lng)] → Google Encoded Polyline"""
    factor, prev_lat, prev_lng, out = 10 ** precision, 0, 0, []
    for lat, lng in points:
        ilat, ilng = round(lat * factor), round(lng * factor)
        for delta in (ilat - prev_lat, ilng - prev_lng):
            value = ~(delta << 1) if delta < 0 else delta << 1
            while value >= 0x20:
                out.append(chr((0x20 | (value & 0x1F)) + 63))
                value >>= 5
            out.append(chr(value + 63))
        prev_lat, prev_lng = ilat, ilng
    return "".join(out)
