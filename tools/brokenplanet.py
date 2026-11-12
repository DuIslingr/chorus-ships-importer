"""Nimika Prime's broken planet (LocAST01_Geo: SM_Planet_Destroyed_LocAST_Part_001-006 sharing one frame, 13 700 km out,
and its loose fragments, SM_Planet_Destroyed_LocAST_Fragment_001-003) as orbit props of the remake (Modding/README
"orbit" "props"), their materials baked over their own UV set 0 from the masters' compiled base passes:

    M_Planet_Broken (MI_Planet_Broken_LocAST002-006, _Fragments_001): the planet's own colour, CA_Planets' "Color | From
      Elevation" row at the terrain height (T_Planet_LocGTH_H at uv x Tiling | Terrain Base; Macro | Color Influence 0)
      plus the grunge (2 (g - 0.5) x Grunge | Intensity), x Color | Dimming Factor (the view's fresnel term, which lifts it
      toward the atmosphere colour at the rim, left at 0), x Overall Basecolor Tint; where the mesh mask (its three
      channels summed) x the vertex colour's red says, the broken rock instead: A - Diffuse x A - Color Multiplier at uv x
      A - Tiling, B's by the A|B key saturate((|Mask - (mesh mask + min((k x A|B - Mask Multiplier)^A|B - Mask Exp, 1))|
      - A|B - Expansion) / A|B - Fuziness), then C's (B - Diffuse x C- Color Multiplier at uv x C - Tiling) by the C mask.
      The key's k (T_Planet_Destroyed_LocAST_Part_001_A, hard-wired, read over UV set 1) and the C mask's modulation (UV
      set 1) are read over UV set 0 here. No glow (Overall Emissive Tint 0: only the atmosphere rim, at 0). The normal: the
      mesh's, with the terrain's (x Terrain | Normal Intensity) or the rock's laid over by Unreal's angle-corrected blend.
    M_BrokenPlanet_Core (MI_BrokenPlanet_Core_Part001, on Part_001 by the level's override): the lava, two flowing reads of
      Core - Flow Emissive Diffuse at uv x Magma Tiling (flowing in the remake: the material's "lava" block, GoF2/Hull's
      LavaFlow, its maps packed by _lava; the bake below its fallback, at rest), mixed toward the
      spots (Core - 2nd Flow Emissive Diffuse at uv x 2nd Magma Tiling, x 2nd magma multiply, ^ 2nd magma Exp) by the
      first's (x 2nd core mask multiply)^2nd core mask Exp, x T_Planet_Destroyed_LocAST_Part_001_A's red (twice); its
      temperature Core - Temp Min to Max by that, its glow Unreal's BlackBody x (T / 2500)^4 (tools/rocks.blackbody) where
      the core mask (that texture's blue) is; the rock around it A / B (A - Color 0: black, B - Color grey) by the C mask.

Scale: the six parts at one place, turn and scale (each sized by its own extent, like the destroyed moon), placed in
Chorus's direction (below the play area: (Y, Z, -X) of Unreal's (-1.08e8, -3.00e8, -1.37e9) cm) far enough to look as
large as in Chorus (about 85 degrees across) inside the flight camera's 300 000 units.
"""
import math, os
import numpy as np
from PIL import Image
from . import glb

UP = 'SpacePrototype/Content/UnleashedPrototype/'
PLANETS = UP + 'ArtAssets/Environment/Planets/'
PARTS = [PLANETS + f'SM_Planet_Destroyed_LocAST_Part_{i:03d}' for i in range(1, 7)]
FRAGMENTS = [PLANETS + f'SM_Planet_Destroyed_LocAST_Fragment_{i:03d}' for i in range(1, 4)]
EXPORTS = PARTS + FRAGMENTS
CORE_MI = 'MI_BrokenPlanet_Core_Part001'   # (LocAST01_Geo's override on Part_001)
UE_AT = np.array([-108300000.0, -300455100.0, -1367899600.0])   # (cm, the six parts' shared origin in LocAST01_Geo)
DISTANCE, SIZE = 260000.0, 230000.0   # (game units: the planet's middle, its width)
FRAGMENT_COUNT, FRAGMENT_RING = 12, (110000.0, 190000.0)
BAKE = 1024


def _direction():
    d = np.array([UE_AT[1], UE_AT[2], -UE_AT[0]])   # (Unreal X forward, Y right, Z up -> game x right, y up, z forward)
    return d / np.linalg.norm(d)


