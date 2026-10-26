#!/usr/bin/env python3
"""Build helpers for the win95_savers badge app (no third-party packages).

  python3 tools/win95_savers.py mark            # print the flattened GitHub mark
  python3 tools/win95_savers.py build [--output DIR]

`mark` flattens the MIT-licensed Primer Octicons `mark-github-24` path into
the normalised polygon embedded in the app. `build` draws the 24x24 menu icon
and writes an installable `win95_savers.zip`.
"""

import argparse
import math
from pathlib import Path
import re
import struct
import zipfile
import zlib

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "apps/win95_savers"

# primer/octicons icons/mark-github-24.svg (MIT License, GitHub Inc.)
MARK_PATH = (
    "M10.226 17.284c-2.965-.36-5.054-2.493-5.054-5.256 0-1.123.404-2.336 1.078-3.144"
    "-.292-.741-.247-2.314.09-2.965.898-.112 2.111.36 2.83 1.01.853-.269 1.752-.404 "
    "2.853-.404 1.1 0 1.999.135 2.807.382.696-.629 1.932-1.1 2.83-.988.315.606.36 "
    "2.179.067 2.942.72.854 1.101 2 1.101 3.167 0 2.763-2.089 4.852-5.098 5.234.763"
    ".494 1.28 1.572 1.28 2.807v2.336c0 .674.561 1.056 1.235.786 4.066-1.55 7.255-5"
    ".615 7.255-10.646C23.5 6.188 18.334 1 11.978 1 5.62 1 .5 6.188.5 12.545c0 4.986 "
    "3.167 9.12 7.435 10.669.606.225 1.19-.18 1.19-.786V20.63a2.9 2.9 0 0 1-1.078"
    ".224c-1.483 0-2.359-.808-2.987-2.313-.247-.607-.517-.966-1.034-1.033-.27-.023-"
    ".359-.135-.359-.27 0-.27.45-.471.898-.471.652 0 1.213.404 1.797 1.235.45.651"
    ".921.943 1.483.943.561 0 .92-.202 1.437-.719.382-.381.674-.718.944-.943"
)


def tokens(path):
    for item in re.finditer(r"[A-Za-z]|-?(?:\d+\.?\d*|\.\d+)(?:e-?\d+)?", path):
        yield item.group()


def arc_points(x0, y0, rx, ry, phi, large, sweep, x1, y1, steps=10):
    # SVG endpoint arc to centre parameterisation (SVG 1.1 appendix F.6.5).
    phi = math.radians(phi)
    cos_p, sin_p = math.cos(phi), math.sin(phi)
    dx, dy = (x0 - x1) / 2, (y0 - y1) / 2
    x_, y_ = cos_p * dx + sin_p * dy, -sin_p * dx + cos_p * dy
    scale = (x_ * x_) / (rx * rx) + (y_ * y_) / (ry * ry)
    if scale > 1:
        rx, ry = rx * math.sqrt(scale), ry * math.sqrt(scale)
    num = rx * rx * ry * ry - rx * rx * y_ * y_ - ry * ry * x_ * x_
    den = rx * rx * y_ * y_ + ry * ry * x_ * x_
    coef = math.sqrt(max(0, num / den)) * (-1 if large == sweep else 1)
    cx_, cy_ = coef * rx * y_ / ry, -coef * ry * x_ / rx
    cx = cos_p * cx_ - sin_p * cy_ + (x0 + x1) / 2
    cy = sin_p * cx_ + cos_p * cy_ + (y0 + y1) / 2
    start = math.atan2((y_ - cy_) / ry, (x_ - cx_) / rx)
    end = math.atan2((-y_ - cy_) / ry, (-x_ - cx_) / rx)
    delta = end - start
    if sweep and delta < 0:
        delta += math.tau
    elif not sweep and delta > 0:
        delta -= math.tau
    points = []
    for i in range(1, steps + 1):
        a = start + delta * i / steps
        x, y = rx * math.cos(a), ry * math.sin(a)
        points.append((cos_p * x - sin_p * y + cx, sin_p * x + cos_p * y + cy))
    return points


