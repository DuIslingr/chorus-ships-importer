"""Chorus's warships as boss fights: their parts as the remake's capital ship subsystems (ships.json "subsystems",
Modding/README "Capital ship subsystems").

Chorus builds a warship from its size's base blueprint (Core/Ships/Large/<Size>Warship/BP_<Size>Warship_Base) and a
configuration of it (NPC/Capitals/<Size>Warship/BP_NPC_Warship_<Size>_A, ...): modules (BP_Warship_Module_Artillery /
EnergyArrays / Engine / Reactor / Hangar, WeakpointAttachmentComponents), each a list of weakpoint actors on the hull mesh's
sockets (or at an offset from the ship's root, "None") with a transform; the configuration's templates override the base's.
Its hull takes no damage itself (BP_NPC_Warship_Base's DamageReceiverComponent DefaultDamageMultiplier 0): its health comes
from its modules (HealthFromModulesModifier), the weakpoints pass their damage on (bRedirectDamageToOwner) and deal
DeathDamageToOwner when destroyed. The energy arrays shield the core (GetShieldHitpoints, GetNumberOfEnergyCells; the
barriers, SM_<Size>WarshipBarriers, break when they fall: BreakBarrier, OnCoreShieldsDown), then the reactor
(BP_Device_Core_*) can be destroyed: its module's OnAllWeakpointActorsKilled starts the death throes.

Here (the remake's own terms):
- the hull: "hullDamage" 0 (hurt only through its parts), "shieldedDamage" 1 (the energy arrays shield the core, not the
  hull: the parts' passed-on hits still count while they stand), the barrier mesh in the hull model as an energy field
  ("shieldMaterial": shown while an energy array stands);
- the turret mounts (BP_TurretMount_Weak / Heavy / Sniper / Mine / Missile, their _Shield variants alike): turret parts with
  Chorus's turrets (tools/turrets.py), the heavier ones first, at most 8 (the remake's multiplayer copies carry 8);
- the energy arrays (BP_Device_EnergyArray_Line / Single): shield parts, stage 1;
- the thrusters (BP_Device_Thruster_*): weak spots;
- the reactor (BP_Device_Core_*): stage 2 (behind the energy arrays), a weak spot whose destruction destroys the ship;
- the hangar (BP_Device_ShipSpawner_Terran, the small warship's): launches Circle fighters.
Every part that passes its damage on does so at WEAK_SHARE, its death at Chorus's DeathDamageToOwner / BONUS_BASE of the
hull. The parts' models are the devices' meshes as prop ships (PROPS, npcs.py's "prop" role: race -1, never in traffic),
placed with their full turn ("turretForward" with "turretUp").
"""
import json, os, re
import numpy as np

UP = 'SpacePrototype/Content/UnleashedPrototype/'
LARGE = UP + 'ArtAssets/Vehicles/Large/'
FM = UP + 'ArtAssets/Environment/FactionMining/'
MOD = 'chorus_ships'
# ship id: (configuration blueprint, its size's base, the barrier mesh)
CONFIGS = {
    'circle_warship': ('NPC/Capitals/SmallWarship/BP_NPC_Warship_Small_A', 'Core/Ships/Large/SmallWarship/BP_SmallWarship_Base',
                       LARGE + 'SM_SmallWarship/SM_SmallWarshipBarriers'),
    'circle_destroyer': ('NPC/Capitals/MediumWarship/BP_NPC_Warship_Medium_A', 'Core/Ships/Large/MediumWarship/BP_MediumWarship_Base',
                         LARGE + 'SM_MediumWarship/SM_MediumWarshipBarriers'),
    'circle_dreadnought': ('NPC/Capitals/LargeWarship/BP_NPC_Warship_Large_ConfigA', 'Core/Ships/Large/LargeWarship/BP_LargeWarship_Base',
                           LARGE + 'SM_LargeWarship/SM_LargeWarshipBarriers'),
}
# the other configurations of a size, as ships of their own on the same model: (id suffix, configuration, name: the
# importer's words, after what they carry)
VARIANTS = {
    'circle_warship': [('c', 'NPC/Capitals/SmallWarship/BP_NPC_Warship_Small_C', 'Circle Missile Warship')],
    'circle_destroyer': [('b', 'NPC/Capitals/MediumWarship/BP_NPC_Warship_Medium_B', 'Circle Carrier Destroyer'),
                         ('c', 'NPC/Capitals/MediumWarship/BP_NPC_Warship_Medium_C', 'Circle Siege Destroyer')],
}
VARIANT_IDS = [f'{sid}_{x}' for sid, vs in VARIANTS.items() for x, _, _ in vs]
BARRIER_MATERIAL = 'MI_Barrierfield_WarshipMoreOpaque'
# the barrier as an energy field: added, Chorus's barrier red, no collision (the remake's hulls leave additive meshes out)
BARRIER = {'additive': True, 'emissionColor': [1.0, 0.28, 0.12], 'emissionIntensity': 0.35, 'ignoreVertexColors': True}
# the turret mounts' turrets (tools/turrets.py's items), heavier first when the 8 are picked
TURRETS = [('Sniper', 'chorus_turret_sniper'), ('Heavy', 'chorus_turret_heavy'), ('Missile', 'chorus_turret_missile'),
           ('Mine', 'chorus_turret_mine'), ('Weak', 'chorus_turret_light')]
