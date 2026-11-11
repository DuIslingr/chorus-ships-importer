"""Radiance .hdr (RGBE, the new run-length encoding CUE4Parse writes for cube textures as lat-long panoramas) to linear
float rgb, rows top first."""
import numpy as np


def read(path):
    data = open(path, 'rb').read()
    head, pos = [], 0
    while True:
        end = data.index(b'\n', pos)
        line = data[pos:end].decode('ascii', 'replace'); pos = end + 1
        if line.startswith('-Y') or line.startswith('+Y'):
            parts = line.split(); h, w = int(parts[1]), int(parts[3]); break
        head.append(line)
    out = np.zeros((h, w, 4), np.uint8)
    for y in range(h):
        if data[pos] == 2 and data[pos + 1] == 2 and (data[pos + 2] << 8 | data[pos + 3]) == w:
            pos += 4
            for c in range(4):
                x = 0
                while x < w:
                    n = data[pos]; pos += 1
                    if n > 128:
                        n -= 128; out[y, x:x + n, c] = data[pos]; pos += 1
                    else:
                        out[y, x:x + n, c] = np.frombuffer(data, np.uint8, n, pos); pos += n
                    x += n
        else:   # (a flat scanline)
            out[y] = np.frombuffer(data, np.uint8, w * 4, pos).reshape(w, 4); pos += w * 4
    e = out[..., 3].astype(np.int32)
    scale = np.where(e > 0, np.ldexp(1.0, e - 136), 0.0)
    return out[..., :3].astype(np.float64) * scale[..., None]
