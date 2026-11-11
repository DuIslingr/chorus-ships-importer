# The Chorus ships the importer builds, as the remake's ships.json entries (Modding/README "ships.json").
#
# Positions: the export's glTF is Unreal's frame in metres with X forward, Y up, Z right (Unreal (x, y, z) cm ->
# (x, z, y) / 100). The remake turns the model by modelYaw 90 (nose +X -> +Z) and scales it to modelLength; mounts are
# game units in the ship's frame (x toward the pilot's left, y up, z forward): (-gz, gy, gx) x k, k = SCALE / 0.05 game
# units per glTF metre (the same mapping as the EVERSPACE 2 importer's warships.ue_to_game).
import json, os
import numpy as np
from . import glb, textures

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


def _colours(mi, force=False):
    """The emissive masks' colours: (channel, linear rgb, multiplier); Emissive02 -> G, Emissive03 -> B."""
    cols, sc = mi.get('Colors', {}), mi.get('Scalars', {})
    out = []
    for name, ch in (('Emissive02', 1), ('Emissive03', 2)):
        if name in cols:
            c = cols[name]
            mult = 1.0 if force else float(sc.get(name + '_Multiplier', 1.0))   # (a missing multiplier: the parent's, taken as 1)
            out.append((ch, [c['R'], c['G'], c['B']], mult))
    return out


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


def forsaken(export, mod):
    """Builds models/forsaken.glb and maps/*, returns the ships.json entry."""
    src = os.path.join(export, PHOENIX, 'skelmesh', 'SK_Phoenix.glb')
    prims = glb.static_mesh(src)
    lo, hi = glb.bounds(prims)
    length = float(hi[0] - lo[0])                       # along the nose (glTF X)
    os.makedirs(os.path.join(mod, 'models'), exist_ok=True); os.makedirs(os.path.join(mod, 'maps'), exist_ok=True)
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
        entry.update(textures.convert_material(tex_dir, names, _colours(mi, force=short == 'thruster'), os.path.join(mod, 'maps'), 'forsaken_' + short))
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
        {'slotType': 0, 'position_engine': to_game(bone('SM_Phoenix_wpnPlatform_01_l'))},   # SCK_Weapon_L
        {'slotType': 0, 'position_engine': to_game(bone('SM_Phoenix_wpnPlatform_01_r'))},   # SCK_Weapon_R
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
    }
