"""Chorus's death explosions as the remake's ships.json "deathFx" (World.ModDeathFx: a JSON file of particle emitters).

Chorus's death effect configs (Effects/ExplosionSystem/ExplosionConfigs/BP_*_Expl_*: BP_Fighter_Expl_Chase_01's steps) set off
its modular explosions, each a Cascade particle system: the fighters' "Explosion Main" (P_Explosion_Main) at the end of a
5 s tumble with 3 - 12 "Explosion Sub" (P_Explosion_Sub) and 3 - 6 "Sparks" (P_Explosion_Small_Sparks) over it; the
warships' and big ships' P_Explosion_Large_M. Each emitter's level 0 read here (the exporter's JSON: every distribution
comes with its baked lookup table): its material's image, flipbook and frames over life, bursts and rate, life, size and
size over life, colour and alpha over life, speed (along the emitter's X, outward, or from its spawn sphere), drag, the
parent's velocity, rotation. The lights-only emitters (ParticleModuleLight) as the remake's "light" emitters (their range
the particle's size x RadiusScale; Chorus's brightness, 1e9 - 4e9 in its physical units, as 3 x its square root over
1e9); the impostor debris (MI_ImposterDebris: T_Debris_D, a 2 x 2 sheet of rocks with alpha, through its parent
MI_ImposterSplinters' parameter) alpha-blended ("blend": "alpha"), a dim grey (Chorus lights them, with burning edges);
each fireball's smoke (its flipbook's coverage, A, drawn dark under the fire: Chorus's translucent fireball shows its
base colour where the fire, G, is weak) as an alpha-blended companion; the trails along the debris (SpawnPerUnit at a
LocationEmitter's particles: "trail") and the vector fields as turbulence ("noise"). The trails' M_LoopFireSmoke (its
compiled translucent pass, MI_P_Explosion_01_GPU_02) takes the particle colour as parameters: R the erosion threshold,
G its softness, B the glow's strength, A the opacity; its colour only the blackbody (Mix BlackBody/Diffuse Emissive 1)
at smoothstep(saturate((flipbook A x the fractal detail - R) / G)) x Color Temperature, x (K / 2500)^4, 20 %
desaturated; its opacity flipbook A x the detail: baked (_firesmoke) at the particle's start (R, G) as an alpha-blended
image (RGB the glow, A the coverage), B over life its brightness; its flipbook (wall-clock time in Chorus) a random
frame a puff. Left out: the mesh emitters, the threshold's rise over life (the glow fades instead).

Units: Chorus centimetres -> game units at the ships' scale (SCALE 3.6: 0.72 a centimetre). Brightness: Chorus's HDR
colours (its fireball 10 000 at its start: colour x colour scale x the material's Tint) squeezed into the remake's bloom
range, x 8 / (8 + x) (a fireball about 8, the sparks 5 - 7). The fireball's flipbook (T_*_DE: G its fire, B the white-hot
core, A its coverage) baked to one added image, (G^Power + B / 2) x A; the sparks' material has no image: a soft streak.
"""
import json, os
import numpy as np
from PIL import Image

UP = 'SpacePrototype/Content/UnleashedPrototype/'
PS = UP + 'Effects/ExplosionSystem/ParticleSystems/'
CM = 0.72                 # game units a Chorus centimetre (the ships' SCALE 3.6 / 0.05 / 100)
SAMPLES = 12              # curve samples written
EFFECTS = {
    'fighter': {'main': ['P_Explosion_Main'], 'dying': ['P_Explosion_Sub', 'P_Explosion_Small_Sparks'], 'dyingCount': [3, 12]},
    'large': {'main': ['P_Explosion_Large_M'], 'dying': ['P_Explosion_Sub'], 'dyingCount': [4, 10], 'dyingScale': 4.0},
}
LARGE_M = 400.0           # metres: a hull longer gets the big ships' explosion
SMOKE = [0.07, 0.065, 0.06]   # the fireball's smoke, unlit in space (Chorus's lit base colour, dimmed)
DEBRIS = [0.42, 0.4, 0.38]    # the impostor rocks' grey
EXPORTS = []   # (the systems are read as JSON, their images exported on demand)


def _squeeze(p): return 8.0 * p / (8.0 + p)


