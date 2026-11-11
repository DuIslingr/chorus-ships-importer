"""The Forsaken as a ship kit (the remake's shipkits.json, Modding/README "Customizable ships"), so its weapons show: one hull
part (models/forsaken.glb, at the kit's scale and yaw, the same size as the plain ship), and "hardpoints" rules that put
Chorus's own weapon model of each mounted Chorus gun on its mount (the weapon platforms), and a Chorus model of the same kind on any other primary (the game's lasers, blasters and thermo guns a Glow,
auto-cannons and the rest a Talon); secondaries show none. A "toggle" lets the player hide them in the Customize screen.

Chorus mounts one weapon model per kind and tier (ArtAssets/Vehicles/Playerships/Phoenix: SK_Gatling_01 and Weapons/SK_*),
exported in Chorus's frame like the hull (X forward, Y up, metres, origin at the attach point). Each becomes a static glb
with a "muzzle" node at the middle of its front, where the remake moves that gun's shots. Their material instances are
converted like the hull's; the emissive masks take the hull's cyan glow (the weapon instances set no colours of their own).
"""
import json, os
import numpy as np
from . import glb, textures
from .ships import PHOENIX, SCALE, _mi, _tex

KIT_ID = 'forsaken'
MOD_ID = 'chorus_ships'
GLOW = [0.0, 0.61, 1.0]

# item id (tools/weapons.py) -> the weapon's mesh under PHOENIX
WEAPON_MESHES = {
    'chorus_gatling_t1': 'SK_Gatling_01', 'chorus_gatling_t2a': 'Weapons/SK_GatlingT2A', 'chorus_gatling_t2b': 'Weapons/SK_GatlingT2B',
    'chorus_gatling_t3a': 'Weapons/SK_GatlingT3A', 'chorus_gatling_t3b': 'Weapons/SK_GatlingT3B',
    'chorus_laser_t1': 'Weapons/SK_LaserT1', 'chorus_laser_t2a': 'Weapons/SK_LaserT2A', 'chorus_laser_t2b': 'Weapons/SK_LaserT2B',
    'chorus_laser_t3a': 'Weapons/SK_LaserT3A', 'chorus_laser_t3b': 'Weapons/SK_LaserT3B',
}
# (Chorus's launchers, SK_MissileT1..T3B, sit on the same platforms as the guns; the remake's secondary mount is between
# the wing attach points, inside the hull, so secondaries show no model.)
EXPORTS = [PHOENIX + '/' + p for p in WEAPON_MESHES.values()]
# The game's weapons by category: lasers (0), blasters (1), thermo guns -> the Glow; the rest of the primaries the Talon.
ENERGY_CATEGORIES = [0, 1, 3]


def muzzle(prims):
    """The middle of the model's front face: x at its foremost point, y / z the bounds' middle."""
    lo, hi = glb.bounds(prims)
    return [float(hi[0]), float((lo[1] + hi[1]) / 2), float((lo[2] + hi[2]) / 2)]


def weapons(export, mod):
    """models/weapons/*.glb, their maps; -> (the kit's "hardpoints", its weapon materials). Missing meshes are left out."""
    rules, materials, done = [], [], set()
    os.makedirs(os.path.join(mod, 'models', 'weapons'), exist_ok=True)
    os.makedirs(os.path.join(mod, 'maps'), exist_ok=True)
    models = {}
    for wid, rel in WEAPON_MESHES.items():
        src = os.path.join(export, PHOENIX, rel + '.glb')
        if not os.path.exists(src):
            print(f'  {rel}: not exported')
            continue
        prims = glb.static_mesh(src)
        name = os.path.basename(rel).lower()
        path = 'models/weapons/' + name + '.glb'
        glb.save(os.path.join(mod, path), prims, name, nodes={'muzzle': muzzle(prims)})
        models[wid] = path
        for mat, _, _ in prims:
            if mat in done: continue
            done.add(mat)
            mi_path = os.path.join(os.path.dirname(PHOENIX + '/' + rel), mat)
            if not os.path.exists(os.path.join(export, mi_path + '.json')): continue
            mi = _mi(export, mi_path)
            names = {'diffuse': _tex(mi, 'Albedo', 'PM_Diffuse'), 'normal': _tex(mi, 'Normal', 'PM_Normals'),
                     'rmo': _tex(mi, 'RMO', 'PM_SpecularMasks'), 'emissive': _tex(mi, 'Emissive Masks', 'PM_Emissive')}
            entry = {'material': mat}
            entry.update(textures.convert_material(os.path.dirname(os.path.join(export, mi_path)), names,
                                                   [(1, GLOW, 1.0), (2, GLOW, 1.0)], os.path.join(mod, 'maps'),
                                                   'weapon_' + mat.lower(), size=1024, small=512))
            materials.append(entry)
        rules.append({'slot': 'primary', 'model': path, 'items': [f'{MOD_ID}:{wid}']})
    # Every other weapon: a Chorus model of its kind.
    if 'chorus_laser_t1' in models: rules.append({'slot': 'primary', 'model': models['chorus_laser_t1'], 'categories': ENERGY_CATEGORIES})
    if 'chorus_gatling_t1' in models: rules.append({'slot': 'primary', 'model': models['chorus_gatling_t1']})
    rules.append({'slot': 'secondary', 'model': ''})
    return {'toggle': True, 'weapons': rules}, materials


SKIN_FIELDS = ('material', 'diffuse', 'normal', 'metallicSmoothness', 'emission', 'emissionColor', 'emissionIntensity')


def _kit_ship(ship, build):
    entry = {k: v for k, v in ship.items() if k not in ('model', 'modelLength', 'modelYaw', 'materials', 'hangarHeight')}
    entry.update({'kit': KIT_ID, 'kitType': KIT_ID, 'build': build})
    return entry


def build(export, mod, ship, skinned=()):
    """shipkits.json (one kit) and the ship entries turned into kit ships (model -> kit / kitType / build). `skinned`: ships
    on the same hull with materials of their own (the Elder Buddy), each a kit skin of its id that its ship wears (and the
    Forsaken's Customize screen offers)."""
    hardpoints, weapon_materials = weapons(export, mod)
    kit = {'id': KIT_ID, 'name': 'Forsaken', 'slots': ['hull'], 'scale': SCALE, 'yaw': ship.get('modelYaw', 90),
           'materials': ship.get('materials', []) + weapon_materials,
           'parts': [{'id': 'forsaken', 'slot': 'hull', 'name': 'Forsaken', 'model': ship['model'], 'types': [KIT_ID]}],
           'hardpoints': hardpoints}
    entries = [_kit_ship(ship, {'hull': 'forsaken'})]
    skins = []
    for other in skinned:
        skins.append({'id': other['id'], 'name': other['name'], 'types': [KIT_ID],
                      'engineColor': other.get('engineGlowColor', [1, 1, 1]),
                      'materials': [{k: m[k] for k in SKIN_FIELDS if k in m} for m in other.get('materials', [])]})
        entries.append(_kit_ship(other, {'hull': 'forsaken', 'skin': other['id']}))
    if skins: kit['skins'] = skins
    return [kit], entries
