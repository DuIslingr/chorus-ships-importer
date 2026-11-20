"""The Forsaken's drift look (the remake's ships.json "driftFx": World.ModDriftFx; docs/notes/mods-models.md "Drift energy
field"), from Chorus's own effects.

BP_Player_Ship_Phoenix (its graph's "FX Drift Started" / "FX Drift Recovery Started" events) activates four Cascade systems
as the drift starts and deactivates them as it recovers; each sits on a socket of the skeleton (SK_Phoenix_Skeleton's
SkeletalMeshSocket list: a bone, a location in cm and a rotator), so it rides the wings as they fold out:
    DriftStartParticles_L1  P_Drift_L      SCK_VFX_Drift_L2  (BONE_SM_Phoenix_wingLow_l1)
    DriftStartParticles_R1  P_Drift_R      SCK_VFX_Drift_R2  (BONE_SM_Phoenix_wingLow_r1)
    P_Drift_L_Top           P_Drift_L_Top  SCK_VFX_Drift_L4  (BONE_SM_Phoenix_wingBase_Top_l)
    P_Drift_R_Top           P_Drift_R_Top  SCK_VFX_Drift_R4  (BONE_SM_Phoenix_wingBase_Top_r)
The sockets become nodes of models/forsaken.glb (children of their bones: sockets(), rig.save_rigged), each part's effects
are written in that node's frame.

Each system's emitters (tools/explosions.py's reader with 'cascade': the editor's switched-off ones left out, Unreal's
EmitterLoops 0 as "loop", bUseLocalSpace "local", the Location module's start "at"; images by tools/rites.py's picker:
M_Pulse_Glow's dots a soft glow, the GPU sparks the explosions' streak, the refraction shock waves left out) and its energy
field: the mesh emitters on M_Drift_MagnetField (MI_Drift_MagnetField, M_Drift_MagnetField_Inst; "Bot" and "vertical" on
the side systems, "Top" on the top ones), SM_Drift_HalfSphere emitted again every 0.2 s with a 0.2 s life (a shell that
stays while the drift lasts). Each shell's mesh is baked into its part's frame (fx/drift/<system>_<n>.json, CustomFxMesh):
the emitter's mesh Size (a scale per axis), its MeshRotation start (turns: Pitch Y, Yaw Z, Roll X; the mesh's X along the
velocity under PSA_Velocity, which is zero here: no turn from it) and its Location start, then the socket frame's axes as
the remake's (explosions._ue_axes), in game units (explosions.CM). Its colour the particle's StartColor (0.4, 1, 0.9),
its brightness the shield shell's rule (npcs.CHORUS_EMISSION_PEAK / the colour's peak); the material's five textures by
its compiled shader's slots (M_Drift_MagnetField's ReferencedTextures: band T_ShockWave_Rect_G, mask T_VFX_Masks_Ellipse,
distort T_Noise_Fractal_07, line T_Line_01, background T_Noise_Tiled03), their red channel, at most 512; its parameters
are its defaults (neither instance overrides one), which the remake's CustomDriftField holds.
Left out: the refraction shock waves (M_Refraction_Grayscale_Inst), the hull's own drift glow (the Drift_Emissive_ON /
Off timelines on DMI_DriftEmissive's Emissive02_Multiplier), the dots' axis lock (camera-facing here).
"""
import json, math, os, re
import numpy as np
from PIL import Image

from . import explosions, glb, rites

UP = 'SpacePrototype/Content/UnleashedPrototype/'
SHIELD = UP + 'Player/Powers/ElementalShield/'
# (Chorus's component, its system, the socket it sits on): BP_Player_Ship_Phoenix's SCS nodes
SYSTEMS = [('DriftStartParticles_L1', SHIELD + 'P_Drift_L', 'SCK_VFX_Drift_L2'),
           ('DriftStartParticles_R1', SHIELD + 'P_Drift_R', 'SCK_VFX_Drift_R2'),
           ('P_Drift_L_Top', SHIELD + 'P_Drift_L_Top', 'SCK_VFX_Drift_L4'),
           ('P_Drift_R_Top', SHIELD + 'P_Drift_R_Top', 'SCK_VFX_Drift_R4')]
