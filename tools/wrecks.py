"""Chorus's wrecks as the remake's ships.json "wreck" (World.WreckBreakup: the ship breaks into its wreck's pieces where it
explodes).

Chorus's NPC ships and its player ships have a wreck: a skeletal mesh (SK_*_Wreck) cut into pieces, each piece skinned to
a bone of its own, flung apart by its ABP_Explosion_* anim blueprint's ExplosionPhysics node (a C++ node of Chorus's: its
impulses aren't in the asset; the remake's WreckBreakup flies the pieces its own way). Here each triangle goes with the
bone most of its first vertex's weight sits on, each bone's triangles one piece: a node of its own whose origin is the
piece's middle (it turns about it). The wreck is in its hull's frame: turned and scaled as npcs.build turned and scaled the
hull (its nose, its blueprint's scale), so the remake places it exactly where the hull was. Its materials converted as the
hull's (npcs._convert: Chorus's layers), the whole wreck at once, each vertex carrying its piece through the conversion;
the entries added to the ship's "materials" (the remake paints the wreck with them).
"""
import os
import numpy as np
from . import glb, rig

UP = 'SpacePrototype/Content/UnleashedPrototype/'
SMALL = UP + 'ArtAssets/Vehicles/Small/'
FIGHTER = SMALL + 'TF_terranfighter/Wreck/SK_TF_Fighter_Wreck'
SCOUT = SMALL + 'TS_Scout01/TS_Scout01_Wreck'
GUNSHIP = SMALL + 'TG_Gunship/SK_TG_Gunship_Wreck'
# the gunships as they fly (their death configs' Expl_04, the wreck of that configuration: the hull with its gun pod or mine
# thrower, npcs.SHIPS "place"): Gunship01 with its gun pod, Gunship02 with its mine thrower, the Elite with its gun pod
GUNSHIP_POD = SMALL + 'TG_Gunship/Wreck/SK_TG_Gunship_Wreck_GunPod'
GUNSHIP2_MINE = SMALL + 'TG_Gunship_02/Wreck/SK_TG_Gunship_02_Wreck_Mine'
GUNSHIP_ELITE_POD = SMALL + 'TG_Gunship_Elite/Wreck/SK_TG_Gunship_Elite_Wreck_GunPod'
# ship id: its wreck (the pirates' fighter, scout and gunship are the Circle's hulls repainted: the same wrecks; Chorus keeps
# the fighter's wreck blueprint in the pirate fighter's folder)
WRECKS = {
    'circle_fighter': FIGHTER, 'pirate_fighter': FIGHTER,
    'circle_scout': SCOUT, 'pirate_scout': SCOUT,
    'circle_gunship': GUNSHIP_POD, 'pirate_gunship': GUNSHIP,   # (the pirates' fly without the pod: npcs.SHIPS)
    'circle_gunship_apex': GUNSHIP2_MINE, 'circle_gunship_elite': GUNSHIP_ELITE_POD,
    'disruptor': UP + 'ArtAssets/Affordances/SM_TER_Disruptor/SK_TER_Disruptor_Wreck_02',
    'omen_support': UP + 'NPC/Ships/OmenSupport/Art/SK_OmenSupport_02_Wreck',
    'atlas': SMALL + 'TG_Atlas/SK_TG_Atlas_Wreck',
}
PLAYER = UP + 'ArtAssets/Vehicles/Playerships/'
# the player ships' wrecks: (wreck, its scale to the hull: the Elder Buddy's is made at twice the Forsaken's size); their
# hulls aren't turned (tools/ships.py: nose +X as exported)
PLAYER_WRECKS = {'forsaken': (PLAYER + 'Phoenix/wreck/SK_PhoenixWreck', 1.0),
                 'elder_buddy': (PLAYER + 'Phoenix/wreck/SK_PhoenixWreck_Buddy', 0.5),
                 'argus': (PLAYER + 'TF_Argus/Wreck_SK/SK_TF_Argus_Wreck', 1.0)}
