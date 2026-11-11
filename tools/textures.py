# Chorus's ship maps -> the remake's (URP Lit through ships.json "materials", Modding/README "materials"):
#   _D   base colour (sRGB)            -> <name>_c.png, times the ambient occlusion (RMO blue), softened
#   _N   normal, DirectX (green down)  -> <name>_n.png, green flipped (Unity: green up)
#   _RMO roughness / metallic / AO     -> <name>_ms.png: metallic in R (and G, B), smoothness = 1 - roughness in A
#   _E   emissive masks                -> <name>_e.png: G x Emissive02 + B x Emissive03 (the material instance's colours and
#        multipliers; R, Emissive01, is unused on the Forsaken), normalised; the peak goes to emissionIntensity
import os
import numpy as np
from PIL import Image

AO_STRENGTH = 0.6   # how much of the baked AO darkens the colour map (URP Lit has no AO slot through ships.json)


def _load(path):
    return np.asarray(Image.open(path).convert('RGBA')).astype(np.float32) / 255.0


def _save(arr, path, size, mode):
    im = Image.fromarray((np.clip(arr, 0, 1) * 255 + 0.5).astype(np.uint8), mode)
    if size and im.size[0] > size: im = im.resize((size, size), Image.LANCZOS)
    im.save(path, optimize=True)


def srgb_to_linear(c): return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
def linear_to_srgb(c): return np.where(c <= 0.0031308, c * 12.92, 1.055 * np.power(np.maximum(c, 0), 1 / 2.4) - 0.055)


def convert_rmo(rmo):
    """RMO (R roughness, G metallic, B AO) -> URP metallic / smoothness (R metallic, A smoothness)."""
    ms = np.zeros_like(rmo)
    ms[..., 0] = ms[..., 1] = ms[..., 2] = rmo[..., 1]
    ms[..., 3] = 1.0 - rmo[..., 0]
    return ms


def flip_normal(n):
    out = n.copy(); out[..., 1] = 1.0 - out[..., 1]; return out


def emission(e, colours):
    """e: the _E mask map; colours: [(channel index, linear rgb, multiplier)]. -> (sRGB map normalised, peak) or None."""
    acc = np.zeros(e.shape[:2] + (3,), np.float32)
    for ch, rgb, mult in colours:
        if mult <= 0: continue
        acc += e[..., ch:ch + 1] * np.asarray(rgb, np.float32)[None, None, :] * mult
    lit = acc.max(-1)
    lit = lit[lit > 1e-3]
    if lit.size == 0: return None
    # the brightness the glow is scaled to: its 99.9th percentile, so a few stray pixels of a bright channel don't dim
    # the rest (the supercharged Forsaken's masks: Emissive03's x20 on a handful of pixels)
    peak = float(np.percentile(lit, 99.9))
    if peak <= 1e-4: return None
    return linear_to_srgb(np.clip(acc / peak, 0, 1)), peak


def convert_material(src_dir, tex_names, colours, dst_dir, name, size=2048, small=1024, layout='RMO'):
    """Writes <name>_c / _n / _ms (/ _e) .png and returns the ships.json material entry's map fields. layout: the specular
    map's channels, 'RMO' (R roughness, G metallic, B AO: the Forsaken's), 'MRO' (R metallic, G roughness: the Argus's) or
    'ORM' (R occlusion, G roughness, B metal: Sav's and Ree's floaters)."""
    def find(t): return os.path.join(src_dir, t + '.png') if t and os.path.exists(os.path.join(src_dir, t + '.png')) else None
    out = {}
    d, n, rmo, e = (find(tex_names.get(k)) for k in ('diffuse', 'normal', 'rmo', 'emissive'))
    rmo_a = _load(rmo) if rmo else None
    if rmo_a is not None and layout == 'MRO': rmo_a = rmo_a[..., [1, 0, 2, 3]]
    if rmo_a is not None and layout == 'ORM': rmo_a = rmo_a[..., [1, 2, 0, 3]]   # (R occlusion, G roughness, B metal)
    if d:
        c = _load(d)[..., :3]
        if rmo_a is not None:
            ao = rmo_a[..., 2:3]
            if ao.shape[:2] != c.shape[:2]:
                ao = np.asarray(Image.fromarray((ao[..., 0] * 255).astype(np.uint8)).resize(c.shape[1::-1], Image.BILINEAR), np.float32)[..., None] / 255.0
            c = linear_to_srgb(srgb_to_linear(c) * (1.0 - AO_STRENGTH * (1.0 - ao)))
        _save(c, os.path.join(dst_dir, name + '_c.png'), size, 'RGB'); out['diffuse'] = f'maps/{name}_c.png'
    if n:
        _save(flip_normal(_load(n))[..., :3], os.path.join(dst_dir, name + '_n.png'), size, 'RGB'); out['normal'] = f'maps/{name}_n.png'
    if rmo_a is not None:
        _save(convert_rmo(rmo_a), os.path.join(dst_dir, name + '_ms.png'), small, 'RGBA'); out['metallicSmoothness'] = f'maps/{name}_ms.png'
    if e:
        r = emission(_load(e), colours)
        if r is not None:
            _save(r[0], os.path.join(dst_dir, name + '_e.png'), small, 'RGB')
            out['emission'] = f'maps/{name}_e.png'; out['emissionColor'] = [1, 1, 1]; out['emissionIntensity'] = round(r[1], 3)
    return out