SKELETON = 'SK_Phoenix_Skeleton'
FIELD_MASTER = 'M_Drift_MagnetField'
TEXTURES = {'band': UP + 'Effects/Textures/Noise_02/T_ShockWave_Rect_G',
            'mask': UP + 'Effects/Textures/Masks/T_VFX_Masks_Ellipse',
            'distort': UP + 'Effects/Textures/Noise_02/T_Noise_Fractal_07',
            'line': UP + 'Effects/Textures/T_Line_01',
            'background': UP + 'Effects/Textures/Noise_02/T_Noise_Tiled03'}
EMISSION_PEAK = 3.0   # (npcs.CHORUS_EMISSION_PEAK: the shield shell's exposure rule)
FOLDER = 'fx/drift'


def _json(work, resolver, names):
    """{name: the exporter's JSON} of these packages (dumped once into <work>/drift)."""
    folder = os.path.join(work, 'drift'); os.makedirs(folder, exist_ok=True)
    todo = [n for n in names if not os.path.exists(os.path.join(folder, n + '.json'))]
    if todo and resolver is not None:
        resolver.run('jsonall', '/(' + '|'.join(re.escape(n) for n in todo) + r')\.uasset$', folder, capture=True)
    out = {}
    for n in names:
        f = os.path.join(folder, n + '.json')
        if os.path.exists(f): out[n] = json.load(open(f, encoding='utf-8'))
    return out


def rotator_quat(pitch, yaw, roll):
    """Unreal's FRotator::Quaternion (degrees) -> (x, y, z, w)."""
    d = math.pi / 360.0
    sp, cp = math.sin(pitch * d), math.cos(pitch * d)
    sy, cy = math.sin(yaw * d), math.cos(yaw * d)
    sr, cr = math.sin(roll * d), math.cos(roll * d)
    return (cr * sp * sy - sr * cp * cy, -cr * sp * cy - sr * cp * sy, cr * cp * sy - sr * sp * cy, cr * cp * cy + sr * sp * sy)


def rotator_matrix(pitch, yaw, roll):
    """Unreal's FRotationMatrix (degrees): rows its X, Y and Z axes (v' = v . M, row vectors)."""
    p, y, r = (math.radians(a) for a in (pitch, yaw, roll))
    sp, cp, sy, cy, sr, cr = math.sin(p), math.cos(p), math.sin(y), math.cos(y), math.sin(r), math.cos(r)
    return np.array([[cp * cy, cp * sy, sp],
                     [sr * sp * cy - cr * sy, sr * sp * sy + cr * cy, -sr * cp],
                     [-(cr * sp * cy + sr * sy), cy * sr - cr * sp * sy, cr * cp]])


def sockets(work, resolver):
    """[(socket name, bone name, glTF translation (m), glTF rotation (x, y, z, w))] of the drift's sockets, as rig nodes."""
    d = _json(work, resolver, [SKELETON]).get(SKELETON)
    if not d: return []
    want = {s for _, _, s in SYSTEMS}
    out = []
    for e in d:
        if e.get('Type') != 'SkeletalMeshSocket': continue
        p = e.get('Properties') or {}
        name = p.get('SocketName')
        if name not in want: continue
        loc = p.get('RelativeLocation') or {}; rot = p.get('RelativeRotation') or {}
        x, y, z = (float(loc.get(k, 0.0)) for k in ('X', 'Y', 'Z'))
        q = rotator_quat(float(rot.get('Pitch', 0.0)), float(rot.get('Yaw', 0.0)), float(rot.get('Roll', 0.0)))
        # (rig._ue_t / _ue_q: Unreal (x, y, z) cm -> glTF (x, z, y) m; a quaternion (x, y, z, w) -> (x, z, y, -w))
        out.append((name, p.get('BoneName'), [x / 100.0, z / 100.0, y / 100.0], [q[0], q[2], q[1], -q[3]]))
    return sorted(out)


