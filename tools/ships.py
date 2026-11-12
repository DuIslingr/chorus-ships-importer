# The Chorus ships the importer builds, as the remake's ships.json entries (Modding/README "ships.json").
#
# Positions: the export's glTF is Unreal's frame in metres with X forward, Y up, Z right (Unreal (x, y, z) cm ->
# (x, z, y) / 100). The remake turns the model by modelYaw 90 (nose +X -> +Z) and scales it to modelLength; mounts are
# game units in the ship's frame (x toward the pilot's left, y up, z forward): (-gz, gy, gx) x k, k = SCALE / 0.05 game
# units per glTF metre (the same mapping as the EVERSPACE 2 importer's warships.ue_to_game).
import json, os, shutil
import numpy as np
from PIL import Image
from . import glb, rig, textures
from . import mi as mip   # (material parameters through the parents; "mi" is the local instance below)

SCALE = 3.6          # Chorus metres -> remake metres, as the EVERSPACE 2 importer sizes ES2's ships next to GoF2's
UNIT = 0.05          # remake metres per game unit
K = SCALE / UNIT     # game units per exported metre

PHOENIX = 'SpacePrototype/Content/UnleashedPrototype/ArtAssets/Vehicles/Playerships/Phoenix'


def to_game(p):
    gx, gy, gz = (float(v) for v in p)
    return [round(-gz * K, 1), round(gy * K, 1), round(gx * K, 1)]


def _mi(export, path):
    return json.load(open(os.path.join(export, path + '.json'), encoding='utf-8'))


def _tex(mi, *keys):
    for k in keys:
        t = mi.get('Textures', {}).get(k)
        if t: return t['ObjectName'].split("'")[1]
    return None


def _params(export, path, resolver=None):
    """The material instance's parameters: resolved through its parents (tools/mi.py) when a resolver is given, else only
    its own (the exporter's JSON)."""
    if resolver is not None: return resolver.get(path)
    own, p = _mi(export, path), mip.Params()
    p.scalars.update(own.get('Scalars', {})); p.switches.update(own.get('Switches', {}))
    p.vectors.update({k: [c['R'], c['G'], c['B']] for k, c in own.get('Colors', {}).items()})
    p.textures.update({k: v['ObjectName'].split("'")[1] for k, v in own.get('Textures', {}).items()})
    return p


def _colours(p, force=False, skip=()):
    """The emissive masks' colours: (channel, linear rgb, multiplier) for M_Phoenix's Emissive01 -> R, Emissive02 -> G,
    Emissive03 -> B, each times its Emissive0N_Multiplier (force: 1, for the thrusters the game drives at run time; skip:
    channels drawn otherwise, the glow lines' wave)."""
    out = []
    for name, ch in (('Emissive01', 0), ('Emissive02', 1), ('Emissive03', 2)):
        if ch in skip: continue
        c = p.vector(name)
        if c is None: continue
        mult = 1.0 if force else p.scalar(name + '_Multiplier', 1.0)
        if mult > 0: out.append((ch, list(c), mult))
    return out


WAVE_PATTERN = 'T_HexPatternNoise_01_A'


