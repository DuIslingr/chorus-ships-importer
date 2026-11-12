"""Chorus's player capital ship (the PCLS, "player-controlled large ship": Player/Ships/CapitalShip/Ship/BP_Player_Ship_Capital
on SK_PlayerControlledLargeShip01, the warship Nara takes over; its NPC twin BP_NPC_Warship_PCLS_SpiritClass) as a ship the
player can own in the remake (ships.json), with its three weapons as items (items.json):

- the Artillery (BP_Player_Weapon_Artillery_PlayerCapitalShip: 14 barrels on SK_Artillery_* sockets, each aimed at the
  target, 100 a shot every 0.05 s, 3.15 km) -> an auto turret on the HH-AT "Archimedes" (182), the light turret's model
  (BP_Player_WeaponMesh_Artillery is SK_A_TER_Turret_Weak01), on six of the sockets (turret slots);
- the Death Ray (BP_Player_Weapon_DeathRay_PlayerCapitalShip: SK_DeathRay_* sockets, a 200 m wide hitscan, 2 s cooldown)
  -> a heavy, slow primary on the M6 A3 "Wolverine" (11), the large turret's red;
- the Broadside Missile Barrage (BP_Player_Weapon_BroadsideMissileBarrage_PlayerCapitalShip: 20 launchers along the sides,
  30 homing missiles over 3 s, each 75 over 500 m when it dies) -> homing missiles in salvos with an area blast on the
  Intelli Jet (37), a secondary.
The ship: Chorus's 5000 hull (the Forsaken's 1000) and its slow turn (12 deg/s) as GoF2's heaviest hull and slowest
handling and then some, 1.5x boost (the game's own); sold in a lounge late in the game. Its model is the NPC Captured
Warship's (npcs.py), measured from the hull's middle: the remake fits a camera to a hull over 150 m and centres it on its
pivot (PlayerHull.FitCamera), so its mounts are given from there. Its thrusters' places are the blueprint's
SM_Warship_Thruster_VFX_* components; their colour its thruster lights' (FCB4EF).
"""
import json, os, re
import numpy as np

UP = 'SpacePrototype/Content/UnleashedPrototype/'
HOST = 'captured_warship'   # (npcs.SHIPS: the same mesh, its model shared)
SHIP_ID = 'chorus_pcls'
BLUEPRINT = UP + 'Player/Ships/CapitalShip/Ship/BP_Player_Ship_Capital'
SKELETON = UP + 'ArtAssets/Vehicles/Playerships/PlayerControlledLargeShip/SK_PlayerControlledLargeShip01_Skeleton'
MOD = 'chorus_ships'
GLOW = [0.99, 0.71, 0.94]
# the six artillery barrels that become turret mounts (of 14: two on top, two below, one a side)
TURRET_SOCKETS = ['SK_Artillery_Top_1', 'SK_Artillery_Top_2', 'SK_Artillery_Bottom_1', 'SK_Artillery_Bottom_2',
                  'SK_Artillery_Left_1', 'SK_Artillery_Right_1']
PRIMARY_SOCKETS = ['SK_DeathRay_Top_1', 'SK_DeathRay_Bottom_1']
SECONDARY_SOCKETS = ['SK_Missile_Left_1', 'SK_Missile_Right_1']
ITEMS = [
    {'id': 'chorus_capital_artillery', 'base': 182, 'name': 'PCLS Artillery',
     'description': "The capital ship's artillery barrel: an automatic turret that aims itself at whatever you fight. (Chorus)",
     'techLevel': 9, 'occurrence': 3, 'price': [450000, 470000],
     'stats': {'damage': 14, 'loadingTimeMs': 150, 'range': 3150, 'projectileSpeed': 32},
     'turret': 'chorus_turret_light', 'color': [1.0, 0.18, 0.1]},
    {'id': 'chorus_capital_deathray', 'base': 11, 'name': 'PCLS Death Ray',
     'description': "The capital ship's death ray: a slow, crushing beam that cuts through anything in front of it. (Chorus)",
     'techLevel': 9, 'occurrence': 2, 'price': [900000, 940000],
     'stats': {'damage': 320, 'loadingTimeMs': 2500, 'range': 4500, 'projectileSpeed': 60}, 'color': [1.0, 0.1, 0.35]},
    {'id': 'chorus_capital_barrage', 'base': 37, 'name': 'PCLS Broadside Barrage',
     'description': "The capital ship's broadside missiles: homing salvos that blow up over a wide area. (Chorus)",
     'techLevel': 9, 'occurrence': 3, 'price': [900, 950],
     'stats': {'damage': 75, 'empDamage': 0, 'loadingTimeMs': 3000, 'range': 9000, 'projectileSpeed': 22, 'salvoShots': 5,
               'salvoCount': 2, 'salvoGapMs': 300, 'echoDelayMs': 80, 'echoPercent': 100, 'echoRadius': 10000},
     'color': [1.0, 0.0, 0.0]},
]


def items(turret_items):
    """items.json entries for the three weapons (the artillery on the light turret's model, from tools/turrets.py)."""
    by_id = {t['id']: t for t in turret_items}
    out = []
    for spec in ITEMS:
        it = {k: v for k, v in spec.items() if k not in ('turret', 'color')}
        it['stats'] = dict(spec['stats'])
        fx = {'projectile': {'color': spec['color'], 'glow': 3 if spec['base'] != 37 else 2}}
        if spec.get('turret'):
            t = by_id.get(spec['turret'])
            if t is None: print(f"  {spec['id']}: {spec['turret']} not built"); continue
            fx['turret'] = dict(t['fx']['turret'])
        it['fx'] = fx
        out.append(it)
    return out


