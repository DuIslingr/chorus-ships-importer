"""Chorus's turrets (ArtAssets/Equipment/Armaments/Turret: the light, heavy, missile, mine and sniper turrets its capital
ships, stations and gunships mount) as turret items for the remake (items.json "fx" "turret": a model with a "pivot" that
turns and, in it, a "*_gun" node that tilts, the barrel along +Z; Modding/README "turret"), on the Hammerhead D2A2 (48),
and the NPC capital ships armed with them (npcs.py npcTurrets).

Each turret is a skeletal mesh whose rig is the same throughout: root -> baseYaw (turns) -> basePitch (tilts) -> the guns.
The model here: every triangle on the bone most of its weight sits on (the light, heavy, missile and mine turrets are
rigid; the sniper turret's few blended vertices go with their main bone), grouped by that bone's place in the rig: the
fixed base, the turning part (a "pivot" at baseYaw) and the tilting part (a "turret_gun" at basePitch); turned about its
up axis so the barrel, basePitch to the muzzle bone, points along +Z. Its materials as the hulls' (npcs._convert: Chorus's
layers), in the item's "turret" "materials". At SCALE (3.6, the ships'): 1 unit = 1 Chorus metre as made.

The stats are this importer's, on the Hammerhead D2A2's (damage 10, 280 ms, 2500 range): the light turret as it, the
heavy slower and harder hitting, the sniper far and slow, the missile turret's shots homing missiles in salvos, the mine
turret slow heavy rounds. NPC-only (occurrence 0: no shop stocks them).
"""
import json, os
import numpy as np
from . import glb, npcs, rig
from .ships import SCALE

UP = npcs.UP
ARM = UP + 'ArtAssets/Equipment/Armaments/Turret/'
# (item id, name, skeletal mesh, stats over the Hammerhead D2A2's, description)
TURRETS = [
    ('chorus_turret_light', 'Chorus Light Turret', ARM + 'SK_TER_Turret_Weak/SK_A_TER_Turret_Weak01', {},
     "A Chorus capital ship's light twin-barrelled turret."),
    ('chorus_turret_heavy', 'Chorus Heavy Turret', ARM + 'SK_TER_Turret_Heavy_01/A_TER_Turret_Heavy01_skelmesh',
     {'damage': 18, 'loadingTimeMs': 420, 'range': 2800}, "A Chorus capital ship's six-barrelled heavy turret."),
    ('chorus_turret_missile', 'Chorus Missile Turret', ARM + 'SK_TER_Turret_Missile/SK_TER_MissileTurret_001',
     {'damage': 14, 'loadingTimeMs': 900, 'range': 3500, 'missiles': 1, 'salvoShots': 2, 'salvoCount': 2, 'salvoGapMs': 150},
     "A Chorus missile turret: homing missiles in salvos."),
    ('chorus_turret_mine', 'Chorus Mine Turret', ARM + 'SK_TER_Turret_Mine/SK_Turret_Launcher_Mine',
     {'damage': 30, 'loadingTimeMs': 1400, 'range': 2200, 'projectileSpeed': 18}, "A Chorus mine launcher turret: slow, heavy rounds."),
    ('chorus_turret_sniper', 'Chorus Sniper Turret', ARM + 'SK_TER_Turret_Large/SK_TER_LargeTurret_001',
     {'damage': 40, 'loadingTimeMs': 2200, 'range': 6000, 'projectileSpeed': 60}, "A Chorus long-range sniper turret."),
]
EXPORTS = [t[2] for t in TURRETS]
BASE = 48   # the Hammerhead D2A2
MUZZLE_BONES = ('fx_jnt', 'tips_jnt', 'arm_barrel_end_r', 'heavy_turret_fx_R_4', 'barrel_4')
# (which ship carries which: npcs.CHORUS_TURRETS)


def _rest(g):
    """Each node's rest transform in the mesh's space (its parents' chain), 4 x 4."""
    parent = {c: i for i, n in enumerate(g['nodes']) for c in n.get('children', [])}
    def local(n):
        if 'matrix' in n: return np.asarray(n['matrix'], np.float64).reshape(4, 4).T
        t = np.asarray(n.get('translation', [0, 0, 0]), np.float64); x, y, z, w = n.get('rotation', [0, 0, 0, 1]); s = n.get('scale', [1, 1, 1])
        R = np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                      [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                      [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])
        M = np.eye(4); M[:3, :3] = R * np.asarray(s); M[:3, 3] = t
        return M
    out = {}
    def world(i):
        if i not in out: out[i] = (world(parent[i]) if i in parent else np.eye(4)) @ local(g['nodes'][i])
        return out[i]
    for i in range(len(g['nodes'])): world(i)
    return out, parent