def _bake_planet(p, png, row, red, size):
    """M_Planet_Broken over UV set 0 -> (colour linear, metal, rough, occlusion, normal)."""
    from . import rocks
    v, u = np.meshgrid((np.arange(size) + 0.5) / size, (np.arange(size) + 0.5) / size, indexing='ij')
    s = p.scalar
    tb = s('Tiling | Terrain Base', 4.0)
    h = rocks._sample(png('Terrain Heightmap', False), u * tb, v * tb)[..., 0]
    lut = np.stack([np.interp(np.clip(h, 0, 1), np.linspace(0, 1, len(row)), row[:, k]) for k in range(3)], -1)
    grunge = rocks._sample(png('Grunge | Texture', True), u * tb * s('Grunge | Tiling Factor', 1.0), v * tb * s('Grunge | Tiling Factor', 1.0))[..., :3]
    planet = (lut + (grunge - 0.5) * s('Grunge | Intensity', 0.1) * 2.0) * s('Color | Dimming Factor', 0.3)
    planet = planet * s('Overall Brightness Lit Side', 1.0) * np.asarray((p.vector('Overall Basecolor Tint') or [1, 1, 1])[:3])
    # the broken rock: A, B by the key, C by its mask
    ta, tbb, tc = s('A - Tiling', 1.0), s('B - Tiling', 1.0), s('C - Tiling', 1.0)
    ua, va = u * ta + s('A - Shift  U'), v * ta + s('A - Shift V')
    ub, vb = u * tbb + s('B - Shift  U'), v * tbb + s('B - Shift V')
    uc, vc = u * tc + s('C - Shift  U'), v * tc + s('C - Shift V')
    mask = rocks._sample(png('Mesh Mask', False), u, v, False)[..., :3]
    k = rocks._sample(png('Key', False), u, v)[..., 0]   # (the hard-wired key texture's channel the pass reads: R)
    kk = np.minimum(np.where(k > 0, np.power(np.maximum(k * s('A|B - Mask Multiplier', 1.0), 1e-9), s('A|B - Mask Exp', 1.0)), 0.0), 1.0)
    dist = np.linalg.norm(np.asarray((p.vector('Mask') or [1, 0, 0])[:3]) - (mask + kk[..., None]), axis=-1)
    mab = np.clip((dist - s('A|B - Expansion', 1.0)) / max(s('A|B - Fuziness', 0.8), 1e-3), 0, 1)[..., None]
    ca = rocks._sample(png('A - Diffuse', True), ua, va)[..., :3] * np.asarray((p.vector('A - Color Multiplier') or [1, 1, 1])[:3])
    cb = rocks._sample(png('B - Diffuse', True), ub, vb)[..., :3] * np.asarray((p.vector('B - Color Multiplier') or [1, 1, 1])[:3])
    cc = rocks._sample(png('B - Diffuse', True), uc, vc)[..., :3] * np.asarray((p.vector('C- Color Multiplier') or [0, 0, 0])[:3])
    cm_t = s('C - Mask Tiling', 1.0)
    cmod = rocks._sample(png('C - Mask Modulation', False), u * cm_t + s('C - Mask Shift  U'), v * cm_t + s('C - Mask Shift V'))[..., 0]
    cmod = (cmod - 1.0) * s('C - Mask Mod mix', 1.0) + 1.0
    ck = k * s('C - Mask Multiplier', 1.0)
    ck = np.where(ck > 0, np.power(np.maximum(ck, 1e-9), s('C - Mask Exp', 1.0)), 0.0)
    mc = np.clip(cmod * ck, 0, 1)[..., None]
    rock = ca + (cb - ca) * mab
    rock = rock + (cc - rock) * mc
    w = np.clip(mask.sum(-1) * red, 0, 1)[..., None]
    colour = np.clip(planet + (rock - planet) * w, 0, 1)
    rough = np.clip(np.full(u.shape, s('Roughness | Constant', 0.9)), 0, 1)
    metal = np.zeros(u.shape)
    occl = np.ones(u.shape)
    base = rocks._unpack(rocks._sample(png('A | Mesh Normal', False), u, v, False))
    terrain = rocks._unpack(rocks._sample(png('Terrain Normalmap', False), u * tb, v * tb))
    terrain[..., :2] *= s('Terrain | Normal Intensity', 1.0)
    na = rocks._unpack(rocks._sample(png('A - Normal', False), ua, va))
    nb = rocks._unpack(rocks._sample(png('B - Normal', False), ub, vb))
    detail = terrain + ((na + (nb - na) * mab) - terrain) * w
    detail /= np.maximum(np.linalg.norm(detail, axis=-1, keepdims=True), 1e-6)
    return colour, metal, rough, occl, rocks._blend_angle_corrected(base, detail)