EXPORTS = sorted(set(WRECKS.values()) | {w for w, _ in PLAYER_WRECKS.values()})
# the pirates' hulls are the Circle's in other paint (MI_TER_NPC_Ship04 for Ship02, its lights Lights03 for Lights01): the
# wreck's materials (the Circle's, "_Wreck" / "_Dissolve") repainted the same way; the burn and damage surfaces kept
PIRATE_PAINT = [('NPC_Ship02', 'MI_TER_NPC_Ship04'), ('Lights01', 'MI_TER_NPC_Ship_Lights03')]
SECONDS = {'atlas': 10.0, 'circle_gunship': 8.0, 'pirate_gunship': 8.0, 'circle_gunship_apex': 8.0, 'circle_gunship_elite': 8.0}


def _pieces(src):
    """[(material, attributes with PIECE, indices)] of the wreck, one primitive per material and piece."""
    from . import npcs
    g, _ = glb.load(src)
    joints = g['skins'][0]['joints'] if g.get('skins') else None
    out = []
    for mat, a, idx in glb.static_mesh(src, keep=npcs.KEEP + ('JOINTS_0', 'WEIGHTS_0')):
        tris = np.asarray(idx).reshape(-1, 3)
        if joints is None or 'JOINTS_0' not in a:
            bone = np.zeros(len(tris), int)
        else:
            J = np.asarray(a['JOINTS_0']).round().astype(int); W = np.asarray(a['WEIGHTS_0'])
            vb = np.array([joints[j] for j in J[np.arange(len(J)), W.argmax(1)]])
            bone = vb[tris[:, 0]]
        for b in np.unique(bone):
            sel = tris[bone == b]
            used, local = np.unique(sel, return_inverse=True)
            aa = {k: np.asarray(v)[used] for k, v in a.items() if k not in ('JOINTS_0', 'WEIGHTS_0')}
            aa['PIECE'] = np.full((len(used), 1), float(b), np.float32)
            out.append((mat, aa, local.reshape(-1).astype(np.uint32)))
    return out


