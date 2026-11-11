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
    peak = float(acc.max())
    if peak <= 1e-4: return None
    return linear_to_srgb(acc / peak), peak


def convert_material(src_dir, tex_names, colours, dst_dir, name, size=2048, small=1024):
    """Writes <name>_c / _n / _ms (/ _e) .png and returns the ships.json material entry's map fields."""
    def find(t): return os.path.join(src_dir, t + '.png') if t and os.path.exists(os.path.join(src_dir, t + '.png')) else None
    out = {}
    d, n, rmo, e = (find(tex_names.get(k)) for k in ('diffuse', 'normal', 'rmo', 'emissive'))
    rmo_a = _load(rmo) if rmo else None
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