def _objs(d):
    def objs(ref):
        if not isinstance(ref, dict) or 'ObjectPath' not in ref: return None
        i = int(ref['ObjectPath'].rsplit('.', 1)[1]); return d[i] if i < len(d) else None
    return objs


def _field_emitters(d, resolver):
    """The system's enabled mesh emitters on M_Drift_MagnetField: [{mesh path, size, at, turn, colour, life}] (cm, turns)."""
    objs = _objs(d)
    ps = next((e for e in d if e.get('Type') == 'ParticleSystem'), None)
    out = []
    for r in (ps or {}).get('Properties', {}).get('Emitters', []):
        em = objs(r)
        ep = (em or {}).get('Properties') or {}
        lods = [objs(l) for l in ep.get('LODLevels', [])]
        lod = next((l for l in lods if l and l['Name'].endswith('_0')), lods[0] if lods else None)
        if not lod: continue
        lp = lod['Properties']
        req = (objs(lp.get('RequiredModule')) or {}).get('Properties', {})
        if lp.get('bEnabled', True) is False or req.get('bEnabled', True) is False: continue
        mat_path = (req.get('Material') or {}).get('ObjectPath', '').rsplit('.', 1)[0]
        p = resolver.get(mat_path) if resolver is not None and mat_path else None
        if not p or (p.chain or [None])[-1] != FIELD_MASTER: continue
        td = (objs(lp.get('TypeDataModule')) or {}).get('Properties', {})
        mesh = (td.get('Mesh') or {}).get('ObjectPath', '').rsplit('.', 1)[0]
        if not mesh: continue
        mods = {}
        for mr in lp.get('Modules', []):
            m = objs(mr)
            if m and (m.get('Properties') or {}).get('bEnabled', True) is not False: mods.setdefault(m['Type'].replace('ParticleModule', ''), m.get('Properties') or {})

        def vec(module, key, default):
            dd = explosions._Dist((mods.get(module) or {}).get(key), objs) if module in mods else None
            return [sum(dd.range(k) or (default[k], default[k])) / 2 for k in range(3)] if dd else list(default)
        colour = vec('Color', 'StartColor', (1.0, 1.0, 1.0))
        a = explosions._Dist((mods.get('Color') or {}).get('StartAlpha'), objs).range() if 'Color' in mods else None
        out.append({'mesh': mesh, 'size': vec('Size', 'StartSize', (1.0, 1.0, 1.0)), 'at': vec('Location', 'StartLocation', (0.0, 0.0, 0.0)),
                    'turn': vec('MeshRotation', 'StartRotation', (0.0, 0.0, 0.0)), 'color': colour + [a[1] if a else 1.0],
                    'name': ep.get('EmitterName') or 'field'})
    return out


def _mesh_json(src, f, scale=1.0):
    """The shell mesh (its exported .glb) placed by the emitter 'f' in its socket's frame -> CustomFxMesh (game units)."""
    prims = glb.static_mesh(src, keep=('POSITION', 'NORMAL', 'TEXCOORD_0'))
    pos, nrm, uvs, tris = [], [], [], []
    base = 0
    for _, attrs, idx in prims:
        g = np.asarray(attrs['POSITION'], np.float64)
        ue = np.stack([g[:, 0], g[:, 2], g[:, 1]], -1) * 100.0          # glTF (m) -> Unreal (cm)
        size = np.asarray(f['size'], np.float64)
        R = rotator_matrix(f['turn'][1] * 360.0, f['turn'][2] * 360.0, f['turn'][0] * 360.0)   # (Pitch Y, Yaw Z, Roll X)
        p = (ue * size) @ R + np.asarray(f['at'], np.float64)
        pos.append(np.stack([-p[:, 0], p[:, 2], p[:, 1]], -1) * explosions.CM * scale)   # (explosions._ue_axes)
        if 'NORMAL' in attrs:
            n = np.asarray(attrs['NORMAL'], np.float64)
            n = np.stack([n[:, 0], n[:, 2], n[:, 1]], -1) / np.where(np.abs(size) > 1e-6, size, 1.0)
            n = n @ R
            n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-9)
            nrm.append(np.stack([-n[:, 0], n[:, 2], n[:, 1]], -1))
        if 'TEXCOORD_0' in attrs: uvs.append(np.asarray(attrs['TEXCOORD_0'], np.float64))
        tris.append(np.asarray(idx, np.int64) + base)
        base += len(g)
    out = {'positions': [round(float(v), 3) for v in np.concatenate(pos).reshape(-1)],
           'triangles': [int(i) for i in np.concatenate(tris)]}
    if len(nrm) == len(prims): out['normals'] = [round(float(v), 4) for v in np.concatenate(nrm).reshape(-1)]
    if len(uvs) == len(prims): out['uvs'] = [round(float(v), 5) for v in np.concatenate(uvs).reshape(-1)]
    return out