def _bake_core(p, png, size):
    """M_BrokenPlanet_Core over UV set 0, at rest -> (colour linear, metal, rough, occlusion, normal, glow linear)."""
    from . import rocks
    v, u = np.meshgrid((np.arange(size) + 0.5) / size, (np.arange(size) + 0.5) / size, indexing='ij')
    s = p.scalar
    mt, mt2 = s('Magma Tiling', 6.0), s('2nd Magma Tiling', 30.0)
    m1 = rocks._sample(png('Core - Flow Emissive Diffuse', False), u * mt, v * mt)[..., :3]
    m2 = rocks._sample(png('Core - 2nd Flow Emissive Diffuse', False), u * mt2, v * mt2)[..., :3] * s('2nd magma multiply', 1.0)
    m2 = np.where(m2 > 0, np.power(np.maximum(m2, 1e-9), s('2nd magma Exp', 1.0)), 0.0)
    k = m1 * s('2nd core mask multiply', 1.0)
    k = np.where(k > 0, np.power(np.maximum(k, 1e-9), s('2nd core mask Exp', 1.0)), 0.0)
    lava = m1 + (m2 - m1) * k
    meshmask = rocks._sample(png('A/B - CORE Mesh Mask', False), u, v, False)
    r = meshmask[..., 0]
    T = s('Core - Temp  Min', 400.0) + (s('Core - Temp  Max', 3000.0) - s('Core - Temp  Min', 400.0)) * lava[..., 0] * r * r
    core = meshmask[..., 2][..., None]
    glow = rocks.blackbody(T) * ((T * 0.0004) ** 4)[..., None] * core
    # the rock: A (its colour black) and B by the C mask, toward the core's colours (black) where the core is
    ta, tb = s('A - Tiling', 30.0), s('B -Tiling', 25.0)
    ca = rocks._sample(png('A - Diffuse', True), u * ta, v * ta)[..., :3] * np.asarray((p.vector('A - Color') or [0, 0, 0])[:3])
    cb = rocks._sample(png('B - Diffuse', True), u * tb, v * tb)[..., :3] * np.asarray((p.vector('B - Color') or [0.27, 0.25, 0.25])[:3])
    cm = rocks._sample(png('C - Mask Modulation', False), u, v)[..., 0][..., None]
    rock = ca + (cb - ca) * np.clip(cm, 0, 1)
    colour = np.clip(rock * (1.0 - core), 0, 1)
    base = rocks._unpack(rocks._sample(png('A - Mesh Normal Map', False), u, v, False))
    detail = rocks._unpack(rocks._sample(png('B - Normal', False), u * tb, v * tb))
    return colour, np.zeros(u.shape), np.full(u.shape, 0.9), np.ones(u.shape), rocks._blend_angle_corrected(base, detail), glow