def build(export, mod, resolver, sid, nose, sc, size, override=None):
    """-> (ships.json "wreck", its materials) for ship 'sid' (turned by 'nose', scaled by 'sc' as its hull; 'override' its
    repaint, npcs.SHIPS "override": the pirates' hulls), or (None, [])."""
    from . import npcs
    path = WRECKS.get(sid) or (PLAYER_WRECKS[sid][0] if sid in PLAYER_WRECKS else None)
    src = os.path.join(export, (path or '') + '.glb')
    if not path or not os.path.exists(src): return None, []
    prims = npcs._turn(_pieces(src), nose)
    if sc != 1.0: prims = [(m, dict(a, POSITION=(np.asarray(a['POSITION']) * sc).astype(np.float32)), i) for m, a, i in prims]
    conv, mats = npcs._convert(export, mod, f'{sid}_wreck', [prims], resolver, size, override)
    groups = {}
    for m, a, i in conv:
        if 'PIECE' not in a or not len(a['PIECE']): continue
        groups.setdefault(int(a['PIECE'][0, 0]), []).append((m, {k: v for k, v in a.items() if k != 'PIECE'}, i))
    nodes, meshes = [], {}
    for n, (b, ps) in enumerate(sorted(groups.items())):
        ps = npcs._uniform(ps) if any('chorus' in e for e in mats) or any('COLOR_0' in a for _, a, _ in ps) else ps
        P = np.concatenate([np.asarray(a['POSITION']) for _, a, _ in ps])
        centre = (P.min(0) + P.max(0)) / 2
        ps = [(m, dict(a, POSITION=(np.asarray(a['POSITION']) - centre).astype(np.float32)), i) for m, a, i in ps]
        nodes.append({'name': f'piece_{n}', 'translation': [float(v) for v in centre]})
        meshes[n] = ps
    if not nodes: return None, []
    rel = f'models/wrecks/{sid}.glb'
    os.makedirs(os.path.join(mod, 'models', 'wrecks'), exist_ok=True)
    keep = npcs.CHORUS_KEEP if any('chorus' in e for e in mats) else glb.KEEP
    rig.save(os.path.join(mod, rel), nodes, list(range(len(nodes))), meshes, [], f'{sid}_wreck', keep=keep)
    # its burn: the wreck materials' Burn_Amount (MF_WreckBurn; the Forsaken's 0.95), the strongest of them; and Chorus's own
    # burn from MF_WreckBurn's compiled base pass: its Burn_Noise map (T_DamageSurface01_D), tiling, offset, falloff and
    # temperature, over UV1 where the master says so (Burn_Noise_UseUV1: the trim masters'), the vertex colour's red keeping
    # parts from burning (saturate(1 - red)) where the model keeps its colours. The first material with a map sets them.
    burns, burn_map = [], None
    attrs = {k for ps in meshes.values() for _, a, _ in ps for k in a}
    for m in sorted({m for m, _, _ in prims}):
        _, path = npcs._find_mi(export, m)
        q = npcs._params(export, path, resolver) if path and resolver is not None else None
        if q is None: continue
        if 'Burn_Amount' in q.scalars: burns.append(float(q.scalars['Burn_Amount']))
        name = q.textures.get('Burn_Noise')
        if burn_map is None and name:
            if name in q.texture_paths: resolver.fetch_textures([q.texture_paths[name]], export)
            rel_map = npcs._chorus_map(mod, npcs._png(export, name), 1024, 'data')
            if rel_map:
                uv1 = bool(q.switches.get('Burn_Noise_UseUV1')) and 'TEXCOORD_1' in attrs and 'TEXCOORD_1' in keep
                burn_map = {'burnMap': rel_map, 'burnTiling': q.scalar('Burn_NoiseTiling', 1.0), 'burnOffset': q.scalar('Burn_Noise_Offset', 0.0),
                            'burnFalloff': q.scalar('Burn_Falloff', 3.0), 'burnTemperature': q.scalar('Burn_Temperature', 1500.0),
                            'burnVertexRed': 'COLOR_0' in attrs and 'COLOR_0' in keep, 'burnUv1': uv1}
    print(f'  {sid}: its wreck in {len(nodes)} pieces')
    w = {'model': rel, 'seconds': SECONDS.get(sid, 6.0), 'speed': 1.0, 'spin': 1.0}
    if burns: w['burn'] = round(min(1.0, max(burns)), 3)
    if burn_map: w.update({k: (round(v, 5) if isinstance(v, float) else v) for k, v in burn_map.items()})
    return w, mats


def apply(e, s, export, mod, resolver, nose, sc, size):
    """Gives ships.json entry 'e' (npcs.SHIPS entry 's') its wreck (its materials added to the entry's)."""
    from . import npcs
    sid = s['id']
    override = dict(s.get('override') or {})
    if sid.startswith('pirate_') and sid in WRECKS:
        names = {m for m, _, _ in glb.static_mesh(os.path.join(export, WRECKS[sid] + '.glb'))} if os.path.exists(os.path.join(export, WRECKS[sid] + '.glb')) else set()
        for name in names:
            for part, paint in PIRATE_PAINT:
                if part in name:
                    _, path = npcs._find_mi(export, paint)
                    if path: override.setdefault(name, path)
    w, mats = build(export, mod, resolver, sid, nose, sc, size, override)
    if not w: return
    e['wreck'] = w
    have = {m['material'] for m in e.get('materials', [])}
    e['materials'] = e.get('materials', []) + [m for m in mats if m['material'] not in have]


def apply_players(entries, export, mod, resolver):
    """The player ships' wrecks (PLAYER_WRECKS) on their ships.json entries (the Forsaken's kit ships, the Argus, the Elder
    Buddy; the supercharged Forsaken is another hull)."""
    for e in entries:
        if e.get('id') in PLAYER_WRECKS:
            apply(e, {'id': e['id']}, export, mod, resolver, '+x', PLAYER_WRECKS[e['id']][1], 1024)