def _load(work, resolver, name):
    folder = os.path.join(work, 'bp_expl'); os.makedirs(folder, exist_ok=True)
    f = os.path.join(folder, name + '.json')
    if not os.path.exists(f) and resolver is not None:
        resolver.run('jsonall', f'/ExplosionSystem/ParticleSystems/{name}\\.uasset$', folder, capture=True)
    return json.load(open(f, encoding='utf-8')) if os.path.exists(f) else None


class _Dist:
    """A Cascade distribution (its baked table, or a referenced object): value(s) at a time, its range."""
    def __init__(self, d, objs):
        self.vals, self.stride, self.scale, self.bias, self.op, self.n = None, 1, 0.0, 0.0, 1, 1
        self.const = None
        if not isinstance(d, dict): self.const = d; return
        t = d.get('Table')
        if t and t.get('Values') is not None:
            self.vals = np.asarray(t['Values'], np.float64); self.stride = max(1, t.get('EntryStride', 1))
            self.scale, self.bias, self.op, self.n = t.get('TimeScale', 0.0), t.get('TimeBias', 0.0), t.get('Op', 1), t.get('EntryCount', 1)
            return
        o = objs(d.get('Distribution'))
        if o:
            p = o.get('Properties') or {}
            if isinstance(p.get('Constant'), dict):   # (a vector constant: DistributionVectorConstant)
                c = p['Constant']; self.vals = np.array([c.get('X', 0.0), c.get('Y', 0.0), c.get('Z', 0.0)], np.float64); self.stride = 3
            elif 'Constant' in p: self.const = p['Constant']
            elif 'Max' in p or 'Min' in p: self.vals = np.array([p.get('Min', 0.0), p.get('Max', 0.0)]); self.op, self.stride = 2, 2
            elif (p.get('ConstantCurve') or {}).get('Points'):   # (a curve object without its table: its points, linear)
                pts = p['ConstantCurve']['Points']
                key = lambda o: [o['X'], o['Y'], o['Z']] if isinstance(o, dict) else [o]
                xs = np.array([float(q.get('InVal', 0.0)) for q in pts])
                ys = np.array([key(q.get('OutVal', 0.0)) for q in pts], np.float64)
                grid = np.linspace(0.0, 1.0, SAMPLES)
                table = np.stack([np.interp(grid, xs, ys[:, c]) for c in range(ys.shape[1])], -1)
                self.vals, self.stride, self.n = table.reshape(-1), ys.shape[1], SAMPLES
                self.scale, self.bias, self.op = float(SAMPLES - 1), 0.0, 1

    def range(self, comp=0):
        """(min, max) of component 'comp' at time 0 (a uniform's two ends, else the constant)."""
        if self.const is not None: return (float(self.const), float(self.const))
        if self.vals is None: return None
        if self.op == 2:   # uniform: [min..., max...] per entry
            half = self.stride // 2
            return (float(self.vals[comp]), float(self.vals[half + comp]))
        v = float(self.vals[comp]); return (v, v)

    def curve(self, comp=0, samples=SAMPLES):
        """The component over life 0..1 (sampled), or None for a constant."""
        if self.vals is None or self.n <= 1: return None
        out = []
        for x in np.linspace(0.0, 1.0, samples):
            f = (x - self.bias) * self.scale if self.scale else 0.0
            i = int(np.clip(np.floor(f), 0, self.n - 1)); j = min(i + 1, self.n - 1); w = float(np.clip(f - i, 0, 1))
            a = self.vals[i * self.stride + comp]; b = self.vals[j * self.stride + comp]
            out.append(float(a + (b - a) * w))
        return out

    def peak(self, comp=0):
        if self.const is not None: return float(self.const)
        if self.vals is None: return 1.0
        return float(np.max(self.vals[comp::self.stride]))


def _spark(mod):
    """fx/chorus_spark.png: a soft white streak (the sparks' material has no image)."""
    rel = 'fx/chorus_spark.png'
    path = os.path.join(mod, rel)
    if not os.path.exists(path):
        y, x = np.mgrid[-1:1:64j, -1:1:64j]
        v = np.clip(1.0 - np.sqrt(x * x * 4.0 + y * y), 0, 1) ** 1.5
        a = (v * 255).astype(np.uint8)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        Image.fromarray(np.stack([a, a, a, a], -1), 'RGBA').save(path, optimize=True)
    return rel