def _lava(mod, p, png, stem, glow_scale):
    """M_BrokenPlanet_Core's flow as the remake's "lava" block (GoF2/Hull LavaFlow): its maps packed into three (emit: the
    flow emissives' red; flow: the two flowmaps' red and green; masks: the time offsets, the part mask's red and the core
    mask's blue), its numbers, the flowmaps' mip levels moved with their size. -> the block, or None."""
    from . import textures as tx
    s = p.scalar
    def chans(param, idx, n):
        a = png(param, False)
        if a.shape[0] <= 4: return None   # (missing: png's placeholder)
        im = Image.fromarray((np.clip(a[..., idx], 0, 1) * 255).astype(np.uint8))
        return np.asarray(im.resize((n, n), Image.LANCZOS), np.float32) / 255.0
    def size(param):
        a = png(param, False); return a.shape[0]
    n_e, n_f, n_m = 1024, 512, 1024
    e1, e2 = chans('Core - Flow Emissive Diffuse', 0, n_e), chans('Core - 2nd Flow Emissive Diffuse', 0, n_e)
    f1, f2 = chans('Core - Flowmap', slice(0, 2), n_f), chans('Core - 2nd Flowmap', slice(0, 2), n_f)
    t1, t2 = chans('FlowMapTimeOffset', 0, n_m), chans('FlowMap 2 TimeOffset', 0, n_m)
    part, core = chans('Key', 0, n_m), chans('A/B - CORE Mesh Mask', 2, n_m)
    if any(x is None for x in (e1, e2, f1, f2, part, core)): return None
    z = np.zeros((n_m, n_m), np.float32)
    t1 = t1 if t1 is not None else z; t2 = t2 if t2 is not None else z
    rel = {}
    for name, arr, mode in (('emit', np.stack([e1, e2, np.zeros_like(e1)], -1), 'RGB'), ('flow', np.concatenate([f1, f2], -1), 'RGBA'),
                            ('masks', np.stack([t1, t2, part, core], -1), 'RGBA')):
        rel[name] = f'maps/rocks/{stem}_lava_{name}.png'
        tx._save(arr, os.path.join(mod, rel[name]), 0, mode)
    off = p.vector('Flowmap UV Texture Offset') or [0.0, 0.0]
    mip = lambda param, level: round(level + math.log2(n_f / max(size(param), 1)), 3)
    return {'emit': rel['emit'], 'flow': rel['flow'], 'masks': rel['masks'],
            'a': [s('Magma Tiling', 6.0), s('Core - FlowSpeed', 0.05), s('Core - Flowmap Tiling', 1.0), s('Core - FlowIntensity', 0.1)],
            'b': [s('Magma Flow TimeOffset Tiling', 1.0), s('Magma Flow TimeOffset intensity', 1.0), float(off[0]), float(off[1])],
            'c': [s('2nd Magma Tiling', 30.0), s('Core - FlowSpeed 2', 0.05), s('Core - Flowmap Tiling 2', 1.0), s('Core - FlowIntensity 2', 0.1)],
            'd': [s('Magma Flow 2 TimeOffset Tiling', 1.0), s('2nd core mask multiply', 1.0), s('2nd core mask Exp', 1.0), s('2nd magma multiply', 1.0)],
            'magma2Exp': s('2nd magma Exp', 1.0), 'tempMin': s('Core - Temp  Min', 400.0), 'tempMax': s('Core - Temp  Max', 3000.0),
            'mip': mip('Core - Flowmap', s('Core - FlowMipLevel', 0.0)), 'mip2': mip('Core - 2nd Flowmap', s('Core - FlowMipLevel 2', 0.0)),
            'glow': round(glow_scale, 5)}


def _material(export, mod, resolver, mat, src, size):
    """One part's baked material entry, or None."""
    from . import npcs, planets, rocks, textures as tx
    _, mpath = npcs._find_mi(export, mat)
    p = resolver.get(mpath) if mpath else None
    if p is None: print(f'  broken planet: {mat} not found'); return None
    resolver.fetch_textures(list(p.texture_paths.values()), export)
    cache = {}
    hard = {'Key': 'T_Planet_Destroyed_LocAST_Part_001_A'}   # (the masters' hard-wired textures, their referenced 16 / 2)
    def png(param, srgb):
        t = p.textures.get(param) or hard.get(param)
        path = p.texture_paths.get(t) or (PLANETS + t if t else '')
        if t and path and not os.path.exists(os.path.join(export, path + '.png')): resolver.fetch_textures([path], export)
        f = os.path.join(export, path + '.png')
        if (param, srgb) not in cache: cache[(param, srgb)] = rocks._load(f, srgb) if os.path.exists(f) else np.full((4, 4, 4), 0.5, np.float32)
        return cache[(param, srgb)]
    stem = f'brokenplanet_{mat}'.lower()
    cov = np.ones((size, size), bool)
    if p.chain[-1] == 'M_BrokenPlanet_Core':
        colour, metal, rough, occl, normal, glow = _bake_core(p, png, size)
    else:
        rows = planets._atlas_rows(resolver)
        row = planets._curve_row(resolver, rows, p.scalar('Color | From Elevation', 0.0))[:, :3]
        red = float(np.asarray(glb.static_mesh(src, keep=('POSITION', 'COLOR_0'))[0][1].get('COLOR_0', [[1.0]]))[..., 0].mean())
        colour, metal, rough, occl, normal = _bake_planet(p, png, row, red, size)
        glow = None
    e = {'material': mat, **rocks._write_maps(mod, stem, colour, metal, rough, occl, normal)}
    if glow is not None:
        hot = glow.max(-1)
        hot = hot[hot > 1e-4]   # (the core is a small part of the layout: its own texels)
        peak = float(np.percentile(hot, 99.5)) if hot.size else 0.0
        if peak > 0.05:
            # (flowing: the "lava" block, its glow held as the bake's, x min(peak, 3) / peak; else the bake at rest)
            lava = _lava(mod, p, png, stem, min(peak, 3.0) / peak) if p.chain[-1] == 'M_BrokenPlanet_Core' else None
            if lava: e['lava'] = {k: ([round(float(x), 5) for x in v] if isinstance(v, list) else v) for k, v in lava.items()}
            else:
                rel = f'maps/rocks/{stem}_e.png'
                tx._save(tx.linear_to_srgb(np.clip(glow / peak, 0, 1)), os.path.join(mod, rel), 0, 'RGB')
                e.update({'emission': rel, 'emissionColor': [1, 1, 1], 'emissionIntensity': round(min(peak, 3.0), 3)})
    return e