# the devices (their blueprints' meshes; the core's own mesh offset, Unreal cm), kind and death damage (DeathDamageToOwner)
DEVICES = {
    'BP_Device_EnergyArray_Line': ('array', 'chorus_part_energy_array', None, 100.0),
    'BP_Device_EnergyArray_Single': ('array', 'chorus_part_energy_cell', None, 100.0),
    'BP_Device_Thruster_SmallWarship': ('thruster', 'chorus_part_thruster_small', None, 100.0),
    'BP_Device_Thruster_MediumWarship': ('thruster', 'chorus_part_thruster_medium', None, 100.0),
    'BP_Device_Thruster_MediumWarship_Fin': ('thruster', 'chorus_part_thruster_fin', None, 100.0),
    'BP_Device_Thruster_MediumWarship_Fin_Fliped': ('thruster', 'chorus_part_thruster_fin_flipped', None, 100.0),
    'BP_Device_Thruster_LargeWarship_Primary': ('thruster', 'chorus_part_thruster_large', None, 100.0),
    'BP_Device_Core_Corvette': ('core', 'chorus_part_core', None, 0.0),
    'BP_Device_Core_Frigate': ('core', 'chorus_part_core', None, 0.0),
    'BP_Device_Core_Large': ('core', 'chorus_part_core_large', (0.0, 0.0, 5130.0), 0.0),
    'BP_Device_ShipSpawner_Terran': ('hangar', None, None, 200.0),
    'BP_Device_ShipSpawner_Faceless': ('hangar', 'omen', None, 200.0),
}
TURRET_DEATH = {'Weak': 10.0}   # (BP_TurretMount_Weak's DeathDamageToOwner; the rest 15)
# the parts' models: npcs.SHIPS "prop" entries (id, name, mesh)
PROPS = [
    ('chorus_part_energy_array', 'Energy Array', FM + 'SM_TER_EnergyArrayModule_001'),
    ('chorus_part_energy_cell', 'Energy Cell', FM + 'SM_TER_EnergyArrayModule_004'),
    ('chorus_part_thruster_small', 'Thruster', LARGE + 'SM_SmallWarship/SM_SmallWarship_Thruster'),
    ('chorus_part_thruster_medium', 'Thruster', LARGE + 'SM_MediumWarship/SM_MediumWarship_Thruster'),
    ('chorus_part_thruster_fin', 'Thruster', LARGE + 'SM_MediumWarship/SM_MediumWarship_Thruster_Fin'),
    ('chorus_part_thruster_fin_flipped', 'Thruster', LARGE + 'SM_MediumWarship/SM_MediumWarship_Thruster_Fin_flipped'),
    ('chorus_part_thruster_large', 'Primary Thruster', LARGE + 'SM_LargeWarship/SM_LargeWarship_PrimaryThruster'),
    ('chorus_part_core', 'Reactor Core', UP + 'Core/WeakPoints/Art/SM_ShipCore_Frame'),
    ('chorus_part_core_large', 'Reactor Core', LARGE + 'SM_LargeWarship/SM_LargeWarship_Core'),
]
NAMES = {'array': 'Energy Array', 'thruster': 'Thruster', 'core': 'Reactor Core'}
MAX_TURRETS = 8
# Chorus passes a part's hits on whole, its hull being their sum x HealthFromModulesModifier (0.6-0.8); the remake's parked
# capital has its own hull (NpcTables.Hull: about 6000 mid-game) and a part about 1000 ((500 + 50 rank) x difficulty), so
# a share and bonuses that leave the hull a third to a half when every part but the reactor is gone: the reactor decides
WEAK_SHARE = 0.1      # (of a part's hits passed on to the hull)
BONUS_BASE = 4000.0   # (DeathDamageToOwner over this: the share of the hull a part's death takes; a thruster's 100 = 2.5 %)
HANGAR = {'ships': [f'{MOD}:circle_fighter', f'{MOD}:circle_scout'], 'every': 30, 'perWave': 2, 'maxAlive': 4, 'total': 8}
OMEN_HANGAR = {'ships': [f'{MOD}:omen_drone', f'{MOD}:omen_bat_swarm'], 'every': 25, 'perWave': 3, 'maxAlive': 6, 'total': 12}


