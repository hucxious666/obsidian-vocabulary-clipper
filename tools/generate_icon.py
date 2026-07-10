import binascii
import struct
import zlib
from pathlib import Path


SIZE = 128
SCALE = 4
PURPLE = (111, 85, 217)
WHITE = (255, 255, 255)
W_POLYGON = [(27, 34), (44, 34), (54, 80), (64, 47), (77, 47), (87, 80), (96, 34), (112, 34), (96, 96), (80, 96), (70, 65), (59, 96), (43, 96)]


def inside_polygon(x, y, polygon):
    inside = False
    previous = polygon[-1]
    for current in polygon:
        x1, y1 = previous
        x2, y2 = current
        if (y1 > y) != (y2 > y):
            boundary = (x2 - x1) * (y - y1) / (y2 - y1) + x1
            if x < boundary:
                inside = not inside
        previous = current
    return inside


def inside_rounded_square(x, y):
    radius = 28
    if radius <= x < SIZE - radius or radius <= y < SIZE - radius:
        return 0 <= x < SIZE and 0 <= y < SIZE
    center_x = radius if x < radius else SIZE - radius
    center_y = radius if y < radius else SIZE - radius
    return (x - center_x) ** 2 + (y - center_y) ** 2 <= radius ** 2


def pixel(x, y):
    purple_samples = 0
    white_samples = 0
    for sy in range(SCALE):
        for sx in range(SCALE):
            px = x + (sx + 0.5) / SCALE
            py = y + (sy + 0.5) / SCALE
            if inside_rounded_square(px, py):
                purple_samples += 1
                if inside_polygon(px, py, W_POLYGON):
                    white_samples += 1
    total = SCALE * SCALE
    alpha = round(255 * purple_samples / total)
    if purple_samples == 0:
        return (0, 0, 0, 0)
    white_mix = white_samples / purple_samples
    rgb = tuple(round(PURPLE[i] * (1 - white_mix) + WHITE[i] * white_mix) for i in range(3))
    return (*rgb, alpha)


def chunk(kind, data):
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", binascii.crc32(kind + data) & 0xFFFFFFFF)


def main():
    rows = []
    for y in range(SIZE):
        row = bytearray([0])
        for x in range(SIZE):
            row.extend(pixel(x, y))
        rows.append(bytes(row))
    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", SIZE, SIZE, 8, 6, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(b"".join(rows), 9))
    png += chunk(b"IEND", b"")
    target = Path(__file__).resolve().parents[1] / "extension" / "icon.png"
    target.write_bytes(png)
    print(target)


if __name__ == "__main__":
    main()