def build(export, mod, resolver, rnd):
    """-> (orbit props, their materials) for Nimika Prime's orbit, or ([], []). The six parts are one model (their shared
    frame kept as made), the fragments a model each."""
    from . import npcs
    mats, whole, extents, rels = [], [], {}, {}
    os.makedirs(os.path.join(mod, 'models', 'rocks'), exist_ok=True)
    for path in PARTS + FRAGMENTS:
        src = os.path.join(export, path + '.glb')
        if not os.path.exists(src): print(f'  broken planet: {path.rsplit("/", 1)[1]} not exported'); return [], []
        prims = glb.static_mesh(src, keep=npcs.KEEP[:-1])
        mat = CORE_MI if path == PARTS[0] else prims[0][0]
        if mat not in {m['material'] for m in mats}:
            e = _material(export, mod, resolver, mat, src, BAKE)
            if e is None: return [], []
            mats.append(e)
        prims = [(mat, a, i) for _, a, i in prims]
        if path in PARTS: whole += prims; continue
        name = path.rsplit('/', 1)[1].lower()
        rels[path] = f'models/rocks/{name}.glb'
        glb.save(os.path.join(mod, rels[path]), prims, name)
        lo, hi = glb.bounds(prims); extents[path] = float(np.max(np.asarray(hi) - np.asarray(lo)))
    glb.save(os.path.join(mod, 'models', 'rocks', 'broken_planet.glb'), whole, 'broken_planet')
    lo, hi = glb.bounds(whole)
    k = SIZE / float(np.max(np.asarray(hi) - np.asarray(lo)))   # (game units a model metre)
    at = _direction() * DISTANCE
    props = [{'model': 'models/rocks/broken_planet.glb', 'at': [round(float(v)) for v in at],
              'rotation': [0, round(rnd.uniform(0, 360)), 0], 'size': round(SIZE)}]
    # its loose fragments round it, between it and the station, at the same scale
    d0 = _direction()
    side = np.cross(d0, [0, 1, 0] if abs(d0[1]) < 0.9 else [1, 0, 0]); side /= np.linalg.norm(side)
    up = np.cross(side, d0)
    for i in range(FRAGMENT_COUNT):
        path = FRAGMENTS[i % len(FRAGMENTS)]
        a = rnd.uniform(0, 6.283); d = rnd.uniform(*FRAGMENT_RING)
        pos = d0 * d * 0.8 + (side * math.cos(a) + up * math.sin(a)) * d * 0.45
        props.append({'model': rels[path], 'at': [round(float(v)) for v in pos], 'rotation': [round(rnd.uniform(0, 360)) for _ in range(3)],
                      'size': round(extents[path] * k * rnd.uniform(0.7, 1.4))})
    print(f'  broken planet: {len(PARTS)} parts in one model, {FRAGMENT_COUNT} fragments, {len(mats)} materials')
    return props, mats


def _euler(e):
    """Unity's Euler angles (degrees, z x y order) as a rotation matrix (Unity frame)."""
    x, y, z = (math.radians(v) for v in e)
    rx = np.array([[1, 0, 0], [0, math.cos(x), -math.sin(x)], [0, math.sin(x), math.cos(x)]])
    ry = np.array([[math.cos(y), 0, math.sin(y)], [0, 1, 0], [-math.sin(y), 0, math.cos(y)]])
    rz = np.array([[math.cos(z), -math.sin(z), 0], [math.sin(z), math.cos(z), 0], [0, 0, 1]])
    return ry @ rx @ rz