def blueprints(resolver, work):
    """The configurations and bases as JSON in <work>/bp_wp (read from the pak once). -> the folder."""
    folder = os.path.join(work, 'bp_wp'); os.makedirs(folder, exist_ok=True)
    names = [p for c in CONFIGS.values() for p in c[:2]] + [v[1] for vs in VARIANTS.values() for v in vs]
    todo = [p for p in names if not os.path.exists(os.path.join(folder, p.rsplit('/', 1)[1] + '.json'))]
    if todo and resolver is not None:
        resolver.run('jsonall', '/(' + '|'.join(re.escape(p.rsplit('/', 1)[1]) for p in todo) + r')\.uasset$', folder, capture=True)
    return folder


def _quat(q):
    """Unreal's FQuat as its rotation matrix (row vectors: v' = v @ M)."""
    x, y, z, w = (q.get(k, 0.0) for k in 'XYZW')
    x2, y2, z2 = x + x, y + y, z + z
    xx, xy, xz, yy, yz, zz, wx, wy, wz = x * x2, x * y2, x * z2, y * y2, y * z2, z * z2, w * x2, w * y2, w * z2
    return np.array([[1 - (yy + zz), xy + wz, xz - wy], [xy - wz, 1 - (xx + zz), yz + wx], [xz + wy, yz - wx, 1 - (xx + yy)]], np.float64)


def _modules(folder, config, base):
    """{module component name: (its class, its WeakpointInfos, its offset from the root in cm)}: the base's, overridden by
    the configuration's templates."""
    mods = {}
    for name in (base, config):
        f = os.path.join(folder, name.rsplit('/', 1)[1] + '.json')
        if not os.path.exists(f): continue
        for e in json.load(open(f, encoding='utf-8')):
            t, p = e.get('Type', ''), e.get('Properties') or {}
            if not t.startswith('BP_Warship_Module_'): continue
            old = mods.get(e['Name'])
            loc = p.get('RelativeLocation')
            off = np.array([loc.get(k, 0.0) for k in 'XYZ']) if loc else (old[2] if old else np.zeros(3))
            infos = p['WeakpointInfos'] if 'WeakpointInfos' in p else (old[1] if old else [])
            mods[e['Name']] = (t, infos, off)
    return mods


def parts(work, sid, hull_mesh, config=None):
    """The warship's parts: [(class, Unreal cm position, row rotation matrix)] in its hull mesh's frame ('config' another
    configuration of its size, VARIANTS)."""
    from . import npcs
    config0, base, _ = CONFIGS[sid]
    config = config or config0
    folder = os.path.join(work, 'bp_wp')
    out = []
    for name, (t, infos, off) in _modules(folder, config, base).items():
        for w in infos:
            actor = (w.get('WeakpointActor') or {}).get('ObjectName') or ''
            cls = actor.split("'")[1].removesuffix('_C') if "'" in actor else None
            if not cls: continue
            tr = w.get('Transform') or {}
            t_ = tr.get('Translation') or {}
            loc = np.array([t_.get(k, 0.0) for k in 'XYZ'])
            rot = _quat(tr.get('Rotation') or {'W': 1.0})
            sock = npcs._socket(work, hull_mesh, w.get('SocketName')) if w.get('SocketName') not in (None, 'None') else None
            if sock is not None:
                s_loc, s_rot, s_sc = (np.asarray(v, np.float64) for v in sock)
                out.append((cls, (loc * s_sc) @ s_rot + s_loc, rot @ s_rot))
            else:
                out.append((cls, loc + off, rot))
    return out