def flatten(path, steps=6):
    items = list(tokens(path))
    points = []
    x = y = 0
    command = None
    i = 0

    def num():
        nonlocal i
        i += 1
        return float(items[i - 1])

    while i < len(items):
        if items[i].isalpha():
            command = items[i]
            i += 1
        rel = command.islower()
        op = command.upper()
        ox, oy = (x, y) if rel else (0, 0)
        if op == "M":
            x, y = num() + ox, num() + oy
            points.append((x, y))
            command = "l" if rel else "L"
        elif op == "L":
            x, y = num() + ox, num() + oy
            points.append((x, y))
        elif op == "H":
            x = num() + ox
            points.append((x, y))
        elif op == "V":
            y = num() + oy
            points.append((x, y))
        elif op == "C":
            c1 = (num() + ox, num() + oy)
            c2 = (num() + ox, num() + oy)
            end = (num() + ox, num() + oy)
            for s in range(1, steps + 1):
                t = s / steps
                mt = 1 - t
                points.append((
                    mt ** 3 * x + 3 * mt * mt * t * c1[0] + 3 * mt * t * t * c2[0] + t ** 3 * end[0],
                    mt ** 3 * y + 3 * mt * mt * t * c1[1] + 3 * mt * t * t * c2[1] + t ** 3 * end[1],
                ))
            x, y = end
        elif op == "A":
            rx, ry, phi, large, sweep = num(), num(), num(), int(num()), int(num())
            end = (num() + ox, num() + oy)
            points.extend(arc_points(x, y, rx, ry, phi, large, sweep, *end))
            x, y = end
        elif op == "Z":
            pass
        else:
            raise ValueError("Unsupported path command " + command)
    return points


def simplify(points, tolerance):
    kept = [points[0]]
    for point in points[1:]:
        if math.dist(point, kept[-1]) >= tolerance:
            kept.append(point)
    if math.dist(kept[0], kept[-1]) < tolerance:
        kept.pop()
    return kept


def mark_polygon():
    points = simplify(flatten(MARK_PATH), 0.5)
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    half = max(max(xs) - min(xs), max(ys) - min(ys)) / 2
    return [((px - cx) / half, (py - cy) / half) for px, py in points]


def inside(polygon, x, y):
    winding = 0
    count = len(polygon)
    for i in range(count):
        x0, y0 = polygon[i]
        x1, y1 = polygon[(i + 1) % count]
        if y0 <= y < y1 or y1 <= y < y0:
            if x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
                winding += 1 if y1 > y0 else -1
    return winding != 0


def png(width, height, pixels):
    def chunk(kind, data):
        return (struct.pack(">I", len(data)) + kind + data
                + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF))
    raw = bytearray()
    for row in range(height):
        raw.append(0)
        for col in range(width):
            raw.extend(pixels[row * width + col])
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + chunk(b"IEND", b""))


def icon(size=24):
    # A Win95-style beige monitor on a teal desktop, showing the GitHub mark
    # in the four Windows flag colours.
    teal, beige, shadow, light = (0, 128, 128), (192, 192, 192), (96, 96, 96), (255, 255, 255)
    black = (0, 0, 0)
    flag = ((237, 28, 36), (34, 177, 76), (0, 120, 215), (255, 201, 14))
    polygon = mark_polygon()
    pixels = []
    s = size / 48
    for y in range(size):
        for x in range(size):
            u, v = x / s, y / s
            colour = teal
            if 6 <= u < 42 and 4 <= v < 34:
                colour = beige
                if u < 7 or v < 5:
                    colour = light
                elif u >= 41 or v >= 33:
                    colour = shadow
                if 10 <= u < 38 and 8 <= v < 30:
                    colour = black
                    hits = [0, 0, 0, 0]
                    total = 0
                    for sy in range(4):
                        for sx in range(4):
                            px = (u + (sx + 0.5) / 4 / s - 24) / 10
                            py = (v + (sy + 0.5) / 4 / s - 19) / 10
                            if inside(polygon, px, py):
                                hits[(px >= 0) + 2 * (py >= 0)] += 1
                                total += 1
                    if total:
                        quad = max(range(4), key=lambda q: hits[q])
                        colour = tuple(int(c * total / 16) for c in flag[quad])
            elif 18 <= u < 30 and 34 <= v < 39:
                colour = beige
            elif 12 <= u < 36 and 39 <= v < 43:
                colour = beige if v < 42 else shadow
            pixels.append(colour)
    return png(size, size, pixels)


def build(output):
    (APP / "icon.png").write_bytes(icon())
    output.mkdir(parents=True, exist_ok=True)
    package = output / "win95_savers.zip"
    with zipfile.ZipFile(package, "w", zipfile.ZIP_DEFLATED) as archive:
        for filename in ("__init__.py", "icon.png", "README.md"):
            archive.write(APP / filename, "win95_savers/" + filename)
    print(f"Icon: {APP / 'icon.png'}")
    print(f"Installable package: {package}")


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("mark", help="print the flattened mark polygon")
    build_parser = sub.add_parser("build", help="write icon.png and win95_savers.zip")
    build_parser.add_argument("--output", type=Path, default=ROOT / "dist/win95_savers")
    args = parser.parse_args()
    if args.command == "mark":
        points = mark_polygon()
        print(f"# {len(points)} points")
        print("MARK = (" + ", ".join(f"({x:.3f}, {y:.3f})" for x, y in points) + ")")
    else:
        build(args.output.resolve())


if __name__ == "__main__":
    main()