def rasterize(uv, idx, size):
    """Which triangle covers each texel of a size x size map over the UVs uv (0..1), and where in it: -> (tri: size x
    size int, -1 where uncovered; bary: size x size x 3 weights of the triangle's corners)."""
    tri = np.full((size, size), -1, np.int32); bary = np.zeros((size, size, 3), np.float32)
    p = np.asarray(uv, np.float64) * size - 0.5
    for t, (a, b, c) in enumerate(np.asarray(idx).reshape(-1, 3)):
        (x0, y0), (x1, y1), (x2, y2) = p[a], p[b], p[c]
        d = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
        if abs(d) < 1e-12: continue
        lx, hx = max(int(np.floor(min(x0, x1, x2))), 0), min(int(np.ceil(max(x0, x1, x2))), size - 1)
        ly, hy = max(int(np.floor(min(y0, y1, y2))), 0), min(int(np.ceil(max(y0, y1, y2))), size - 1)
        if lx > hx or ly > hy: continue
        X, Y = np.meshgrid(np.arange(lx, hx + 1), np.arange(ly, hy + 1))
        w0 = ((y1 - y2) * (X - x2) + (x2 - x1) * (Y - y2)) / d
        w1 = ((y2 - y0) * (X - x2) + (x0 - x2) * (Y - y2)) / d
        w2 = 1 - w0 - w1
        m = (w0 >= -0.02) & (w1 >= -0.02) & (w2 >= -0.02)
        if not m.any(): continue
        tri[ly:hy + 1, lx:hx + 1][m] = t
        bary[ly:hy + 1, lx:hx + 1][m] = np.stack([w0[m], w1[m], w2[m]], -1)
    return tri, bary


def interpolate(attr, idx, tri, bary):
    """A per-vertex attribute (n x k) at every covered texel (rasterize's tri / bary) -> size x size x k (0 elsewhere)."""
    corners = np.asarray(idx).reshape(-1, 3)[np.maximum(tri, 0)]          # size x size x 3 vertex indices
    a = np.asarray(attr, np.float32)
    out = (a[corners] * bary[..., None]).sum(-2)
    out[tri < 0] = 0
    return out


def dilate(img, covered, steps=4):
    """Grows the covered texels' values into their uncovered neighbours (no dark seams under filtering)."""
    img, cov = img.copy(), covered.copy()
    for _ in range(steps):
        grown, g = img.copy(), cov.copy()
        for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            src, sc = np.roll(img, (dy, dx), (0, 1)), np.roll(cov, (dy, dx), (0, 1))
            fill = sc & ~g; grown[fill] = src[fill]; g |= fill
        img, cov = grown, g
    return img


def sample(tex, uv):
    """Nearest texel of tex (h x w x k) at the UVs uv (... x 2, wrapping)."""
    h, w = tex.shape[:2]
    x = (np.mod(uv[..., 0], 1.0) * w).astype(np.int64) % w
    y = (np.mod(uv[..., 1], 1.0) * h).astype(np.int64) % h
    return tex[y, x]


def bake_vertex_colours(uv, colours, idx, size=1024):
    """Per-vertex colours (n x 3, linear) interpolated across each triangle and drawn over its UVs (0..1, unique) -> a
    size x size x 3 float image (linear)."""
    tri, bary = rasterize(uv, idx, size)
    return dilate(interpolate(colours, idx, tri, bary), tri >= 0)
