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
base colour where the fire, G, is weak) as an alpha-blended companion. Left out: the mesh emitters, trails spawned along
a path, vector fields.

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
            if 'Constant' in p: self.const = p['Constant']
            elif 'Max' in p or 'Min' in p: self.vals = np.array([p.get('Min', 0.0), p.get('Max', 0.0)]); self.op, self.stride = 2, 2

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


def _emitters(export, mod, resolver, d, scale=1.0):
    """CustomFxEmitter entries of one Cascade system (its JSON 'd')."""
    def objs(ref):
        if not isinstance(ref, dict) or 'ObjectPath' not in ref: return None
        i = int(ref['ObjectPath'].rsplit('.', 1)[1]); return d[i] if i < len(d) else None
    ps = next((e for e in d if e.get('Type') == 'ParticleSystem'), None)
    out = []
    for r in (ps or {}).get('Properties', {}).get('Emitters', []):
        em = objs(r)
        if not em: continue
        ep = em.get('Properties') or {}
        if ep.get('EmitterRenderMode') == 'ERM_None': continue
        lights_only = ep.get('EmitterRenderMode') == 'ERM_LightsOnly'
        lods = [objs(l) for l in ep.get('LODLevels', [])]
        lod = next((l for l in lods if l and l['Name'].endswith('_0')), lods[0] if lods else None)
        if not lod: continue
        lp = lod['Properties']
        req = (objs(lp.get('RequiredModule')) or {}).get('Properties', {})
        spawn = (objs(lp.get('SpawnModule')) or {}).get('Properties', {})
        mods = {}
        for mr in lp.get('Modules', []):
            m = objs(mr)
            if m and (m.get('Properties') or {}).get('bEnabled', True) is not False: mods.setdefault(m['Type'].replace('ParticleModule', ''), m.get('Properties') or {})
        if 'SpawnPerUnit' in mods: continue   # (a trail along a moving emitter)
        mat = (req.get('Material') or {}).get('ObjectName', '')
        mat_name = mat.split("'")[1] if "'" in mat else mat
        mat_path = (req.get('Material') or {}).get('ObjectPath', '').rsplit('.', 1)[0]
        tint, image, blend = [1.0, 1.0, 1.0], None, None
        if lights_only:
            if 'Light' not in mods: continue   # (a lights-only emitter without its light draws nothing)
        elif 'Explosion' in mat_name and 'Spark' not in mat_name:
            image, t, _ = _fireball(export, mod, resolver, mat_path)
            if t: tint = list(t)[:3]
        elif 'ImposterDebris' in mat_name:
            image, blend = _debris(export, mod, resolver, mat_path), 'alpha'
        elif 'Spark' in mat_name:
            image = _spark(mod)
        if not image and not lights_only: continue
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
        if bursts: e['bursts'] = bursts
        rate = _Dist(spawn.get('Rate'), objs).range()
        if rate and rate[1] > 0: e['rate'] = rate[1]
        e['duration'] = float(req.get('EmitterDuration') or 1.0)
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
            size = e.pop('size', None)
            if not size: continue
            e['light'] = round(size[1] * rs, 1)
            e['lightIntensity'] = round(3.0 * float(np.sqrt(max(br, 0.0) / 1e9)), 2)
            for k in ('speed', 'forward', 'sphere', 'drag', 'stretch', 'spin', 'randomRotation', 'sheet', 'frames', 'randomFrame'):
                e.pop(k, None)
            out.append(e); continue
        if blend == 'alpha':   # (a plain tint, not a glow)
            e['color'] = DEBRIS
            e.pop('colorOverLife', None)
            if 'sheet' in e: e['randomFrame'] = True; e.pop('frames', None)
        if 'Explosion' in mat_name and 'Spark' not in mat_name:
            sm = _smoke(export, mod, resolver, mat_path)
            if sm:   # (its smoke first: drawn behind the fire)
                smoke = {k: v for k, v in e.items() if k not in ('colorOverLife',)}
                smoke.update({'image': sm, 'blend': 'alpha', 'color': SMOKE})
                out.append(smoke)
        out.append(e)
    return out


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