def _fireball(export, mod, resolver, mi_path):
    """The flipbook of an M_Explosion_* instance baked for adding: -> (its path in the mod, the Tint, Power)."""
    resolver.prefetch([mi_path])
    p = resolver.get(mi_path)
    tex = next(iter(p.textures.values()), None) if p else None
    path = p.texture_paths.get(tex) if tex else None
    if not path: return None, None, 1.0
    resolver.fetch_textures([path], export)
    src = os.path.join(export, path + '.png')
    if not os.path.exists(src): return None, None, 1.0
    power = float(p.scalars.get('Power', 1.0))
    rel = f'fx/{os.path.basename(path).lower()}.png'
    out = os.path.join(mod, rel)
    if not os.path.exists(out):
        im = Image.open(src).convert('RGBA')
        im = im.resize((im.width // 2, im.height // 2), Image.LANCZOS)
        a = np.asarray(im, np.float32) / 255.0
        v = np.clip(a[..., 1] ** power + 0.5 * a[..., 2], 0, 1) * a[..., 3]
        g = (v * 255).astype(np.uint8)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        Image.fromarray(np.stack([g, g, g, g], -1), 'RGBA').save(out, optimize=True)
    return rel, p.vector('Tint') or [1.0, 1.0, 1.0], power


def _texture(export, mod, resolver, mi_path, want=None):
    """The first texture (or the one named 'want') of an instance's chain, exported: -> its PNG path, or None."""
    resolver.prefetch([mi_path])
    p = resolver.get(mi_path)
    if not p: return None
    path = p.texture_paths.get(want) if want else next((v for k, v in p.texture_paths.items() if k in p.textures.values()), None)
    if not path: return None
    resolver.fetch_textures([path], export)
    src = os.path.join(export, path + '.png')
    return src if os.path.exists(src) else None


def _smoke(export, mod, resolver, mi_path):
    """The fireball flipbook's smoke: white where it covers (A), for an alpha-blended, dark-tinted companion."""
    p = resolver.get(mi_path)
    tex = next(iter(p.textures.values()), None) if p else None
    path = p.texture_paths.get(tex) if tex else None
    src = os.path.join(export, path + '.png') if path else None
    if not src or not os.path.exists(src): return None
    rel = f'fx/{os.path.basename(path).lower()}_smoke.png'
    out = os.path.join(mod, rel)
    if not os.path.exists(out):
        im = Image.open(src).convert('RGBA')
        im = im.resize((im.width // 2, im.height // 2), Image.LANCZOS)
        a = (np.asarray(im, np.uint8)[..., 3]).copy()
        w = np.full_like(a, 255)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        Image.fromarray(np.stack([w, w, w, a], -1), 'RGBA').save(out, optimize=True)
    return rel


def _blackbody(k):
    """Chorus's blackbody (MF_WreckBurn's and M_LoopFireSmoke's Planckian-locus fit) x (k / 2500)^4, linear RGB, k array."""
    k = np.asarray(k, np.float64); k2 = k * k
    u = (0.860117757 + 1.54118254e-4 * k + 1.28641212e-7 * k2) / (1.0 + 8.42420235e-4 * k + 7.08145163e-7 * k2)
    v = (0.317398726 + 4.22806245e-5 * k + 4.20481691e-8 * k2) / (1.0 - 2.89741816e-5 * k + 1.61456053e-7 * k2)
    d = 2.0 * u - 8.0 * v + 4.0
    x, y = 3.0 * u / d, 2.0 * v / d
    X, Z = x / y, (1.0 - x - y) / y
    rgb = np.stack([3.2404542 * X - 1.5371385 - 0.4985314 * Z, -0.969266 * X + 1.8760108 + 0.041556 * Z,
                    0.0556434 * X - 0.2040259 + 1.0572252 * Z], -1)
    return np.maximum(rgb, 0.0) * ((k * 4e-4) ** 4)[..., None]


def _firesmoke(export, mod, resolver, mi_path, threshold, softness):
    """An M_LoopFireSmoke instance's flipbook baked at threshold R / softness G (see the header): -> (its path, its peak
    linear glow at full B = 1, the sheet's columns, rows), or None."""
    p = resolver.get(mi_path)
    if not p: return None
    book = p.textures.get('None') or next(iter(p.textures.values()), None)
    detail = p.textures.get('Texture (T2d)')
    paths = [p.texture_paths[t] for t in (book, detail) if t and t in p.texture_paths]
    resolver.fetch_textures(paths, export)
    src = os.path.join(export, p.texture_paths.get(book, '') + '.png') if book in p.texture_paths else None
    if not src or not os.path.exists(src): return None
    cols, rows = int(p.scalars.get('FlipbookColumns', 8)), int(p.scalars.get('FlipbookRows', 8))
    rel = f'fx/{os.path.basename(src)[:-4].lower()}_firesmoke.png'
    out = os.path.join(mod, rel)
    temp = float(p.scalars.get('Color Temperature', 3500.0))
    im = Image.open(src).convert('RGBA'); im = im.resize((im.width // 2, im.height // 2), Image.LANCZOS)
    a = np.asarray(im, np.float32)[..., 3] / 255.0
    h, w = a.shape
    n = np.full_like(a, 0.66)
    dsrc = os.path.join(export, p.texture_paths.get(detail, '') + '.png') if detail in p.texture_paths else None
    if dsrc and os.path.exists(dsrc):   # (the detail: 4 samples summed x Divisor ~ one sample x 4 x Divisor, over each cell x Tiling)
        dn = np.asarray(Image.open(dsrc).convert('L'), np.float32) / 255.0
        tile = float(p.scalars.get('Detail Texture Tiling', 8.0))
        yy, xx = np.mgrid[0:h, 0:w]
        cu = (xx % (w // cols)) / (w / cols) * tile; cv = (yy % (h // rows)) / (h / rows) * tile
        n = dn[(cv * dn.shape[0]).astype(int) % dn.shape[0], (cu * dn.shape[1]).astype(int) % dn.shape[1]] * 4.0 * float(p.scalars.get('Detail Texture Divisor', 0.33))
    st = float(p.scalars.get('Detail Texture Strength', 0.2))
    cover = np.clip(a * (st + n * (1.0 - st)), 0, 1)
    e = np.clip((cover - threshold) / max(softness, 1e-3), 0, 1); e = e * e * (3 - 2 * e)
    glow = _blackbody(e * temp)
    lum = (glow * np.array([0.3, 0.59, 0.11])).sum(-1, keepdims=True)
    glow = glow + float(p.scalars.get('Desaturation Amount', 0.2)) * (lum - glow)
    peak = float(glow.max()) or 1.0
    if not os.path.exists(out):
        os.makedirs(os.path.dirname(out), exist_ok=True)
        rgb = (np.clip(glow / peak, 0, 1) ** (1 / 2.2) * 255).astype(np.uint8)   # (sRGB, as the other fx images)
        Image.fromarray(np.dstack([rgb, (cover * 255).astype(np.uint8)]), 'RGBA').save(out, optimize=True)
    return rel, peak, cols, rows


def _debris(export, mod, resolver, mi_path):
    """MI_ImposterDebris' rock sheet (its AO_Alpha texture, T_Debris_D), halved: -> its path in the mod."""
    src = _texture(export, mod, resolver, mi_path, 'T_Debris_D')
    if not src: return None
    rel = 'fx/t_debris_d.png'
    out = os.path.join(mod, rel)
    if not os.path.exists(out):
        im = Image.open(src).convert('RGBA')
        os.makedirs(os.path.dirname(out), exist_ok=True)
        im.resize((im.width // 2, im.height // 2), Image.LANCZOS).save(out, optimize=True)
    return rel


def _ue_axes(v):
    """A vector in an Unreal component's frame (x forward, y right, z up) -> the remake's effect frame (Unity's axes: x
    right, y up, z forward) as the Forsaken's sockets come out of glTF ((x, z, y)) and glTFast (x negated)."""
    return [-v[0], v[2], v[1]]


def _emitters(export, mod, resolver, d, scale=1.0, pick=None, loop_for=None, cascade=False):
    """CustomFxEmitter entries of one Cascade system (its JSON 'd'). 'pick'(material name, path) -> (image, blend, tint) or
    None (left out) chooses an emitter's image instead of the explosions' rules (tools/rites.py); 'loop_for' seconds: an
    emitter looping for ever (EmitterLoops 0) is repeated that long (its bursts every EmitterDuration, its rate throughout).
    'cascade' (tools/drift.py, an effect that runs until it is stopped): emitters switched off in the editor are left out,
    one looping for ever (EmitterLoops 0, Unreal's default: absent from the JSON) gets "loop", bUseLocalSpace "local", its
    Location module's start "at" (game units, the remake's effect frame: _ue_axes)."""
    def objs(ref):
        if not isinstance(ref, dict) or 'ObjectPath' not in ref: return None
        i = int(ref['ObjectPath'].rsplit('.', 1)[1]); return d[i] if i < len(d) else None
    ps = next((e for e in d if e.get('Type') == 'ParticleSystem'), None)
    out = []
    # the trails: an emitter spawning per unit at another's particles (LocationEmitter): its target, which flies unseen
    sources = {}
    for r in (ps or {}).get('Properties', {}).get('Emitters', []):
        em = objs(r)
        lods = [objs(l) for l in ((em or {}).get('Properties') or {}).get('LODLevels', [])]
        for mr in ((lods[0] or {}).get('Properties', {}).get('Modules', []) if lods else []):
            m = objs(mr)
            if m and m['Type'] == 'ParticleModuleLocationEmitter': sources[(em.get('Properties') or {}).get('EmitterName')] = (m.get('Properties') or {}).get('EmitterName')
    trails = {}
    for r in (ps or {}).get('Properties', {}).get('Emitters', []):
        em = objs(r)
        if not em: continue
        ep = em.get('Properties') or {}
        name = ep.get('EmitterName')
        hidden = ep.get('EmitterRenderMode') == 'ERM_None'
        if hidden and name not in sources.values(): continue
        lights_only = ep.get('EmitterRenderMode') == 'ERM_LightsOnly'
        lods = [objs(l) for l in ep.get('LODLevels', [])]
        lod = next((l for l in lods if l and l['Name'].endswith('_0')), lods[0] if lods else None)
        if not lod: continue
        lp = lod['Properties']
        req = (objs(lp.get('RequiredModule')) or {}).get('Properties', {})
        if cascade and (lp.get('bEnabled', True) is False or req.get('bEnabled', True) is False): continue   # (off in the editor)
        spawn = (objs(lp.get('SpawnModule')) or {}).get('Properties', {})
        mods = {}
        for mr in lp.get('Modules', []):
            m = objs(mr)
            if m and (m.get('Properties') or {}).get('bEnabled', True) is not False: mods.setdefault(m['Type'].replace('ParticleModule', ''), m.get('Properties') or {})
        trail_of = sources.get(name) if 'SpawnPerUnit' in mods else None
        fire_smoke = None
        if 'SpawnPerUnit' in mods and not trail_of: continue   # (a trail along a moving emitter: not one of this system's)
        mat = (req.get('Material') or {}).get('ObjectName', '')
        mat_name = mat.split("'")[1] if "'" in mat else mat
        mat_path = (req.get('Material') or {}).get('ObjectPath', '').rsplit('.', 1)[0]
        tint, image, blend = [1.0, 1.0, 1.0], None, None
        custom = pick(mat_name, mat_path) if pick and not lights_only else NotImplemented
        if lights_only:
            if 'Light' not in mods: continue   # (a lights-only emitter without its light draws nothing)
        elif custom is not NotImplemented:
            if custom is None: continue
            image, blend, t = custom
            if t: tint = list(t)[:3]
        elif resolver.get(mat_path) and (resolver.get(mat_path).chain or [None])[-1] == 'M_LoopFireSmoke':
            # (the particle colour as parameters: its start's R / G the bake's threshold, B the glow over life)
            dc = _Dist((mods.get('ColorOverLife') or {}).get('ColorOverLife'), objs)
            r0 = dc.range(0); g0 = dc.range(1)
            fire_smoke = _firesmoke(export, mod, resolver, mat_path, r0[0] if r0 else 0.1, g0[0] if g0 else 0.5)
            if fire_smoke: image, blend = fire_smoke[0], 'alpha'
        elif 'Explosion' in mat_name and 'Spark' not in mat_name:
            image, t, _ = _fireball(export, mod, resolver, mat_path)
            if t: tint = list(t)[:3]
        elif 'ImposterDebris' in mat_name:
            image, blend = _debris(export, mod, resolver, mat_path), 'alpha'
        elif 'Spark' in mat_name:
            image = _spark(mod)
        if hidden: image = None
        elif not image and not lights_only: continue
        e = {'image': image} if image else {}
        if blend: e['blend'] = blend
        cols, rows = req.get('SubImages_Horizontal') or 1, req.get('SubImages_Vertical') or 1
        if cols * rows > 1:
            e['sheet'] = [cols, rows]
            sub = mods.get('SubUV')
            if sub:
                dd = _Dist(sub.get('SubImageIndex'), objs)
                c = dd.curve()
                if c: e['frames'] = [round(min(1.0, max(0.0, v / max(1, cols * rows - 1))), 4) for v in c]
                else: e['randomFrame'] = True
        bursts = []
        for b in spawn.get('BurstList', []):
            n = b.get('Count', 0); lo = b.get('CountLow', -1)
            bursts += [round(b.get('Time', 0.0), 3), round((n + lo) / 2 if lo is not None and lo >= 0 else n)]
        e['duration'] = float(req.get('EmitterDuration') or 1.0)
        if loop_for and req.get('EmitterLoops', 1) == 0 and bursts:   # (a loop: its bursts again every EmitterDuration)
            period, once = max(0.05, e['duration']), list(bursts)
            k = 1
            while k * period < loop_for:
                for i in range(0, len(once), 2): bursts += [round(once[i] + k * period, 3), once[i + 1]]
                k += 1
        if bursts: e['bursts'] = bursts
        rate = _Dist(spawn.get('Rate'), objs).range()
        if rate and rate[1] > 0: e['rate'] = rate[1]
        if loop_for and req.get('EmitterLoops', 1) == 0: e['duration'] = float(loop_for)
        if cascade:
            if not req.get('EmitterLoops'): e['loop'] = True
            if req.get('bUseLocalSpace'): e['local'] = True
            loc = mods.get('Location')
            dl = _Dist(loc.get('StartLocation'), objs) if loc else None
            xyz = [sum(dl.range(k) or (0.0, 0.0)) / 2 for k in range(3)] if dl else None
            if xyz and any(abs(v) > 1e-3 for v in xyz): e['at'] = [round(v * CM * scale, 2) for v in _ue_axes(xyz)]
        lt = mods.get('Lifetime')
        if lt: e['life'] = [round(v, 3) for v in _Dist(lt.get('Lifetime'), objs).range()]
        sz = mods.get('Size')
        if sz:
            dx = _Dist(sz.get('StartSize'), objs)
            x = dx.range(0); y = dx.range(1)
            if x: e['size'] = [round(min(x) * CM * scale, 1), round(max(x) * CM * scale, 1)]
            if req.get('ScreenAlignment') == 'PSA_Velocity' and x and y and max(x) > 0:
                e['stretch'] = round((y[0] + y[1]) / max(1e-6, x[0] + x[1]), 2)
        sml = mods.get('SizeMultiplyLife')
        if sml:
            c = _Dist(sml.get('LifeMultiplier'), objs).curve()
            if c: e['sizeOverLife'] = [round(v, 3) for v in c]
        # colour: start colour x colour scale over life (x the fireball's Tint); its peak the HDR colour
        start = np.array([1.0, 1.0, 1.0])
        if 'Color' in mods:
            r_ = _Dist(mods['Color'].get('StartColor'), objs)
            start = np.array([r_.range(k)[1] if r_.range(k) else 1.0 for k in range(3)])
        over, alpha = None, None
        for key, ck, ak in (('ColorScaleOverLife', 'ColorScaleOverLife', 'AlphaScaleOverLife'), ('ColorOverLife', 'ColorOverLife', 'AlphaOverLife')):
            if key in mods:
                dc = _Dist(mods[key].get(ck), objs)
                curves = [dc.curve(k) for k in range(3)]
                if all(curves): over = (over if over is not None else 1.0) * np.array(curves).T
                elif dc.range(0): start = start * np.array([dc.range(k)[1] if dc.range(k) else 1.0 for k in range(3)])
                da = _Dist(mods[key].get(ak), objs)
                a = da.curve()
                if a: alpha = a
        colour = (over * start) if over is not None else np.tile(start, (SAMPLES, 1))
        colour = colour * np.array(tint)
        peak_rgb = colour.max(0)
        peak = float(peak_rgb.max()) or 1.0
        hdr = peak_rgb * (_squeeze(peak) / peak)
        e['color'] = [round(float(v), 4) for v in hdr]
        norm = colour / np.maximum(peak_rgb, 1e-9)
        if over is not None: e['colorOverLife'] = [round(float(v), 4) for v in np.clip(norm, 0, 1).reshape(-1)]
        if alpha: e['alphaOverLife'] = [round(float(np.clip(v, 0, 1)), 4) for v in alpha]
        if fire_smoke:   # (its colour B the glow's strength: the baked glow x B, squeezed; R / G were baked in)
            dc = _Dist((mods.get('ColorOverLife') or {}).get('ColorOverLife'), objs)
            b = dc.curve(2)
            bmax = max(b) if b else ((dc.range(2) or (1.0, 1.0))[1])
            hot = fire_smoke[1] * max(bmax, 1e-6)
            e['color'] = [round(_squeeze(hot), 4)] * 3
            if b: e['colorOverLife'] = [round(float(np.clip(v / max(bmax, 1e-6), 0, 1)), 4) for v in b for _ in range(3)]
            else: e.pop('colorOverLife', None)
            e['sheet'] = [fire_smoke[2], fire_smoke[3]]; e['randomFrame'] = True; e.pop('frames', None)
        # speed: along X (the emitter's forward), else outward, else from its spawn sphere
        sphere = mods.get('LocationPrimitiveSphere')
        radius = _Dist(sphere.get('StartRadius'), objs).range() if sphere else None
        if radius: e['sphere'] = round(radius[1] * CM * scale, 1)
        vel = mods.get('Velocity')
        sv = _Dist(vel.get('StartVelocity'), objs) if vel else None
        rv = _Dist(vel.get('StartVelocityRadial'), objs) if vel else None
        fwd = sv.range(0) if sv else None
        rad = rv.range(0) if rv else None
        if fwd and max(abs(fwd[0]), abs(fwd[1])) > 1e-3:
            e['speed'] = [round(min(fwd) * CM * scale, 1), round(max(fwd) * CM * scale, 1)]; e['forward'] = True
        elif rad and rad[1] > 1e-3:
            e['speed'] = [round(rad[0] * CM * scale, 1), round(rad[1] * CM * scale, 1)]
        elif sphere and sphere.get('Velocity') and radius:
            vs = _Dist(sphere.get('VelocityScale'), objs).range() or (1.0, 1.0)
            e['speed'] = [round(radius[1] * vs[0] * CM * scale, 1), round(radius[1] * vs[1] * CM * scale, 1)]
        drag = mods.get('AccelerationDrag')
        if drag:
            dr = _Dist(drag.get('DragCoefficientRaw'), objs).range()
            if dr: e['drag'] = round(dr[1], 3)
        e['inherit'] = 1.0 if 'VelocityInheritParent' in mods else 0.0
        if 'Rotation' in mods: e['randomRotation'] = True
        rr = mods.get('RotationRate')
        if rr:
            sp = _Dist(rr.get('StartRotationRate'), objs).range()
            if sp: e['spin'] = [round(sp[0] * 360.0, 1), round(sp[1] * 360.0, 1)]
        if lights_only:
            # the light: its range the particle's size x RadiusScale, its brightness squeezed (3 at Chorus's 1e9)
            lm = mods['Light']
            rs = (_Dist(lm.get('RadiusScale'), objs).range() or (1.0, 1.0))[1]
            br = (_Dist(lm.get('BrightnessOverLife'), objs).range() or (1e9, 1e9))[1]
            bd = _Dist(lm.get('BrightnessOverLife'), objs) if cascade else None
            bc = bd.curve() if bd else None
            if bc and bd.peak() > 0:   # (a brightness over life: its peak, the curve as the light's fade; the drift's starts dark)
                br = bd.peak()
                e['alphaOverLife'] = [round(float(np.clip(v / br, 0, 1)), 4) for v in bc]
            size = e.pop('size', None)
            if not size: continue
            e['light'] = round(size[1] * rs, 1)
            e['lightIntensity'] = round(3.0 * float(np.sqrt(max(br, 0.0) / 1e9)), 2)
            for k in ('speed', 'forward', 'sphere', 'drag', 'stretch', 'spin', 'randomRotation', 'sheet', 'frames', 'randomFrame'):
                e.pop(k, None)
            out.append(e); continue
        vf = mods.get('VectorFieldLocal')
        if vf and float(vf.get('Intensity', 0) or 0) > 0:   # (its turbulence: Unity's noise)
            rs = (vf.get('RelativeScale3D') or {}).get('X', 1.0)
            e['noise'] = [round(float(vf['Intensity']) * CM * scale, 1), round(float(rs) * 100.0 * CM * scale, 1)]
        if trail_of:   # (puffs along the other emitter's particles: its "trail")
            spu = mods['SpawnPerUnit']
            per = (_Dist(spu.get('SpawnPerUnit'), objs).range() or (1.0, 1.0))[1]
            t = {k: v for k, v in e.items() if k in ('image', 'blend', 'sheet', 'frames', 'randomFrame', 'randomRotation', 'life', 'size',
                                                     'sizeOverLife', 'color', 'colorOverLife', 'alphaOverLife')}
            t['every'] = round(float(spu.get('UnitScalar', 100.0)) / max(per, 1e-3) * CM * scale, 1)
            if t.get('image'): trails[trail_of] = t
            continue
        e['_name'] = name
        if blend == 'alpha':   # (a plain tint, not a glow)
            e['color'] = [round(float(v), 4) for v in tint] if custom not in (NotImplemented, None) else DEBRIS
            e.pop('colorOverLife', None)
            if 'sheet' in e: e['randomFrame'] = True; e.pop('frames', None)
        if 'Explosion' in mat_name and 'Spark' not in mat_name:
            sm = _smoke(export, mod, resolver, mat_path)
            if sm:   # (its smoke first: drawn behind the fire)
                smoke = {k: v for k, v in e.items() if k not in ('colorOverLife',)}
                smoke.update({'image': sm, 'blend': 'alpha', 'color': SMOKE})
                out.append(smoke)
        out.append(e)
    for e in out:   # (each trail on its source; a source left without one draws nothing)
        n = e.pop('_name', None)
        if n in trails: e['trail'] = trails[n]
    return [e for e in out if e.get('image') or e.get('light') or e.get('trail')]


def build(export, mod, resolver, work):
    """Writes <mod>/fx/chorus_death_<kind>.json for each kind of EFFECTS. -> {kind: its path in the mod}."""
    out = {}
    for kind, spec in EFFECTS.items():
        fx = {}
        for part in ('main', 'dying'):
            ems = []
            for name in spec[part]:
                d = _load(work, resolver, name)
                if d: ems += _emitters(export, mod, resolver, d, spec.get('dyingScale', 1.0) if part == 'dying' else 1.0)
            if ems: fx[part] = {'emitters': ems}
        if 'main' not in fx: print(f'  explosions: {kind}: nothing read'); continue
        fx['dyingCount'] = spec['dyingCount']
        rel = f'fx/chorus_death_{kind}.json'
        os.makedirs(os.path.join(mod, 'fx'), exist_ok=True)
        json.dump(fx, open(os.path.join(mod, rel), 'w', encoding='utf-8'), indent=1)
        print(f"  explosions: {kind}: {len(fx['main']['emitters'])} emitters, {len(fx.get('dying', {}).get('emitters', []))} for the tumble")
        out[kind] = rel
    return out


def apply(entries, files):
    """Gives each built ship (ships.json entries) its kind's death effects (the big ships' over LARGE_M long)."""
    for e in entries:
        if e.get('race') == -1: continue   # (the warships' parts)
        # (by the hull's length: the big fireball for a ship over LARGE_M, the fighters' for the rest, a small freighter too)
        kind = 'large' if e.get('modelLength', 0) * 0.05 > LARGE_M else 'fighter'
        if kind in files: e['deathFx'] = files[kind]
