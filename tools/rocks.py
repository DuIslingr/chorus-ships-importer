"""Chorus's asteroids (ArtAssets/Environment/Asteroids) for the remake's orbits: the field asteroids as an orbit's
"asteroids" "models" (mined like the game's), the giant ones and the split rocks as "props" (Modding/README "orbit").

Their materials are baked into one texture set per rock over its own UV set 0 (everything the masters read is a function
of it), from the masters' compiled base passes:

    M_MaskBlend_Placeholder (MI_FieldAsteroid_00x, MI_CapitalAsteroid_008-012, MI_SplitAsteroid): two tiled rock layers,
      A (uv x A - Tiling + its shift) and B (x B - Tiling), blended by the Mesh Mask (its channel by Mesh Mask Channel):
      colour saturate(lerp(A x 0.3, B, m)), metal saturate(lerp(A.M x 0.01, B.M, m)), roughness lerp(A.R, B.R, m),
      occlusion lerp(A.O, B.O, m); the normal lerp(A, B, m) laid over the Mesh Normal by Unreal's angle-corrected blend;
      specular 0.5; no glow (its emissive is the editor's selection colour).
    M_Asteroid_Master, "is Magma Asteroid" (MI_Asteroid_Capital01 on SM_CapitalAsteroid_001-006, MI_Asteroid_JantuTemple01
      on the destroyed moon's SM_Moon_Destroyed_*): the mesh's maps (Mesh Normal, Mesh OCE: occlusion, curvature,
      emissive) at UV set 0 x Mesh UV Tiling, the tiled magma (Tileable Magma Normal, ORDE: occlusion, roughness, detail
      albedo, emissive) at (UV set 0 + offset) x Tiling (the rock as made: its actor scale 1). Colour: the CA_AsteroidColor
      row Albedo LUT at saturate(a x (1 - concavity x Mesh Concavities Intensity)), a = the detail albedo against
      Background Albedo (by Tileable Albedo Intensity; with "Allow Vertex Color Masking (R)" by the vertex colour's red) x
      the mesh occlusion + the curvature x Curvature Color Influence, times Master Brightness. Roughness: a chain of
      blends (concavities, convexities over their threshold, the curvature, the glowing parts) between Roughness Min and
      Max. Glow: blackbody colours (Unreal's BlackBody: Planck's locus by Kang et al., x (T / 2500)^4): the mesh's at a
      temperature from Mesh Min Temperature x (1 - curvature) up to Mesh Max by its emissive mask, x Glow Tint x Mesh
      Emissive Scale; the tiled magma's between Tileable Min and Max Temp, desaturated, x Glow Tint x Tileable Emissive
      Scale x the vertex colour's green and blue (and, with "Use Mesh Emissive Mask", the mesh's emissive map). Baked over
      the rock's unique layout (UV set 2 or 1: the vertex colours and the tiled UV set 0 interpolated per texel).
"""
import json, os
import numpy as np
from PIL import Image
from . import glb, textures

UP = 'SpacePrototype/Content/UnleashedPrototype/'
ROCKS = UP + 'ArtAssets/Environment/Asteroids/'
FIELD = [ROCKS + f'SM_FieldAsteroid_{i:03d}' for i in range(1, 6)]
MAGMA = [ROCKS + f'SM_CapitalAsteroid_{i:03d}' for i in (1, 2, 3, 4, 6)] + [ROCKS + f'SM_Moon_Destroyed_{i:02d}' for i in range(1, 9)]
ALBEDO_ATLAS = ROCKS + 'Generic/CA_AsteroidColor'
GIANT = [ROCKS + f'SM_CapitalAsteroid_{i:03d}' for i in (8, 9, 10, 11, 12)] + [ROCKS + f'SM_SplitAsteroid_{i:03d}' for i in (1, 2)]
EXPORTS = FIELD + GIANT + MAGMA
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


def blackbody(T):
    """Unreal's BlackBody(Temp): linear rgb x (T x 0.0004)^4."""
    T = np.asarray(T, np.float64)
    u = (0.860117757 + 1.54118254e-4 * T + 1.28641212e-7 * T * T) / (1 + 8.42420235e-4 * T + 7.08145163e-7 * T * T)
    v = (0.317398726 + 4.22806245e-5 * T + 4.20481691e-8 * T * T) / (1 - 2.89741816e-5 * T + 1.61456053e-7 * T * T)
    d = 2 * u - 8 * v + 4
    x, y = 3 * u / d, 2 * v / d
    X, Z = x / y, (1 - x - y) / y
    rgb = np.stack([3.2404542 * X - 1.5371385 - 0.4985314 * Z, -0.9692660 * X + 1.8760108 + 0.0415560 * Z,
                    0.0556434 * X - 0.2040259 + 1.0572252 * Z], -1)
    return rgb * ((T * 0.0004) ** 4)[..., None]


def _pow0(x, e): return np.where(x > 0, np.power(np.maximum(x, 1e-12), e), 0.0)


