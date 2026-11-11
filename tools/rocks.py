"""Chorus's asteroids (ArtAssets/Environment/Asteroids) for the remake's orbits: the field asteroids as an orbit's
"asteroids" "models" (mined like the game's), the giant ones and the split rocks as "props" (Modding/README "orbit").

Their materials are baked into one texture set per rock over its own UV set 0 (everything the masters read is a function
of it), from the masters' compiled base passes:

    M_MaskBlend_Placeholder (MI_FieldAsteroid_00x, MI_CapitalAsteroid_008-012, MI_SplitAsteroid): two tiled rock layers,
      A (uv x A - Tiling + its shift) and B (x B - Tiling), blended by the Mesh Mask (its channel by Mesh Mask Channel):
      colour saturate(lerp(A x 0.3, B, m)), metal saturate(lerp(A.M x 0.01, B.M, m)), roughness lerp(A.R, B.R, m),
      occlusion lerp(A.O, B.O, m); the normal lerp(A, B, m) laid over the Mesh Normal by Unreal's angle-corrected blend;
      specular 0.5; no glow (its emissive is the editor's selection colour).
"""
import json, os
import numpy as np
from PIL import Image
from . import glb, textures

UP = 'SpacePrototype/Content/UnleashedPrototype/'
ROCKS = UP + 'ArtAssets/Environment/Asteroids/'
FIELD = [ROCKS + f'SM_FieldAsteroid_{i:03d}' for i in range(1, 6)]
GIANT = [ROCKS + f'SM_CapitalAsteroid_{i:03d}' for i in (8, 9, 10, 11, 12)] + [ROCKS + f'SM_SplitAsteroid_{i:03d}' for i in (1, 2)]
EXPORTS = FIELD + GIANT
BAKE = {'field': 1024, 'giant': 2048}


def _srgb_to_linear(c): return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def _load(path, srgb):
    a = np.asarray(Image.open(path).convert('RGBA'), np.float32) / 255.0
    if srgb: a[..., :3] = _srgb_to_linear(a[..., :3])
    return a


def _sample(img, u, v, wrap=True):
    """Bilinear at Unreal's UVs (v down: the image's rows)."""
    h, w = img.shape[:2]
    x = u * w - 0.5; y = v * h - 0.5
    x0 = np.floor(x).astype(np.int64); y0 = np.floor(y).astype(np.int64)
    fx = (x - x0)[..., None]; fy = (y - y0)[..., None]
    if wrap: x0 %= w; y0 %= h; x1 = (x0 + 1) % w; y1 = (y0 + 1) % h
    else: x0 = np.clip(x0, 0, w - 1); y0 = np.clip(y0, 0, h - 1); x1 = np.clip(x0 + 1, 0, w - 1); y1 = np.clip(y0 + 1, 0, h - 1)
    return img[y0, x0] * (1 - fx) * (1 - fy) + img[y0, x1] * fx * (1 - fy) + img[y1, x0] * (1 - fx) * fy + img[y1, x1] * fx * fy


def _unpack(t):
    n = t[..., :2] * 2.0 - 1.0
    return np.concatenate([n, np.sqrt(np.maximum(1.0 - (n * n).sum(-1, keepdims=True), 0.0))], -1)


def _blend_angle_corrected(base, detail):
    """Unreal's BlendAngleCorrectedNormals as the compiled pass has it: t = detail + (0, 0, 1), u = base with x, y negated,
    normalize(t x dot(t, u) - u x t.z)."""
    t = detail + np.array([0.0, 0.0, 1.0])
    u = base * np.array([-1.0, -1.0, 1.0])
    r = t * (t * u).sum(-1, keepdims=True) - u * t[..., 2:3]
    return r / np.maximum(np.linalg.norm(r, axis=-1, keepdims=True), 1e-8)