CM = 0.72              # game units a Chorus centimetre (the ships' SCALE 3.6)
SHIELD_SHARE = 0.75    # (a shielded turret mount's own shield, x its hull: shot down first, BP_TurretMount_ShieldBreakEffect)
THROES_BLASTS = 12     # (the countdown's blasts over the hull: BP_NPC_Warship_Base's ExplosionVFX every 0.2 - 0.3 s inside)


def _throes(work, sid):
    """(PhaseDuration s, ExplosionDamageRadius cm) of the warship's size base, or None."""
    f = os.path.join(work, 'bp_wp', CONFIGS[sid][1].rsplit('/', 1)[1] + '.json')
    if not os.path.exists(f): return None
    for e in json.load(open(f, encoding='utf-8')):
        if e.get('Name', '').startswith('Default__'):
            p = e.get('Properties') or {}
            if p.get('PhaseDuration') and p.get('ExplosionDamageRadius'): return float(p['PhaseDuration']), float(p['ExplosionDamageRadius'])
    return None


def _spread(items, n):
    """At most n of the items, spread over the list."""
    if n <= 0: return []
    if len(items) <= n: return list(items)
    return [items[int(i * len(items) / n)] for i in range(n)]


def _turret(cls):
    for word, item in TURRETS:
        if f'_{word}' in cls: return word, item
    return None, None


MAX_EXHAUSTS = 8


def _nozzle(work, prop, pos, rot):
    """A thruster part's nozzle: the rear of its mesh along the device's forward (Unreal cm in the hull's frame) and the
    nozzle's half width (cm), or None when the part's mesh wasn't exported."""
    mesh = next((m for i, _, m in PROPS if i == prop), None)
    src = os.path.join(work, 'export', (mesh or '') + '.glb')
    if not mesh or not os.path.exists(src): return None
    from . import glb
    P = np.concatenate([np.asarray(a['POSITION'], np.float64) for _, a, _ in glb.static_mesh(src)]) * 100.0   # (glb: Unreal x, z, y)
    ue = np.stack([P[:, 0], P[:, 2], P[:, 1]], 1)
    lo, hi = ue.min(0), ue.max(0)
    rear = np.array([lo[0], (lo[1] + hi[1]) / 2, (lo[2] + hi[2]) / 2])
    return pos + rear @ rot, float(min(hi[1] - lo[1], hi[2] - lo[2])) * 0.3