def bake_magma(attrs, idx, p, png, lut, size):
    """M_Asteroid_Master's magma permutations over the rock's unique layout (attrs['LAYOUT']). -> (colour linear, metal,
    roughness, occlusion 1, normal in the layout's frame, emission linear, covered)."""
    from . import npcs, textures as tx
    tri, bary = tx.rasterize(attrs['LAYOUT'], idx, size)
    cov = tri >= 0
    uv0 = tx.interpolate(attrs['TEXCOORD_0'], idx, tri, bary).astype(np.float64)
    vc = attrs.get('COLOR_0')
    vc = np.ones((len(attrs['POSITION']), 3), np.float32) if vc is None or float(np.abs(vc[:, :3]).max()) < 1e-6 else vc[:, :3]
    c = tx.interpolate(vc, idx, tri, bary)
    sw = lambda n, d=False: bool(p.switches.get(n, d))
    s_ = p.scalar
    uvM = uv0 * s_('Mesh UV Tiling for Capitals', 1.0)
    uvT = (uv0 + [s_('Tileable Offet X'), s_('Tilable Offset Y')]) * s_('Tiling (at 100% scale)', 1.0)
    mn = _unpack(_sample(png('Mesh Normal', False), uvM[..., 0], uvM[..., 1]))
    mn[..., :2] *= s_('Mesh Normalmap Intensity', 1.0)
    tn = _unpack(_sample(png('Tileable Magma Normal', False), uvT[..., 0], uvT[..., 1]))
    tn[..., :2] *= s_('Tileable Normal Intensity', 1.0)
    vcr = sw('Allow Vertex Color Masking (R)')
    if vcr: tn = (tn - [0, 0, 1]) * c[..., 0:1] + [0, 0, 1]
    ts = _blend_angle_corrected(tn, mn)
    oce = _sample(png('Mesh OCE', False), uvM[..., 0], uvM[..., 1])
    orde = _sample(png('Tileable Magma ORDE', False), uvT[..., 0], uvT[..., 1])
    O, C, E = oce[..., 0], oce[..., 1], oce[..., 2]
    tO, tR, tD, tE = orde[..., 0], orde[..., 1], orde[..., 2], orde[..., 3]
    sharp, strength = s_('Mesh Emissive Mask Sharpness', 1.0), s_('Mesh Emissive Mask Strength', 1.0)
    mask = np.clip((1 - tO) * _pow0(E, sharp) * strength, 0, 1)
    tmin = s_('Mesh Min Temperature') * (1 - C)
    Tm = tmin + (s_('Mesh Max Temperature') - tmin) * mask
    tint = np.asarray(p.vector('GlowTint') or [1, 0.03, 0], np.float64)
    glow = blackbody(Tm) * tint * s_('Mesh Emissive Scale', 1.0)
    te = np.minimum(np.abs(tE), 1.0)
    Tt = s_('Tileable Min Temp') + (s_('Tileable Max Temp') - s_('Tileable Min Temp')) * te
    bt = blackbody(Tt)
    grey = (bt * [0.3, 0.59, 0.11]).sum(-1, keepdims=True)
    bt = bt + (grey - bt) * s_('Magma desaturation')
    bt = bt * tint * s_('Tileable Emissive Scale', 1.0) * c[..., 2:3] * c[..., 1:2]
    if sw('Use Mesh Emissive Mask'):
        e0 = _sample(png('Mesh OCE', False), uv0[..., 0], uv0[..., 1])[..., 2]
        bt = bt * np.clip(_pow0(e0, sharp) * strength, 0, 1)[..., None]
    glow = glow + bt
    bg, tai = s_('Background Albedo', 0.5), s_('Tileable Albedo Intensity', 1.0)
    a = bg + c[..., 0] * (tD - bg) * tai if vcr else bg + (tD - bg) * tai
    a = a * (1 + s_('Mesh AO Intensity', 1.0) * (O - 1)) + (C - 0.5) * 2 * s_('Curvature Color Influence')
    concav = np.clip(-2 * (C - 0.5), 0, 1)
    ci = s_('Mesh Concavities Intensity')
    u = np.clip(a * (1 - concav * ci), 0, 1)
    colour = np.clip(lut(u) * s_('Master Brightness', 1.0), 0, 1)
    r = s_('Background Roughness', 0.5) + (tR - s_('Background Roughness', 0.5)) * c[..., 0] if vcr else tR
    r = r + (s_('Mesh Concavities Roughness') - r) * concav * ci
    thr = max(s_('Convexities Treshold', 0.5), 1e-6)
    cv = np.clip((C - thr) / thr, 0, 1) * s_('Mesh Convexities Intensity')
    r = r + (s_('Mesh Convexities Roughness') - r) * cv
    r = r + (np.clip(C * s_('Base Roughness Multiplier', 1.0), 0, 1) - r) * s_('Blend Base Roughness')
    r = r + (s_('Tileable Emissive Roughness') - r) * te
    r = r + (s_('Mesh Glow Roughness') - r) * mask
    rough = np.clip(s_('Roughness Min') + (s_('Roughness Max') - s_('Roughness Min')) * r, 0, 1)
    # the normal from UV set 0's frame (the maps') into the layout's
    tris = np.asarray(idx).reshape(-1, 3)
    pos = np.asarray(attrs['POSITION'], np.float64)
    n = tx.interpolate(attrs['NORMAL'], idx, tri, bary)
    n /= np.maximum(np.linalg.norm(n, axis=-1, keepdims=True), 1e-8)
    t = np.maximum(tri, 0)
    T0, B0 = npcs._frames(pos, attrs['TEXCOORD_0'], tris); T2, B2 = npcs._frames(pos, attrs['LAYOUT'], tris)
    t0, b0 = npcs._ortho(T0[t].astype(np.float32), B0[t].astype(np.float32), n)
    t2, b2 = npcs._ortho(T2[t].astype(np.float32), B2[t].astype(np.float32), n)
    world = ts[..., :1] * t0 + ts[..., 1:2] * b0 + ts[..., 2:3] * n
    out = np.stack([(world * t2).sum(-1), (world * b2).sum(-1), (world * n).sum(-1)], -1)
    out /= np.maximum(np.linalg.norm(out, axis=-1, keepdims=True), 1e-8)
    out[~cov] = [0, 0, 1]
    return colour, np.zeros(tri.shape), rough, np.ones(tri.shape), out, glow, cov


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