def blueprints(resolver, work):
    """The player capital's blueprint and skeleton as JSON in <work>/bp_cap (read once)."""
    folder = os.path.join(work, 'bp_cap'); os.makedirs(folder, exist_ok=True)
    todo = [p for p in (BLUEPRINT, SKELETON) if not os.path.exists(os.path.join(folder, p.rsplit('/', 1)[1] + '.json'))]
    if todo and resolver is not None:
        resolver.run('jsonall', '/(' + '|'.join(re.escape(p.rsplit('/', 1)[1]) for p in todo) + r')\.uasset$', folder, capture=True)
    return folder


def _sockets(folder):
    """{socket: (Unreal cm, rotation row matrix)} of the skeleton (on its root bone: the hull's frame)."""
    from . import npcs
    f = os.path.join(folder, SKELETON.rsplit('/', 1)[1] + '.json')
    out = {}
    if not os.path.exists(f): return out
    for e in json.load(open(f, encoding='utf-8')):
        if e.get('Type') != 'SkeletalMeshSocket': continue
        p = e.get('Properties') or {}
        loc, rot = p.get('RelativeLocation') or {}, p.get('RelativeRotation') or {}
        out[p.get('SocketName')] = (np.array([loc.get(k, 0.0) for k in 'XYZ']),
                                    npcs._rotator(rot.get('Pitch', 0.0), rot.get('Yaw', 0.0), rot.get('Roll', 0.0)).astype(np.float64))
    return out


def _thrusters(folder):
    """[(Unreal cm, scale)] of the blueprint's thruster effect meshes."""
    f = os.path.join(folder, BLUEPRINT.rsplit('/', 1)[1] + '.json')
    out = []
    if not os.path.exists(f): return out
    for e in json.load(open(f, encoding='utf-8')):
        p = e.get('Properties') or {}
        if e.get('Type') == 'StaticMeshComponent' and 'PCLS_Thruster' in (p.get('ComponentTags') or []):
            loc, sc = p.get('RelativeLocation') or {}, p.get('RelativeScale3D') or {}
            out.append((np.array([loc.get(k, 0.0) for k in 'XYZ']), float(np.mean([sc.get(k, 1.0) for k in 'XYZ']))))
    return out


def player_entry(host, s, work, prims, nose, sc, k):
    """The ships.json entry of the player's capital ship, on the NPC Captured Warship's built entry 'host' (npcs.SHIPS
    entry 's', its prims as drawn, its turn 'nose', scale 'sc', 'k' game units per model metre)."""
    from . import glb, npcs
    folder = os.path.join(work, 'bp_cap')
    socks = _sockets(folder)
    if not socks: print(f'  {SHIP_ID}: its skeleton not read'); return None
    lo, hi = glb.bounds(prims)
    centre = (np.asarray(lo, np.float64) + np.asarray(hi, np.float64)) / 2   # (FitCamera puts the hull's middle on the pivot)
    turn = npcs.ROT[nose]
    def turned(v_cm, point=True):
        v = np.array([v_cm[0], v_cm[2], v_cm[1]], np.float32) / (100.0 if point else 1.0)
        return turn(v[None, :])[0] * (sc if point else 1.0)
    def game(v): v = v - centre; return [round(-float(v[2]) * k, 1), round(float(v[1]) * k, 1), round(float(v[0]) * k, 1)]
    def axis(d):
        v = turned(d, False); v = v / max(float(np.linalg.norm(v)), 1e-8)
        return [round(-float(v[2]), 4), round(float(v[1]), 4), round(float(v[0]), 4)]
    mounts = []
    for name in PRIMARY_SOCKETS:
        if name in socks: mounts.append({'slotType': 0, 'position_engine': game(turned(socks[name][0]))})
    for name in SECONDARY_SOCKETS:
        if name in socks: mounts.append({'slotType': 1, 'position_engine': game(turned(socks[name][0]))})
    for name in TURRET_SOCKETS:
        if name in socks:
            loc, rot = socks[name]
            mounts.append({'slotType': 2, 'position_engine': game(turned(loc)), 'turretUp': axis(rot[2])})
    for loc, scale in _thrusters(folder):
        r = max(round(6.0 * scale * k), 8)   # (the thruster group's nozzle: about 6 m across at scale 1)
        mounts.append({'slotType': 3, 'position_engine': game(turned(loc)), 'turretAngles': [0.35, 0.35, 0.35],
                       'glowColor': GLOW, 'glowSize': [r, r, round(r * 4)]})
    count = lambda t: sum(1 for m in mounts if m['slotType'] == t)
    e = {'id': SHIP_ID, 'name': 'Spirit-class Capital Ship', 'race': 0,
         'description': "The warship Chorus's Nara takes over and flies: a capital ship of your own, slow to turn, with self-aiming "
                        "artillery, a death ray and broadside missile barrages. Its hull and shields dwarf any fighter's. (Chorus)",
         'armor': 2500, 'cargo': 600, 'handling': 25, 'price': 25000000, 'priceDefault': 0,
         'slots': {'primary': count(0), 'secondary': count(1), 'turret': count(2), 'equipment': 16},
         'model': host['model'], 'modelLength': host['modelLength'], 'modelYaw': host.get('modelYaw', 90),
         'hangarHeight': host.get('hangarHeight', 0), 'engineGlowColor': GLOW, 'mounts': mounts,
         'materials': host['materials'], 'explosionScale': host.get('explosionScale', 6.0),
         'lounge': {'systemRace': -1, 'minCampaign': 50, 'minRank': 18, 'chance': 2}, 'flightStyle': 'chorus'}
    print(f"  {SHIP_ID}: player capital ship on {HOST}'s model, {count(0)} primaries, {count(1)} secondaries, "
          f"{count(2)} turrets, {count(3)} thrusters")
    return e