def _texture(export, mod, path):
    """A field texture's red channel into the mod (grey, at most 512 a side): its path there, or None."""
    src = os.path.join(export, path + '.png')
    if not os.path.exists(src): return None
    rel = f'{FOLDER}/{path.rsplit("/", 1)[-1]}.png'
    dst = os.path.join(mod, rel)
    if not os.path.exists(dst):
        im = Image.open(src).convert('RGBA')
        if max(im.size) > 512: im = im.resize((min(512, im.width), min(512, im.height)), Image.LANCZOS)
        r = np.asarray(im)[..., 0]
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        Image.fromarray(np.stack([r, r, r], -1), 'RGB').save(dst, optimize=True)
    return rel


def build(export, mod, resolver, work):
    """ships.json "driftFx" for the Forsaken ({} without the export): its parts on the drift's sockets, their emitters and
    fields; the shells' meshes and textures into <mod>/fx/drift."""
    if resolver is None: return {}
    names = [p.rsplit('/', 1)[1] for _, p, _ in SYSTEMS]
    systems = _json(work, resolver, names)
    if not systems: return {}
    pick = rites._picker(export, mod, resolver)
    resolver.fetch_textures(list(TEXTURES.values()), export)
    maps = {k: _texture(export, mod, p) for k, p in TEXTURES.items()}
    parts = []
    for comp, path, socket in SYSTEMS:
        name = path.rsplit('/', 1)[1]
        d = systems.get(name)
        if not d: continue
        ems = explosions._emitters(export, mod, resolver, d, pick=pick, cascade=True)
        for e in ems:
            sheet = pick.sheets.get(e.get('image'))
            if sheet and 'sheet' not in e: e['sheet'] = sheet; e['randomFrame'] = True
        fields = []
        for i, f in enumerate(_field_emitters(d, resolver)):
            mesh = f['mesh']
            src = os.path.join(export, mesh + '.glb')
            if not os.path.exists(src):
                lst = os.path.join(work, 'drift', 'meshes.txt')
                open(lst, 'w').write(mesh + '\n')
                resolver.run('export', lst, export, capture=True)
            if not os.path.exists(src): continue
            rel = f'{FOLDER}/{name.lower()}_{i}.json'
            os.makedirs(os.path.join(mod, FOLDER), exist_ok=True)
            json.dump(_mesh_json(src, f), open(os.path.join(mod, rel), 'w', encoding='utf-8'), separators=(',', ':'))
            peak = max(f['color'][:3]) or 1.0
            field = {'mesh': rel, 'color': [round(v, 4) for v in f['color']], 'exposure': round(EMISSION_PEAK / peak, 4)}
            field.update({k: v for k, v in maps.items() if v})
            fields.append(field)
        part = {'node': socket}
        if ems: part['fx'] = {'emitters': ems}
        if fields: part['fields'] = fields
        if ems or fields:
            parts.append(part)
            print(f"  drift: {name} on {socket}: {len(ems)} emitters, {len(fields)} fields")
    return {'parts': parts} if parts else {}