def apply(e, s, work, mats, nose, sc, k, shrink, config=None):
    """Turns the ships.json entry 'e' of a Chorus warship (npcs.SHIPS entry 's'; its hull built by npcs.build: 'nose' its
    turn, 'sc' its blueprint's scale, 'k' game units per model metre, 'shrink' its scale-down) into a boss fight with its
    parts."""
    from . import npcs
    sid = s['id']
    hull_mesh = s['meshes'][0]
    found = parts(work, sid, hull_mesh, config)
    if not found: print(f'  {sid}: no parts (its blueprints not read)'); return
    turn = npcs.ROT[nose]
    def turned(v_cm, point=True):   # Unreal cm in the hull's frame -> its turned model frame (metres, or a unit direction)
        v = np.array([v_cm[0], v_cm[2], v_cm[1]], np.float32) / (100.0 if point else 1.0)
        return turn(v[None, :])[0] * (sc if point else 1.0)
    def game(v): return [round(-float(v[2]) * k, 1), round(float(v[1]) * k, 1), round(float(v[0]) * k, 1)]
    def axis(d):
        v = turned(d, False); v = v / max(float(np.linalg.norm(v)), 1e-8)
        return [round(-float(v[2]), 4), round(float(v[1]), 4), round(float(v[0]), 4)]
    subs, turrets, nozzles = [], [], []
    for cls, pos, rot in found:
        word, item = _turret(cls)
        if item:
            death = TURRET_DEATH.get(word, 15.0)
            turrets.append((TURRETS.index((word, item)), {'kind': 'turret', 'name': f'{word if word != "Weak" else "Light"} turret',
                            'position_engine': game(turned(pos)), 'turretUp': axis(rot[2]), 'item': f'{MOD}:{item}',
                            'weakspot': WEAK_SHARE, 'bonus': round(death / BONUS_BASE, 4),
                            **({'shield': SHIELD_SHARE} if '_Shield' in cls else {})}))
            continue
        dev = DEVICES.get(cls)
        if dev is None: print(f'  {sid}: {cls} left out'); continue
        kind, prop, mesh_off, death = dev
        if mesh_off is not None: pos = pos + np.asarray(mesh_off) @ rot   # (the device's mesh off its origin: the core's)
        if kind == 'hangar':
            subs.append({'kind': 'hangar', 'model': 'none', 'position_engine': game(turned(pos)), 'turretUp': axis(rot[2]),
                         **(OMEN_HANGAR if prop == 'omen' else HANGAR)})
            continue
        p = {'kind': 'object', 'name': NAMES[kind], 'model': f'{MOD}:{prop}', 'position_engine': game(turned(pos)),
             'turretUp': axis(rot[2]), 'turretForward': axis(rot[0])}
        if shrink < 1.0: p['scale'] = round(shrink, 4)
        if kind == 'array': p.update({'shields': True, 'stage': 1, 'bonus': round(death / BONUS_BASE, 4)})
        elif kind == 'thruster':
            p.update({'weakspot': WEAK_SHARE, 'bonus': round(death / BONUS_BASE, 4)})
            n = _nozzle(work, prop, pos, rot)
            if n: nozzles.append((game(turned(n[0])), max(round(n[1] / 100.0 * sc * k), 8)))
        elif kind == 'core': p.update({'stage': 2, 'weakspot': 1.0, 'bonus': 1.0})
        subs.append(p)
    # the turrets: the heavier first, the rest spread over the hull
    turrets.sort(key=lambda t: t[0])
    heavy = [t for _, t in turrets if t['item'] != f'{MOD}:chorus_turret_light']
    light = [t for _, t in turrets if t['item'] == f'{MOD}:chorus_turret_light']
    room = max(0, MAX_TURRETS - len(heavy))
    picked = heavy[:MAX_TURRETS] + _spread(light, room)
    e['subsystems'] = picked + subs
    # the reactor going critical (BP_<Size>Warship_Base's PhaseDuration and ExplosionDamageRadius; OnDeathDamageAmount 1000,
    # a fighter's hull and more: all of a ship's at its middle, falling off to the edge)
    throes = _throes(work, s['id'])
    if throes: e['deathThroes'] = {'seconds': throes[0], 'radius': round(throes[1] * CM * shrink), 'damage': 1.0, 'blasts': THROES_BLASTS}
    e['hullDamage'] = 0
    e['shieldedDamage'] = 1
    # (its turret mounts' npcTurrets give way to the turret parts; its exhausts go to its thrusters' nozzles)
    e['mounts'] = [m for m in e['mounts'] if m.get('slotType') != 2]
    if nozzles:
        glow = next((m.get('glowColor') for m in e['mounts'] if m.get('slotType') == 3), s.get('glow'))
        e['mounts'] = [m for m in e['mounts'] if m.get('slotType') != 3] + [
            {'slotType': 3, 'position_engine': at, 'turretAngles': [0.35, 0.35, 0.35], 'glowColor': glow, 'glowSize': [r, r, 40]}
            for at, r in nozzles[:MAX_EXHAUSTS]]
    e.pop('npcTurrets', None)
    for m in mats:
        if BARRIER_MATERIAL.lower() in m['material'].lower():
            for key in list(m):
                if key != 'material': del m[key]
            m.update(BARRIER)
            e['shieldMaterial'] = m['material']
            e['shieldBlocks'] = True   # (Chorus's barriers block the way in until they break)
    counts = {}
    for p in e['subsystems']: counts[p.get('name', p['kind'])] = counts.get(p.get('name', p['kind']), 0) + 1
    print(f'  {sid}: {len(e["subsystems"])} parts ({", ".join(f"{n} {c}" for n, c in counts.items())}; '
          f'{len(turrets) - len(picked)} turrets left out)')


def variants(e, s, work, mats, nose, sc, k, shrink):
    """The other configurations of the warship's size (VARIANTS) as ships.json entries of their own on its model."""
    import copy
    out = []
    for suffix, config, name in VARIANTS.get(s['id'], []):
        v = copy.deepcopy(e)
        v.update({'id': f"{s['id']}_{suffix}", 'name': name})
        vm = copy.deepcopy(mats)
        v['materials'] = vm
        for key in ('subsystems', 'deathThroes', 'shieldMaterial', 'shieldBlocks'): v.pop(key, None)
        apply(v, s, work, vm, nose, sc, k, shrink, config)
        out.append(v)
    return out