def bake_mask_blend(p, png, size):
    """M_MaskBlend_Placeholder over UV set 0: -> (colour linear rgb, metal, roughness, occlusion, normal) at size x size."""
    v, u = np.meshgrid((np.arange(size) + 0.5) / size, (np.arange(size) + 0.5) / size, indexing='ij')
    ta, tb = p.scalar('A - Tiling', 1.0), p.scalar('B - Tiling', 1.0)
    ua, va = u * ta + p.scalar('A - Shift  U'), v * ta + p.scalar('A - Shift V')
    ub, vb = u * tb + p.scalar('B - Shift  U'), v * tb + p.scalar('B - Shift V')
    chan = np.asarray((p.vector('Mesh Mask Channel') or [1, 0, 0]) + [0.0])[:4]
    m = (_sample(png('Mesh Mask', False), u, v, False) * chan).sum(-1)[..., None]
    ca, cb = _sample(png('A - Diffuse', True), ua, va)[..., :3], _sample(png('B - Diffuse', True), ub, vb)[..., :3]
    colour = np.clip(ca * 0.3 + (cb - ca * 0.3) * m, 0, 1)
    ma, mb = _sample(png('A - MRO', False), ua, va), _sample(png('B - MRO', False), ub, vb)
    metal = np.clip(ma[..., 0] * 0.01 + (mb[..., 0] - ma[..., 0] * 0.01) * m[..., 0], 0, 1)
    rough = np.clip(ma[..., 1] + (mb[..., 1] - ma[..., 1]) * m[..., 0], 0, 1)
    occl = np.clip(ma[..., 2] + (mb[..., 2] - ma[..., 2]) * m[..., 0], 0, 1)
    na, nb = _unpack(_sample(png('A - Normal', False), ua, va)), _unpack(_sample(png('B - Normal', False), ub, vb))
    detail = na + (nb - na) * m
    base = _unpack(_sample(png('Mesh Normal', False), u, v, False))
    return colour, metal, rough, occl, _blend_angle_corrected(base, detail)


def _write_maps(mod, stem, colour, metal, rough, occl, normal):
    maps = os.path.join(mod, 'maps', 'rocks'); os.makedirs(maps, exist_ok=True)
    rel = lambda s: f'maps/rocks/{stem}_{s}.png'
    # (Unreal's ambient occlusion darkens the sky light only; the remake's materials have no slot: folded into the colour
    #  at half, the light it leaves)
    c = colour * (0.5 + 0.5 * occl[..., None])
    textures._save(textures.linear_to_srgb(c), os.path.join(mod, rel('c')), 0, 'RGB')
    ms = np.stack([metal, np.zeros_like(metal), np.zeros_like(metal), 1.0 - rough], -1)
    textures._save(ms, os.path.join(mod, rel('ms')), 0, 'RGBA')
    textures._save(textures.flip_normal(normal * 0.5 + 0.5), os.path.join(mod, rel('n')), 0, 'RGB')
    return {'diffuse': rel('c'), 'metallicSmoothness': rel('ms'), 'normal': rel('n')}


def build(export, mod, resolver):
    """-> {'field': (models, materials), 'giant': (models, materials)} for stations.json orbits."""
    from . import npcs
    out = {}
    for group, meshes in (('field', FIELD), ('giant', GIANT)):
        models, mats = [], []
        for path in meshes:
            src = os.path.join(export, path + '.glb')
            if not os.path.exists(src): print(f'  rock {path}: not exported'); continue
            prims = glb.static_mesh(src, keep=npcs.KEEP)
            name = path.rsplit('/', 1)[-1]
            for mat in sorted({m for m, _, _ in prims}):
                if any(e['material'] == mat for e in mats): continue
                mi, mpath = npcs._find_mi(export, mat)
                p = resolver.get(mpath) if mpath else None
                if p is None or p.chain[-1] != 'M_MaskBlend_Placeholder':
                    print(f'  rock {name}: {mat} ({p.chain[-1] if p else "?"}) not a mask blend: left out'); continue
                resolver.fetch_textures(list(p.texture_paths.values()), export)
                cache = {}
                def png(param, srgb):
                    t = p.textures.get(param)
                    f = os.path.join(export, (p.texture_paths.get(t) or '') + '.png')
                    if (param, srgb) not in cache: cache[(param, srgb)] = _load(f, srgb) if os.path.exists(f) else np.full((4, 4, 4), 0.5, np.float32)
                    return cache[(param, srgb)]
                mats.append({'material': mat, **_write_maps(mod, mat.lower(), *bake_mask_blend(p, png, BAKE[group]))})
            rel = f'models/rocks/{name}.glb'
            os.makedirs(os.path.join(mod, 'models', 'rocks'), exist_ok=True)
            keep = [(m, a, i) for m, a, i in prims if any(e['material'] == m for e in mats)]
            if not keep: continue
            glb.save(os.path.join(mod, rel), keep, name)
            models.append(rel)
            print(f'  rock {name}: {len(keep)} parts')
        out[group] = (models, mats)
    return out