def _wave(export, mod, p, tex_dir, mask, name, resolver):
    """M_Phoenix's glow lines (its compiled base pass: Emissive02 isn't read; Emissive02 Min / Max are, along a wave over the
    Magnetic Plates Pattern) as the material's "wave" block (the remake's GoF2/Hull GlowWave), or None: the masks' green
    channel x Emissive02_Multiplier, the pattern x Magnetic Pattern Tiling, the wave a cycle a second (View.GameTime)."""
    mult = p.scalar('Emissive02_Multiplier', 1.0)
    lo, hi = p.vector('Emissive02 Min'), p.vector('Emissive02 Max')
    src = os.path.join(tex_dir, (mask or '') + '.png')
    if mult <= 0 or not lo or not hi or not mask or not os.path.exists(src): return None
    pattern = p.textures.get('Magnetic Plates Pattern') or WAVE_PATTERN
    path = getattr(p, 'texture_paths', {}).get(pattern)
    if path and resolver is not None: resolver.fetch_textures([path], export)
    psrc = os.path.join(export, (path or '') + '.png')
    if not path or not os.path.exists(psrc): return None
    maps = os.path.join(mod, 'maps')
    prel = f'maps/{pattern.lower()}.png'
    if not os.path.exists(os.path.join(mod, prel)): shutil.copyfile(psrc, os.path.join(mod, prel))
    # (the masks' green alone, at the emission map's size)
    m = Image.open(src).convert('RGBA').split()[1]
    if m.width > 1024: m = m.resize((1024, 1024 * m.height // m.width), Image.LANCZOS)
    mrel = f'maps/{name}_wave.png'
    m.convert('RGB').save(os.path.join(maps, f'{name}_wave.png'), optimize=True)
    return {'pattern': prel, 'mask': mrel, 'channel': 1, 'tiling': p.scalar('Magnetic Pattern Tiling', 1.0), 'speed': 1.0,
            'multiplier': mult, 'min': [round(v, 4) for v in lo[:3]], 'max': [round(v, 4) for v in hi[:3]]}


def nozzle_faces(prims, material, depth=0.6):
    """Per side, the nozzle of the thruster mesh: its rear-facing triangles (normal within ~30 degrees of backward)
    no more than `depth` metres ahead of that side's rearmost one, area-weighted. -> [(centre, (half height, half width))]."""
    out = []
    for name, a, idx in prims:
        if name != material: continue
        p = a['POSITION']; t = idx.reshape(-1, 3)
        A, B, C = p[t[:, 0]], p[t[:, 1]], p[t[:, 2]]
        cr = np.cross(B - A, C - A); area = np.linalg.norm(cr, axis=1) / 2
        nx = cr[:, 0] / np.maximum(2 * area, 1e-9); cen = (A + B + C) / 3
        for side in (-1, 1):
            m = (nx < -0.85) & (np.sign(cen[:, 2]) == side)
            if not m.any(): continue
            m &= cen[:, 0] < cen[m][:, 0].min() + depth
            w = area[m]; c = (cen[m] * w[:, None]).sum(0) / w.sum()
            out.append((c, (np.ptp(cen[m][:, 1]) / 2, np.ptp(cen[m][:, 2]) / 2)))
    return out


# The Forsaken's material instances (ShipSkin_Forsaken's "Main" list) and how each is drawn.
FORSAKEN_MATERIALS = [
    ('MI_Phoenix_thruster01', PHOENIX + '/MI_Phoenix_thruster01', 'thruster'),
    ('MI_Phoenix_center_Moveable', PHOENIX + '/MI_Phoenix_center_Moveable', 'center_moveable'),
    ('MI_Phoenix_outer_wing', PHOENIX + '/MI_Phoenix_outer_wing', 'outer_wing'),
    ('MI_Phoenix_center_static', PHOENIX + '/MI_Phoenix_center_static', 'center_static'),
    ('MI_Phoenix_inner_wing', PHOENIX + '/MI_Phoenix_inner_wing', 'inner_wing'),
    ('MI_Phoenix_cockpit', PHOENIX + '/MI_Phoenix_cockpit', 'cockpit'),
    ('MI_WeaponMount', PHOENIX + '/Weapons/WeaponMount/MI_WeaponMount', 'weapon_mount'),
]


def forsaken(export, mod, resolver=None, anims=None):
    """Builds models/forsaken.glb and maps/*, returns the ships.json entry. resolver: a tools/mi.Resolver (the glow
    colours an instance inherits from its parents)."""
    src = os.path.join(export, PHOENIX, 'skelmesh', 'SK_Phoenix.glb')
    prims = glb.static_mesh(src)
    lo, hi = glb.bounds(prims)
    length = float(hi[0] - lo[0])                       # along the nose (glTF X)
    os.makedirs(os.path.join(mod, 'models'), exist_ok=True); os.makedirs(os.path.join(mod, 'maps'), exist_ok=True)
    if anims:   # Chorus's drift: the parts on the skeleton, with its clips (tools/rig.py)
        rig.save_rigged(os.path.join(mod, 'models', 'forsaken.glb'), src, prims, anims, 'forsaken')
    else:
        glb.save(os.path.join(mod, 'models', 'forsaken.glb'), prims, 'forsaken')

    materials = []
    for mat, mi_path, short in FORSAKEN_MATERIALS:
        mi = _mi(export, mi_path)
        tex_dir = os.path.dirname(os.path.join(export, mi_path))
        names = {'diffuse': _tex(mi, 'Albedo', 'PM_Diffuse'), 'normal': _tex(mi, 'Normal', 'PM_Normals'),
                 'rmo': _tex(mi, 'RMO', 'PM_SpecularMasks'), 'emissive': _tex(mi, 'Emissive Masks', 'PM_Emissive')}
        # An instance that leaves its colour / normal map to its parent (MI_Phoenix_center_Moveable: MI_Phoenix's) uses
        # its own set's siblings, T_<set>_D / _N (exported by name, import.EXPORTS).
        stem = (names['rmo'] or names['emissive'] or '').rsplit('_', 1)[0]
        for key, suffix in (('diffuse', '_D'), ('normal', '_N')):
            if not names[key] and stem: names[key] = stem + suffix
        entry = {'material': mat}
        p = _params(export, mi_path, resolver)
        wave = _wave(export, mod, p, tex_dir, names['emissive'], 'forsaken_' + short, resolver) if short != 'thruster' and resolver is not None else None
        entry.update(textures.convert_material(tex_dir, names, _colours(p, force=short == 'thruster', skip=(1,) if wave else ()), os.path.join(mod, 'maps'), 'forsaken_' + short))
        if wave: entry['wave'] = wave
        if short == 'thruster' and 'emission' in entry:
            # The nozzles' glow multipliers are 0 in the asset (the game drives them with the thrust at run time):
            # here the glow follows the engines (dim at idle, full at full throttle).
            entry.update({'engine': True, 'engineIdle': 0.25, 'emissionIntensity': 4.0})
        materials.append(entry)

    nozzles = nozzle_faces(prims, 'MI_Phoenix_thruster01')
    j = glb.joint_positions(src)
    def bone(name): return j['BONE_' + name]
    mid = lambda a, b: (bone(a) + bone(b)) / 2
    glow = [0.0, 0.61, 1.0]                             # the thruster's Emissive02, 009CFF
    mounts = [
        {'slotType': 0, 'position_engine': to_game(bone('SM_Phoenix_wpnPlatform_01_l')),     # SCK_Weapon_L
         **({'follow': rig.FOLLOW['SM_Phoenix_wpnPlatform_01_l']} if anims else {})},       # (riding the platform: rig.py)
        {'slotType': 0, 'position_engine': to_game(bone('SM_Phoenix_wpnPlatform_01_r')),     # SCK_Weapon_R
         **({'follow': rig.FOLLOW['SM_Phoenix_wpnPlatform_01_r']} if anims else {})},
        {'slotType': 1, 'position_engine': to_game(mid('SK_Phoenix_wingWeaponAttach_l', 'SK_Phoenix_wingWeaponAttach_r'))},
    ]
    for centre, half in nozzles:                        # the thrusters' nozzles (their rear faces), one per side
        mounts.append({'slotType': 3, 'position_engine': to_game(centre), 'turretAngles': [0.35, 0.35, 0.35],
                       'glowColor': glow, 'glowSize': [round(half[1] * K), round(half[0] * K), 40]})
    cockpit = to_game(bone('SM_Phoenix_cockpitWindow'))

    return {
        'id': 'forsaken',
        'name': 'Forsaken',
        'description': "Nara's sentient fighter from Chorus: a fast, agile hull whose wings fold out for combat, "
                       'with twin guns on its wing platforms and a launcher under the nose.',
        'race': 0,
        'armor': 560, 'cargo': 35, 'handling': 160,
        'price': 3900000, 'priceDefault': 0,
        'slots': {'primary': 2, 'secondary': 1, 'turret': 0, 'equipment': 12},
        'model': 'models/forsaken.glb',
        'icon': 'icons/forsaken.png',
        'modelLength': round(length * K), 'modelYaw': 90,
        'hangarHeight': round(-float(lo[1]) * K + 20),
        'cockpit': cockpit,
        'engineGlowColor': glow,
        'mounts': mounts,
        'materials': materials,
        'lounge': {'systemRace': -1, 'minCampaign': 20, 'minRank': 8, 'chance': 6},
        # The remake's Chorus flight (FlightModel.StepChorus, 2026-11-11): this ship always flies as in Chorus; import.py's
        # --flight-style changes it ("player" leaves it to the player's option).
        'flightStyle': 'chorus',
        **({'animations': rig.ANIMATIONS} if anims else {}),
    }


# ---- the Elder Buddy: the Forsaken's hull in the Elder set (BP_Player_Ship_ElderBuddy's OverrideMaterials) ----------------
# The Elder hull instances set no glow colours of their own: they inherit them through MI_Elder_Theia_* and
# MI_ElderAmaranth_* from the Forsaken's (MI_Phoenix_*), so the glow lines are the Forsaken's cyan and the centre's
# accent its red. Only the thruster is the Elder's own: Emissive02 1 / 0.43 / 0, its engine glow.
ELDER_ORANGE = [1.0, 0.432, 0.0]
ELDER_MATERIALS = [
    ('MI_Phoenix_thruster01', PHOENIX + '/MI_Elder_Buddy_thruster', 'thruster'),
    ('MI_Phoenix_center_Moveable', PHOENIX + '/MI_Elder_Buddy_center_moveable', 'center_moveable'),
    ('MI_Phoenix_outer_wing', PHOENIX + '/MI_Elder_Buddy_outer_wing', 'outer_wing'),
    ('MI_Phoenix_center_static', PHOENIX + '/MI_Elder_Buddy_center_static', 'center_static'),
    ('MI_Phoenix_inner_wing', PHOENIX + '/MI_Elder_Buddy_inner_wing', 'inner_wing'),
    ('MI_Phoenix_cockpit', PHOENIX + '/MI_Elder_Buddy_cockpit', 'cockpit'),
]
ELDER_EXPORTS = [p for _, p, _ in ELDER_MATERIALS]


def elder_buddy(export, mod, forsaken_entry, resolver=None):
    """The Elder Buddy: the Forsaken's model and mounts with the Elder material set (its maps under maps/elder_*); -> the
    ships.json entry (its "materials" name the Forsaken model's own materials, so a kit can use them as a skin)."""
    materials = []
    for mat, mi_path, short in ELDER_MATERIALS:
        if not os.path.exists(os.path.join(export, mi_path + '.json')): continue
        mi = _mi(export, mi_path)
        tex_dir = os.path.dirname(os.path.join(export, mi_path))
        names = {'diffuse': _tex(mi, 'Albedo', 'PM_Diffuse'), 'normal': _tex(mi, 'Normal', 'PM_Normals'),
                 'rmo': _tex(mi, 'RMO', 'PM_SpecularMasks'), 'emissive': _tex(mi, 'Emissive Masks', 'PM_Emissive')}
        # (their masks' blue is 1 everywhere, unused: Emissive03_Multiplier is 0; green, Emissive02, lights the lines)
        p = _params(export, mi_path, resolver)
        wave = _wave(export, mod, p, tex_dir, names['emissive'], 'elder_' + short, resolver) if short != 'thruster' and resolver is not None else None
        colours = _colours(p, force=short == 'thruster', skip=(1,) if wave else ())
        entry = {'material': mat}
        entry.update(textures.convert_material(tex_dir, names, colours, os.path.join(mod, 'maps'), 'elder_' + short))
        if wave: entry['wave'] = wave
        if short == 'thruster' and 'emission' in entry:
            entry.update({'engine': True, 'engineIdle': 0.25, 'emissionIntensity': 4.0})
        materials.append(entry)
    e = dict(forsaken_entry)
    e.update({'id': 'elder_buddy', 'name': 'Elder Buddy',
              'description': "The Forsaken in the Elder's colours, from Chorus: the same agile hull in the Elder's plating, "
                             'its thrusters burning orange.',
              'armor': 600, 'handling': 155, 'price': 4300000, 'icon': 'icons/elder_buddy.png',
              'engineGlowColor': ELDER_ORANGE, 'materials': materials,
              'mounts': [dict(m, glowColor=ELDER_ORANGE) if m.get('slotType') == 3 else m for m in forsaken_entry['mounts']],
              'lounge': {'systemRace': -1, 'minCampaign': 30, 'minRank': 10, 'chance': 4}})
    return e


# ---- the Argus (BP_Player_Ship_Argus, SK_TF_Argus) --------------------------------------------------------------------
ARGUS = 'SpacePrototype/Content/UnleashedPrototype/ArtAssets/Vehicles/Playerships/TF_Argus'
ARGUS_EXPORTS = [ARGUS + '/SK_TF_Argus']
ARGUS_MATERIALS = ['MI_Argus_Hull', 'MI_Argus_Tech', 'MI_Argus_Cockpit', 'MI_Argus_Cockpitglass']
ARGUS_GLOW = [1.0, 0.6, 0.3]   # (not read: the boost's shock diamonds are an effect material)


def _argus_colours(p):
    """The Argus's emissive map is a colour map; its instances weight its channels (EmissiveIntensity_R / _G / _B)."""
    return [(0, [1, 0, 0], p.scalar('EmissiveIntensity_R', 1.0)), (1, [0, 1, 0], p.scalar('EmissiveIntensity_G', 1.0)),
            (2, [0, 0, 1], p.scalar('EmissiveIntensity_B', 1.0))]


def _vertex_glow(mod, name, mesh, p):
    """M_Argus_Master's "Use VC as Emissve": the glow is the mesh's vertex colours, not the (empty) emissive map. Red marks
    the lit trim and vents (x EmissiveIntensity_R), blue the small lights (x EmissiveIntensity_B); green is a soft
    gradient over whole panels, the hull-heat mask ("Glow Hull" parameters, Glow Alpha 0 at rest): left out. Baked over
    UV set 0 (unique on the hull) -> the material's emission fields, or {} when nothing glows."""
    uv, col, idx = mesh
    w = np.array([p.scalar('EmissiveIntensity_R', 1.0), 0.0, p.scalar('EmissiveIntensity_B', 1.0)], np.float32)
    w *= p.scalar('EmissiveBoost', 1.0) or 1.0
    img = textures.bake_vertex_colours(uv, col * w[None, :], idx, 1024)
    peak = float(img.max())
    if peak <= 1e-3: return {}
    textures._save(textures.linear_to_srgb(img / peak), os.path.join(mod, 'maps', name + '_e.png'), 1024, 'RGB')
    return {'emission': f'maps/{name}_e.png', 'emissionColor': [1, 1, 1], 'emissionIntensity': round(peak, 3)}


def argus(export, mod, resolver=None):
    """models/argus.glb and its maps; -> the ships.json entry, or None without the export."""
    src = os.path.join(export, ARGUS, 'SK_TF_Argus.glb')
    if not os.path.exists(src): return None
    prims = glb.static_mesh(src, keep=tuple(glb.KEEP) + ('COLOR_0',))
    vc = {m: (a['TEXCOORD_0'], np.asarray(a['COLOR_0'], np.float32)[:, :3], i) for m, a, i in prims if 'COLOR_0' in a and 'TEXCOORD_0' in a}
    prims = [(m, {k: v for k, v in a.items() if k != 'COLOR_0'}, i) for m, a, i in prims]
    lo, hi = glb.bounds(prims)
    length = float(hi[0] - lo[0])
    glb.save(os.path.join(mod, 'models', 'argus.glb'), prims, 'argus')
    materials = []
    for mat in sorted({p[0] for p in prims}):
        mi_path = ARGUS + '/' + mat
        if not os.path.exists(os.path.join(export, mi_path + '.json')): continue
        mi = _mi(export, mi_path)
        names = {'diffuse': _tex(mi, 'Albedo', 'PM_Diffuse', 'Diffuse', 'BaseColor'), 'normal': _tex(mi, 'Normal', 'PM_Normals'),
                 'rmo': _tex(mi, 'MRO', 'RMO', 'PM_SpecularMasks'), 'emissive': _tex(mi, 'Emissive', 'Emissive Masks', 'PM_Emissive')}
        names = {k: v for k, v in names.items() if v}
        # (texture parameter names differ per master material: fall back on the instance's own textures by suffix)
        for t in (v['ObjectName'].split("'")[1] for v in mi.get('Textures', {}).values()):
            for key, suf in (('diffuse', '_D'), ('normal', '_N'), ('rmo', '_MRO'), ('emissive', '_E')):
                if key not in names and t.endswith(suf): names[key] = t
        entry = {'material': mat}
        p = _params(export, mi_path, resolver)
        if p.switch('Use VC as Emissve'): names.pop('emissive', None)   # (the master reads the vertex colours instead)
        entry.update(textures.convert_material(os.path.dirname(os.path.join(export, mi_path)), names, _argus_colours(p),
                                               os.path.join(mod, 'maps'), 'argus_' + mat.lower().replace('mi_argus_', ''),
                                               layout='MRO'))
        if p.switch('Use VC as Emissve') and mat in vc and float(np.min(vc[mat][0])) >= 0 and float(np.max(vc[mat][0])) <= 1:
            entry.update(_vertex_glow(mod, 'argus_' + mat.lower().replace('mi_argus_', ''), vc[mat], p))
        if mat == 'MI_Argus_Cockpitglass': entry.update({'color': [0.05, 0.08, 0.1]})
        materials.append(entry)
    j = glb.joint_positions(src)
    bone = lambda n: j['BONE_SM_Argus_' + n]
    mounts = [{'slotType': 0, 'position_engine': to_game(bone('L_Weapon_B_00'))},
              {'slotType': 0, 'position_engine': to_game(bone('R_Weapon_B_00'))},
              {'slotType': 1, 'position_engine': to_game(bone('L_Weapon_A_00'))}]
    for centre, half in nozzle_faces(prims, 'MI_Argus_Tech'):
        mounts.append({'slotType': 3, 'position_engine': to_game(centre), 'turretAngles': [0.35, 0.35, 0.35],
                       'glowColor': ARGUS_GLOW, 'glowSize': [round(half[1] * K), round(half[0] * K), 40]})
    glass = next((p[1]['POSITION'] for p in prims if p[0] == 'MI_Argus_Cockpitglass'), None)
    cockpit = to_game(glass.mean(0)) if glass is not None else to_game([1.0, 1.5, 0.0])
    return {
        'id': 'argus', 'name': 'Argus',
        'description': 'A heavy fighter from Chorus: broader and better armoured than the Forsaken, with guns on both '
                       'flanks and a launcher under its long nose.',
        'race': 0, 'armor': 760, 'cargo': 60, 'handling': 125,
        'price': 4800000, 'priceDefault': 0,
        'slots': {'primary': 2, 'secondary': 1, 'turret': 0, 'equipment': 14},
        'model': 'models/argus.glb', 'icon': 'icons/argus.png',
        'modelLength': round(length * K), 'modelYaw': 90,
        'hangarHeight': round(-float(lo[1]) * K + 20),
        'cockpit': cockpit, 'engineGlowColor': ARGUS_GLOW,
        'mounts': mounts, 'materials': materials,
        'lounge': {'systemRace': -1, 'minCampaign': 40, 'minRank': 12, 'chance': 4},
        'flightStyle': 'chorus',
    }