def build_model(src, path, tid, export, mod, resolver):
    """One turret: -> (ships.json-style materials for its "turret" "materials", muzzle along the gun in game units)."""
    g, b = glb.load(src)
    skin = g['skins'][0]; joints = skin['joints']
    names = {i: n.get('name', '') for i, n in enumerate(g['nodes'])}
    by_name = {v: k for k, v in names.items()}
    W, parent = _rest(g)
    # the joints' rest positions in the mesh's space (their inverse bind matrices)
    ibm = glb.read(g, b, skin['inverseBindMatrices']).astype(np.float64).reshape(-1, 4, 4).transpose(0, 2, 1)
    jpos = {joints[j]: np.linalg.inv(ibm[j])[:3, 3] for j in range(len(joints))}
    yaw, pitch = by_name.get('baseYaw'), by_name.get('basePitch')
    muzzle = next((by_name[m] for m in MUZZLE_BONES if m in by_name), pitch)
    def under(node, anc):
        while node is not None:
            if node == anc: return True
            node = parent.get(node)
        return False
    p_yaw, p_pitch, p_muz = (jpos.get(n, W[n][:3, 3]) for n in (yaw, pitch, muzzle))
    fwd = p_muz - p_pitch; fwd[1] = 0
    ang = np.arctan2(fwd[0], fwd[2]) if np.linalg.norm(fwd) > 1e-6 else 0.0
    c, s_ = np.cos(-ang), np.sin(-ang)
    Ry = np.array([[c, 0, s_], [0, 1, 0], [-s_, 0, c]])   # (turns the barrel onto +Z)
    groups = {'base': [], 'pivot': [], 'gun': []}
    for mat, a, idx in glb.static_mesh(src, keep=npcs.KEEP + ('JOINTS_0', 'WEIGHTS_0')):
        J = np.asarray(a['JOINTS_0']).round().astype(int); Wt = np.asarray(a['WEIGHTS_0'])
        bone = np.array([joints[j] for j in J[np.arange(len(J)), Wt.argmax(1)]])
        tris = np.asarray(idx).reshape(-1, 3)
        tb = bone[tris[:, 0]]
        kind = np.array(['gun' if under(t, pitch) else 'pivot' if under(t, yaw) else 'base' for t in tb])
        for k, origin in (('base', np.zeros(3)), ('pivot', p_yaw), ('gun', p_pitch)):
            sel = tris[kind == k]
            if not len(sel): continue
            used, local = np.unique(sel, return_inverse=True)
            aa = {kk: np.asarray(v)[used] for kk, v in a.items() if kk not in ('JOINTS_0', 'WEIGHTS_0')}
            aa['POSITION'] = ((aa['POSITION'] - origin) @ Ry.T).astype(np.float32)
            aa['NORMAL'] = (aa['NORMAL'] @ Ry.T).astype(np.float32)
            if 'TANGENT' in aa: aa['TANGENT'] = np.concatenate([aa['TANGENT'][:, :3] @ Ry.T, aa['TANGENT'][:, 3:]], 1).astype(np.float32)
            groups[k].append((mat, aa, local.reshape(-1).astype(np.uint32)))
    # their materials as the hulls' (Chorus's layers), each group apart (its own bake names)
    mats, meshes = {}, {}
    for n_, k in enumerate(('base', 'pivot', 'gun')):
        if not groups[k]: continue
        prims, ms = npcs._convert(export, mod, f'{tid}_{k}', [groups[k]], resolver, 512)
        for m in ms: mats.setdefault(m['material'], m)
        meshes[n_] = npcs._uniform(prims)
    off_pivot = Ry @ p_yaw; off_gun = Ry @ (p_pitch - p_yaw)
    nodes = [{'name': 'base'}, {'name': 'pivot', 'translation': [float(v) for v in off_pivot]},
             {'name': 'turret_gun', 'translation': [float(v) for v in off_gun]}]
    nodes[1]['children'] = [2]
    rig.save(path, nodes, [0, 1], meshes, [], tid, keep=npcs.CHORUS_KEEP)
    along = float(np.dot(Ry @ (p_muz - p_pitch), [0, 0, 1]))
    return list(mats.values()), round(max(along, 0.0) * 20.0, 1)


def build(export, mod, resolver):
    """items.json entries for the turrets, their models in <mod>/models/turrets/."""
    os.makedirs(os.path.join(mod, 'models', 'turrets'), exist_ok=True)
    out = []
    for tid, name, mesh, stats, desc in TURRETS:
        src = os.path.join(export, mesh + '.glb')
        if not os.path.exists(src): print(f'  {tid}: not exported'); continue
        rel = f'models/turrets/{tid}.glb'
        mats, muzzle = build_model(src, os.path.join(mod, rel), tid, export, mod, resolver)
        out.append({'id': tid, 'base': BASE, 'name': name, 'description': desc + ' (Chorus)', 'techLevel': 6, 'occurrence': 0,
                    'price': 60000, 'stats': stats,
                    'fx': {'turret': {'model': rel, 'muzzle': muzzle, 'shotStart': muzzle, 'scale': SCALE, 'materials': mats}}})
        print(f'  {tid}: {len(mats)} materials, muzzle {muzzle} units')
    return out