def _magma_rock(export, mod, resolver, path, src, size):
    """One M_Asteroid_Master rock: its baked maps and a GLB over its layout. -> (model, materials) or None."""
    from . import npcs, planets, textures as tx
    name = path.rsplit('/', 1)[-1]
    prims = glb.static_mesh(src, keep=npcs.KEEP)
    keep, mats = [], []
    rows = planets._atlas_rows(resolver, ALBEDO_ATLAS)
    for mat, attrs, idx in prims:
        mi, mpath = npcs._find_mi(export, mat)
        p = resolver.get(mpath) if mpath else None
        if p is None or p.chain[-1] != 'M_Asteroid_Master': print(f'  rock {name}: {mat} not M_Asteroid_Master: left out'); continue
        layout = npcs._layout(attrs, idx)
        if layout is None: print(f'  rock {name}: no unique layout: left out'); continue
        resolver.fetch_textures(list(p.texture_paths.values()), export)
        cache = {}
        def png(param, srgb):
            t = p.textures.get(param)
            f = os.path.join(export, (p.texture_paths.get(t) or '') + '.png')
            if (param, srgb) not in cache: cache[(param, srgb)] = _load(f, srgb) if os.path.exists(f) else np.full((4, 4, 4), 0.5, np.float32)
            return cache[(param, srgb)]
        row = planets._curve_row(resolver, rows, p.scalar('Albedo LUT', 0.0))[:, :3]
        lut = lambda u: np.stack([np.interp(u, np.linspace(0, 1, len(row)), row[:, k]) for k in range(3)], -1)
        a = dict(attrs, LAYOUT=layout)
        colour, metal, rough, occl, normal, glow, cov = bake_magma(a, idx, p, png, lut, size)
        stem = f'{mat}_{name}'.lower()
        dil = lambda x: tx.dilate(x.astype(np.float32), cov)
        e = {'material': f'{mat}_{name}', **_write_maps(mod, stem, dil(colour), dil(metal), dil(rough), occl, dil(normal))}
        peak = float(np.percentile(glow.max(-1)[cov], 99.9)) if cov.any() else 0.0
        if peak > 0.05:   # (below: the cold rock's own faint blackbody, no glow worth a map)
            rel = f'maps/rocks/{stem}_e.png'
            tx._save(tx.linear_to_srgb(np.clip(dil(glow) / peak, 0, 1)), os.path.join(mod, rel), 0, 'RGB')
            e.update({'emission': rel, 'emissionColor': [1, 1, 1], 'emissionIntensity': round(min(peak, 3.0), 3)})
        mats.append(e)
        keep.append((e['material'], dict(attrs, TEXCOORD_0=layout, TANGENT=npcs._tangents(a, idx, 'LAYOUT')), idx))
    if not keep: return None
    rel = f'models/rocks/{name}.glb'
    os.makedirs(os.path.join(mod, 'models', 'rocks'), exist_ok=True)
    glb.save(os.path.join(mod, rel), keep, name)
    print(f'  rock {name}: magma, {len(keep)} parts')
    return rel, mats


def build(export, mod, resolver):
    """-> {'field', 'giant', 'moon': (models, materials)} for stations.json orbits."""
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
    # the magma rocks: the giant ones join the giant props, the destroyed moon's pieces their own group
    out.setdefault('moon', ([], []))
    for path in MAGMA:
        src = os.path.join(export, path + '.glb')
        if not os.path.exists(src): print(f'  rock {path}: not exported'); continue
        moon = 'Moon_Destroyed' in path
        r = _magma_rock(export, mod, resolver, path, src, 1024 if moon else 2048)
        if r is None: continue
        models, mats = out['moon' if moon else 'giant']
        models.append(r[0]); mats.extend(r[1])
    return out
