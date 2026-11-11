"""Every Chorus ship the player doesn't fly, as ships.json entries no one sells: the remake's NPCs fly them with its own
hulls and guns (only the look is Chorus's), by role (Modding/README "traffic", "Capital ships and freighters"):

  fighter    "traffic": {weight, races}: flown by that race's NPC fighters (up to 150 m long)
  boss       "traffic": {boss: true}: the pirate bosses fly it (up to 400 m)
  freighter  "traffic": {capital: "freighter"}: one of the orbits' freighters now and then
  capital    "traffic": {capital: "battleship"}: parked in the orbit as its capital ship; a pirate (8) or Void (9) one is
             hostile and comes with raids
  player     sold by Space Lounge visitors and flown with Chorus flight, like the Forsaken (import.py gives it the
             Forsaken's sounds and an icon)
  A fighter longer than 150 m becomes a boss; a boss stays under 400 m, capital ships and freighters under 4.5 km
  (Modding/README: the flight level's far plane is 15 km), scaled down past it.

Races: the Circle (Chorus's cult) and the pirates -> 8 (pirates), the Omen (the Rift's ships) -> 9 (Void), the civilians
and the Terran military -> Terran (0) and, for freighters, every race's systems.

A ship is one mesh or several modelled in place (a hull and its set dressing: windows, lights; the battleship's seven
modules), turned nose forward (+X, the importer's frame): away from the hull's thruster glow when it has one, else
Unreal's forward (+X), unless the table says ("nose": the container ship and the battleship are modelled along Y).

Materials, by Chorus's master materials (their parameters resolved through the instances' parents, tools/mi.py; rebuilt
in Unity's terms, so approximations where Chorus's shaders layer more):
  baked (per source mesh, over its UV set 2, the unique lightmap layout, into one material, <id>_hull<n>):
    M_NPCShipTrimMaster / M_TrimLayersMaster: trim sheets. A triangle's colour is one swatch of a 256-pixel palette
      (LayerColors, by UV set 3) and its metalness the swatch's LayerData red; the trim sheet (UV set 0, tiling) gives the
      ambient occlusion (Trim AAO blue), roughness (green) and normals; the trim emissive lights the strips whose UVs are
      shifted out of the sheet's row ("Use UV shift to mask trim emissive"), its channels in their tints
    M_PlatingMaster: the palette swatch times the plating's albedo (UV set 0), its ORM and normal map
    M_SimpleMaster (tech panels): their own maps over UV set 0; the emissive mask's channels in the channel colours
    The normals are carried from UV set 0's tangent frame into UV set 2's.
  flat glows: windows (emissive_Color), station and running lights (Emissive_01_Color / Color Emissive), thruster glows
    (StandingColor / Color, following the engines)
  their own maps: single-texture hulls (the Atlases' M_Terran_Hull: Metalness_Roughness_AO), the Omen bones, the Forsaken
    master's (M_Phoenix: the Elder ship), M_JTU_Blend (the Prophet)
  Omen tissue (M_JTU_Faceless, no colour map): the Outer Glow Color as the base colour times the ambient occlusion, and
    the Inner Glow Color glowing through the thin parts (the thickness map, to the power of its Inner Contrast); the cores
    (Enable Core) glow in the Inner Core Color
  flat colours: Sav's and Ree's coats, floaters, the bat swarm's bone, Guilt's shell (with its red glow)
  left out: decals (they need alpha blending), the thruster flames and other effect materials
"""
import glob, json, os, re
import numpy as np
from PIL import Image
from . import glb, textures
from .ships import K, SCALE, _tex, _params, _colours

UP = 'SpacePrototype/Content/UnleashedPrototype/'
SMALL, LARGE, NPC = UP + 'ArtAssets/Vehicles/Small/', UP + 'ArtAssets/Vehicles/Large/', UP + 'NPC/Ships/'
PLAYER = UP + 'ArtAssets/Vehicles/Playerships/'
OMEN_GLOW = [1.0, 0.1, 0.05]   # (the engine glow: the Omen's Inner Glow Color, dimmed)
CIRCLE_GLOW, PIRATE_GLOW, TER_GLOW = [1.0, 0.25, 0.1], [0.6, 0.8, 0.1], [0.05, 0.45, 1.0]
FREIGHT_RACES = [0, 1, 2, 3]
MAX_TRAFFIC, MAX_BOSS, MAX_CAPITAL = 150.0, 400.0, 4500.0   # metres (Modding/README)


def S(sid, name, meshes, role, races, armor, glow, **kw):
    """A ship: id, fallback name (this importer's own words; "bp" reads Chorus's from the pak), meshes, role, races, armour,
    engine glow; options: bp (its NPC blueprint: the display name), name_from ('bp' / 'mesh': a character's ship, named
    by its asset), override ({material: pak path}: a variant's materials), nose, weight, traffic_role."""
    return dict(id=sid, name=name, meshes=[meshes] if isinstance(meshes, str) else meshes, role=role, races=races,
                armor=armor, glow=glow, **kw)


def _civ(n, kind):   # the numbered civilian traffic models
    return LARGE + f'Civilian_Ship_Traffic/SM_TER_CIV_Ship_Traffic_{kind}_{n:03d}'


ATLAS2 = SMALL + 'TG_Atlas_MK2/'
SHIPS = [
    # -- the Circle's and the pirates' fighters (their names: the blueprints' display names, read at build time) ----------
    S('circle_fighter', 'Circle Fighter', SMALL + 'TF_terranfighter/TF_Fighter', 'fighter', [8], 180, CIRCLE_GLOW, bp=NPC + 'Fighter/BP_NPC_Ship_Fighter'),
    S('circle_fighter_snipe', 'Circle Sniper', SMALL + 'TF_terranfighter_02/SM_TF_terranfighter_02', 'fighter', [8], 200, CIRCLE_GLOW,
      bp=NPC + 'FighterSnipe/BP_NPC_Ship_Fighter_Snipe', traffic_role='sniper'),
    S('circle_fighter_net', 'Circle Elite Fighter', SMALL + 'TF_terranfighter_Elite/SM_TF_terranfighter_Elite', 'fighter', [8], 240, CIRCLE_GLOW,
      bp=NPC + 'FighterNet/BP_NPC_Ship_Fighter_Net', traffic_role='webber'),
    S('student_fighter', 'Student Fighter', SMALL + 'TF_Fighter_Student/TF_Fighter_Student', 'fighter', [8], 150, CIRCLE_GLOW,
      bp=NPC + 'FactionStudent/BP_NPC_Ship_Fighter_Student'),
    S('circle_scout', 'Circle Scout', SMALL + 'TS_Scout01/TS_Scout01', 'fighter', [8], 140, CIRCLE_GLOW, bp=NPC + 'Scout/BP_NPC_Ship_Scout'),
    S('circle_support', 'Circle Support Ship', SMALL + 'TS_SupportShip/SM_TS_Supportship', 'fighter', [8], 200, CIRCLE_GLOW,
      bp=NPC + 'SupportShip/BP_NPC_Ship_SupportShip', traffic_role='shieldCharger'),
    S('circle_support_drone', 'Circle Support Drone', SMALL + 'SupportDrone/SM_TER_SupportDrone', 'fighter', [8], 90, CIRCLE_GLOW),
    S('disruptor', 'Disruptor', UP + 'ArtAssets/Affordances/SM_TER_Disruptor/SM_TER_Disruptor', 'fighter', [8], 220, CIRCLE_GLOW,
      bp=NPC + 'Disruptor/BP_NPC_Ship_Disruptor', name_from='bp', traffic_role='jumpSuppressor'),
    S('pirate_fighter', 'Pirate Fighter', SMALL + 'TF_Fighter_Pirate/TF_Fighter_Pirate', 'fighter', [8], 170, PIRATE_GLOW,
      bp=NPC + 'Pirate/FighterPirate/BP_NPC_Ship_Fighter_Pirate'),
    S('pirate_scout', 'Pirate Scout', SMALL + 'TS_Scout01_Pirate/TS_Scout01_Pirate', 'fighter', [8], 130, PIRATE_GLOW,
      bp=NPC + 'Pirate/ScoutPirate/BP_NPC_Ship_ScoutPirate'),
    S('elder_ship', 'Elder Ship', NPC + 'Elder/Base/SM_NPC_Ship_Elder_Base', 'fighter', [0], 400, [0.0, 0.61, 1.0], weight=0.3),
    S('ufo', 'Unidentified Craft', SMALL + 'TU_Ufo/SM_TU_Ufo', 'fighter', [9], 300, [0.4, 1.0, 0.5], weight=0.2),
    # -- gunships and the characters' ships: bosses --------------------------------------------------------------------
    S('circle_gunship', 'Circle Gunship', SMALL + 'TG_Gunship/TG_gunship', 'boss', [8], 900, CIRCLE_GLOW, bp=NPC + 'Gunship/BP_NPC_Ship_Gunship'),
    S('circle_gunship_apex', 'Circle Heavy Gunship', SMALL + 'TG_Gunship_02/SM_TG_Gunship_02', 'boss', [8], 950, CIRCLE_GLOW, bp=NPC + 'Gunship2/BP_NPC_Ship_Gunship2'),
    S('circle_gunship_elite', 'Circle Elite Gunship', SMALL + 'TG_Gunship_Elite/SM_TG_Gunship_Elite', 'boss', [8], 1100, CIRCLE_GLOW,
      bp=NPC + 'GunshipElite/BP_NPC_Ship_GunshipElite'),
    S('student_gunship', 'Student Gunship', SMALL + 'TG_Gunship_Elite_Cerene/SM_TG_Gunship_Elite_Cerene', 'boss', [8], 1200, CIRCLE_GLOW,
      bp=NPC + 'FactionStudent/BP_NPC_Ship_Cerene_Student', name_from='bp'),
    S('terran_gunship', 'Terran Gunship', SMALL + 'TG_terrangunship_MK2/SM_TS_terran_gunship2', 'boss', [8], 950, TER_GLOW),
    S('pirate_gunship', 'Pirate Gunship', SMALL + 'TG_Gunship_Pirate/TG_Gunship_Pirate', 'boss', [8], 900, PIRATE_GLOW,
      bp=NPC + 'Pirate/GunshipPirate/BP_NPC_Ship_Gunship_Pirate'),
    S('pirate_queen', 'Pirate Leader', SMALL + 'TF_Fighter_Sniper_Pirate/TF_Fighter_Sniper_Pirate', 'boss', [8], 1200, PIRATE_GLOW,
      bp=NPC + 'Pirate/PirateQueen/BP_NPC_Ship_PirateQueen', name_from='bp'),
    S('prophet', 'Final Boss', SMALL + 'SM_NPC_Prophet/SM_NPC_Prophet', 'boss', [8], 1500, CIRCLE_GLOW,
      bp=NPC + 'FinalBoss/Prophet/BP_NPC_Ship_FinalBoss_Prophet', name_from='bp'),
    S('sav', 'Named Ship 1', LARGE + 'SM_Sav/SM_Sav', 'boss', [8], 1000, TER_GLOW, bp=NPC + 'Sav/BP_NPC_Ship_Sav', name_from='bp'),
    S('ree', 'Named Ship 2', LARGE + 'SM_Ree/SM_Ree', 'boss', [8], 1000, TER_GLOW, bp=NPC + 'Ree/BP_NPC_Ship_Ree', name_from='bp'),
    S('aryana', 'Named Ship 3', LARGE + 'SM_NPC_Aryana/SM_NPC_Aryana', 'boss', [8], 1300, TER_GLOW, bp=NPC + 'Aryana/BP_NPC_Ship_Aryana', name_from='bp'),
    # -- the Omen ------------------------------------------------------------------------------------------------------
    S('omen_drone', 'Omen Drone', NPC + 'OmenDrone/Art/SM_OmenDrone', 'fighter', [9], 160, OMEN_GLOW, bp=NPC + 'OmenDrone/BP_NPC_Ship_OmenDrone'),
    S('omen_bat_swarm', 'Omen Swarm', NPC + 'BatSwarm/Art/SM_BatSwarm', 'fighter', [9], 120, OMEN_GLOW, bp=NPC + 'BatSwarm/BP_NPC_Ship_BatSwarm'),
    S('omen_support', 'Omen Support', NPC + 'OmenSupport/Art/SK_OmenSupport_02', 'fighter', [9], 420, OMEN_GLOW, bp=NPC + 'OmenSupport/BP_NPC_Ship_OmenSupport'),
    S('omen_fortress', 'Omen Fortress', NPC + 'Fortress/Art/SM_JTU_Fortress_02_Merged', 'boss', [9], 2000, OMEN_GLOW, bp=NPC + 'Fortress/BP_NPC_Ship_Fortress'),
    S('omen_fortress_elite', 'Omen Elite Fortress', NPC + 'FortressElite/Art/SM_FortressElite_Merged', 'capital', [9], 5000, OMEN_GLOW,
      bp=NPC + 'FortressElite/BP_NPC_Ship_Fortress_Elite'),
    S('guilt', 'Omen Colossus', NPC + 'Guilt/Art/SK_Guilt', 'capital', [9], 8000, OMEN_GLOW, name_from='mesh'),
    # -- civilians: freighters -----------------------------------------------------------------------------------------
    # Chorus's civilian ship (BP_NPC_Ship_CivilianShip: SM_TG_Atlas_MK2_002 in M_TG_Atlas_01) and its variants' paint
    S('civilian_ship', 'Civilian Ship', ATLAS2 + 'SM_TG_Atlas_MK2_002', 'freighter', FREIGHT_RACES, 1500, TER_GLOW,
      bp=NPC + 'CivilianShip/BP_NPC_Ship_CivilianShip'),
    S('civilian_ship_blinkrace', 'Civilian Ship', ATLAS2 + 'SM_TG_Atlas_MK2_002', 'freighter', FREIGHT_RACES, 1500, TER_GLOW,
      bp=NPC + 'CivilianShip/BP_NPC_Ship_CivilianShip_Child_BlinkRace', name_from='variant', override={'M_TG_Atlas_01': ATLAS2 + 'M_TG_Atlas_02'}),
    S('civilian_ship_kirrim', 'Civilian Ship', ATLAS2 + 'SM_TG_Atlas_MK2_002', 'freighter', FREIGHT_RACES, 1500, TER_GLOW,
      bp=NPC + 'CivilianShip/BP_NPC_Ship_CivilianShip_Kirrim', name_from='variant', override={'M_TG_Atlas_01': ATLAS2 + 'M_TG_Atlas_03'}),
    S('civ_shuttle', 'Civilian Shuttle', [LARGE + 'Civilian_Ship_Small/SM_TER_CIV_Ship_Small01', LARGE + 'Civilian_Ship_Small/SM_TER_CIV_Ship_Small01_Emissives',
                                          LARGE + 'Civilian_Ship_Small/SM_TER_CIV_Ship_Small01_windows'], 'freighter', FREIGHT_RACES, 2000, TER_GLOW,
      bp=NPC + 'Civilian02/BP_NPC_Ship_Civilian02'),
    S('civ_transport', 'Civilian Transport', [LARGE + 'Civilian_Ship_Medium/SM_TER_CIV_Ship_Medium01', LARGE + 'Civilian_Ship_Medium/SM_TER_CIV_Ship_Medium01_Emissives',
                                              LARGE + 'Civilian_Ship_Medium/SM_TER_CIV_Ship_Medium01_windows'], 'freighter', FREIGHT_RACES, 3000, TER_GLOW),
    S('civ_liner', 'Civilian Liner', LARGE + 'Civilian_Ship_Large/SM_TER_CIV_Ship_Large01', 'freighter', FREIGHT_RACES, 4000, TER_GLOW),
    S('container_ship', 'Container Ship', [LARGE + 'Containership/SM_TER_ContainerShip01_ConfigA', LARGE + 'Containership/SM_TER_ContainerShip01_SetDressing01',
                                           LARGE + 'Containership/SM_TER_ContainerShip01_SetDressing01_Emissives'], 'freighter', FREIGHT_RACES, 4000, TER_GLOW,
      nose='+z'),
    # (the other Atlas hulls: no NPC blueprint flies them; named by their assets)
    S('atlas', 'Atlas', SMALL + 'TG_Atlas/SM_TG_Atlas', 'freighter', FREIGHT_RACES, 1300, TER_GLOW, name_from='mesh'),
    S('atlas_mk2', 'Atlas Mk II', ATLAS2 + 'SM_TG_Atlas_MK2', 'freighter', FREIGHT_RACES, 1500, TER_GLOW, name_from='mesh'),
    S('atlas_mk3', 'Atlas Mk III', SMALL + 'TG_Atlas_MK3/SM_TG_Atlas_MK3', 'freighter', FREIGHT_RACES, 1800, TER_GLOW, name_from='mesh'),
] + [S(f'hauler_{n:02d}', f'Hauler {n}', _civ(n, 'Large'), 'freighter', FREIGHT_RACES, 3000, TER_GLOW) for n in range(1, 11)] \
  + [S(f'courier_{n:02d}', f'Courier {n}', _civ(n, 'Small'), 'freighter', FREIGHT_RACES, 2000, TER_GLOW) for n in range(1, 7)] \
  + [S(f'traffic_drone_{n}', f'Traffic Drone {n}', SMALL + f'Trafficships/SM_TER_TrafficDrone_{n:03d}', 'freighter', FREIGHT_RACES, 600, TER_GLOW) for n in range(1, 6)] \
  + [S(f'cargo_runner_{n}', f'Cargo Runner {n}', SMALL + f'Trafficships/SM_TER_TrafficShipLarge_{n:03d}', 'freighter', FREIGHT_RACES, 1200, TER_GLOW) for n in range(1, 8)] \
  + [S(f'shuttle_{n}', f'Shuttle {n}', SMALL + f'Trafficships/SM_TER_TrafficShipSmall_{n:03d}', 'freighter', FREIGHT_RACES, 900, TER_GLOW) for n in range(1, 6)] \
  + [
    # -- capital ships ---------------------------------------------------------------------------------------------------
    S('dropship', 'Dropship', LARGE + 'Dropship/SM_TER_Dropship_Combined', 'capital', [8], 6000, CIRCLE_GLOW),
    S('frigate', 'Frigate', [LARGE + 'Frigate/SM_MERGED_TER_Frigate01', LARGE + 'Frigate/SM_MERGED_TER_Frigate01_SetDressingStationLights01',
                             LARGE + 'Frigate/SM_MERGED_TER_Frigate01_SetDressingWindows01'], 'capital', [0], 9000, TER_GLOW),
    S('frigate_mk2', 'Frigate Mk II', LARGE + 'Frigate/SM_TER_Frigate02_Merged', 'capital', [0], 9000, TER_GLOW),
    S('battleship', 'Battleship', [LARGE + f'Battleship/SM_TER_Battleship01_{c}' for c in 'ABCDEFG'], 'capital', [0], 14000, TER_GLOW,
      nose='+z'),
    # (the Resistance admiral's frigate, named by its asset)
    S('kardoh', 'Resistance Frigate', LARGE + 'SM_NPC_Kardoh/SM_NPC_Kardoh', 'capital', [0], 9000, TER_GLOW, name_from='mesh'),
    S('circle_warship', 'Circle Warship', LARGE + 'SM_SmallWarship/SM_SmallWarship', 'capital', [8], 9000, CIRCLE_GLOW),
    S('circle_destroyer', 'Circle Destroyer', LARGE + 'SM_MediumWarship/SM_MediumWarship', 'capital', [8], 12000, CIRCLE_GLOW),
    S('circle_dreadnought', 'Circle Dreadnought', LARGE + 'SM_LargeWarship/SM_LargeWarship', 'capital', [8], 16000, CIRCLE_GLOW),
    # (the warship the player takes over in the story: a Terran capital ship here)
    S('captured_warship', 'Captured Warship', PLAYER + 'PlayerControlledLargeShip/SM_PlayerControlledLargeShip01', 'capital', [0], 7000, TER_GLOW),
    # -- flown by the player -------------------------------------------------------------------------------------------
    S('forsaken_supercharged', 'Forsaken (Supercharged)', PLAYER + 'SuperchargedShip/SK_SuperChargedShip', 'player', [0], 640,
      [0.0, 0.61, 1.0], nose='+x'),   # (its glowing wing sheaths, "thruster" too, would turn it round)
]
EXPORTS = [m for s in SHIPS for m in s['meshes']]

# How a master material is drawn (the last of an instance's chain, tools/mi.py)
TRIM = {'M_NPCShipTrimMaster', 'M_TrimLayersMaster'}
PLATING, PANEL, FACELESS = {'M_PlatingMaster'}, {'M_SimpleMaster'}, {'M_JTU_Faceless'}
GLOWS = {'M_TER_SimpleWindows01': ('emissive_Color', 2.0, False), 'M_TER_StationLights_MASTER': ('Emissive_01_Color', 3.0, False),
         'M_RunningLights_Opaque': ('Color Emissive', 3.0, False), 'M_Thruster_Glow_Masked': ('StandingColor', 3.0, True),
         'M_ThrusterTraffic': ('StandingColor', 3.0, True), 'M_Warship_Thrusters': ('Color', 3.0, True),
         'M_Thruster_Master': (None, 3.0, True)}
FLAT = {'M_NPC_Trim_SavRee': ('Coat01 Tint 1', 0.6), 'M_NPC_Floater_Simple': ([0.3, 0.3, 0.32], 0.4),
        'MI_BatSwarm_Bone': ([0.05, 0.045, 0.045], 0.3), 'M_Guilt_Shell': ([0.04, 0.02, 0.02], 0.5)}
DROP = {'M_DecalMaster_Labels', 'M_DecalMaster_N', 'M_P_Boost_Edge_Argus', 'M_P_Glow_Engine', 'M_Warpin_Omen_Portal',
        'M_BlockoutGrid', 'M_MaskBlend_Placeholder'}


def _find_mi(export, mat):
    hits = glob.glob(os.path.join(export, '**', mat + '.json'), recursive=True)
    return (json.load(open(hits[0], encoding='utf-8')), os.path.dirname(hits[0])) if hits else (None, None)


_PNG = {}
def _png(export, name):
    if not name: return None
    if (export, name) not in _PNG:
        hits = glob.glob(os.path.join(export, '**', name + '.png'), recursive=True)
        _PNG[(export, name)] = hits[0] if hits else None
    return _PNG[(export, name)]


_IMG = {}
def _img(path, linear=False):
    key = (path, linear)
    if key not in _IMG:
        a = textures._load(path)
        _IMG[key] = np.concatenate([textures.srgb_to_linear(a[..., :3]), a[..., 3:]], -1) if linear else a
        if len(_IMG) > 16: _IMG.pop(next(iter(_IMG)))   # (a few 4K maps at most in memory)
    return _IMG[key]


_frames = glb.uv_frames


def _ortho(t, b, n):
    """Gram-Schmidt against the normal (b keeps its own side: mirrored UVs stay mirrored)."""
    def unit(v): return v / np.maximum(np.linalg.norm(v, axis=-1, keepdims=True), 1e-8)
    t = unit(t - n * (t * n).sum(-1, keepdims=True))
    b = b - n * (b * n).sum(-1, keepdims=True); b = unit(b - t * (t * b).sum(-1, keepdims=True))
    return t, b


def _merge(parts):
    """Several primitives' attributes (the keys they share) and indices as one mesh, and each triangle's part index."""
    keys = set.intersection(*(set(a) for a, _ in parts))
    attrs = {k: np.concatenate([np.asarray(a[k]) for a, _ in parts]) for k in keys}
    off, idx, part = 0, [], []
    for n, (a, i) in enumerate(parts):
        idx.append(np.asarray(i) + off); off += len(a['POSITION']); part.append(np.full(len(i) // 3, n, np.int32))
    return attrs, np.concatenate(idx), np.concatenate(part)


def _tangents(attrs, idx, uv_key):
    """Per-vertex glTF tangents (xyz, w = handedness) for the UV set uv_key: the triangles' dP/du summed per vertex,
    made orthogonal to the vertex normal; w from the side dP/dv lies on."""
    pos, nrm = np.asarray(attrs['POSITION'], np.float64), np.asarray(attrs['NORMAL'], np.float64)
    tris = np.asarray(idx).reshape(-1, 3)
    T, B = _frames(pos, np.asarray(attrs[uv_key], np.float64), tris)
    t, b = np.zeros_like(pos), np.zeros_like(pos)
    for k in range(3):
        np.add.at(t, tris[:, k], T); np.add.at(b, tris[:, k], B)
    t -= nrm * (t * nrm).sum(-1, keepdims=True)
    bad = np.linalg.norm(t, axis=-1) < 1e-10
    t[bad] = np.cross(nrm[bad], [0.0, 1.0, 0.0]) + 1e-6
    t /= np.linalg.norm(t, axis=-1, keepdims=True)
    w = np.where((np.cross(nrm, t) * -b).sum(-1) < 0, -1.0, 1.0)   # (glTF: the bitangent points toward -v, glb.tangent_signs)
    return np.concatenate([t, w[:, None]], -1).astype(np.float32)


# ---- the hull bake --------------------------------------------------------------------------------------------------
def _recipe(export, p, master):
    """What the bake samples for one material instance: {'kind', maps (paths), colours}, or None (not baked)."""
    png = lambda n: _png(export, p.texture(n))
    if master in TRIM:
        r = {'kind': 'trim', 'colors': png('LayerColors'), 'data': png('LayerData'), 'aro': png('Trim AAO'), 'normal': png('Trim Normal')}
        # (a blank white sheet masks nothing: MI_TER_NPC_Ship0x's would light the whole hull in its tint)
        if p.switch('Enable Trim Emissive') and p.switch('Use Trim Emissive as Masks') and png('Trim Emissive') \
                and 'blankwhite' not in p.texture('Trim Emissive').lower():
            r['emissive'] = png('Trim Emissive')
            r['tints'] = [p.vector(f'Trim Emissive {c} Channel Tint', [0, 0, 0]) for c in 'RGB']
            r['amount'] = p.scalar('Trim Emissive Amount', 1.0)
            r['uvshift'] = p.switch('Use UV shift to mask trim emissive')
        return r
    if master in PLATING:
        return {'kind': 'plating', 'colors': png('LayerColors'), 'data': png('LayerData'), 'albedo': png('Albedo'),
                'orm': png('ORM'), 'normal': png('Normal')}
    if master in PANEL:
        r = {'kind': 'panel', 'diffuse': png('BaseColor'), 'rmo': png('RMO'), 'normal': png('Normal')}
        if p.switch('Use Emissive') and png('Emissive'):
            r['emissive'] = png('Emissive'); r['amount'] = p.scalar('Emissive Amount', 1.0)
            r['tints'] = [p.vector(f'Emissive {c} Channel Color', [0, 0, 0]) for c in 'RGB']
        return r
    return None


def bake_hull(parts, size):
    """parts: [(attrs, idx, recipe)] of one source mesh (its UV set 2 a unique layout). -> (colour sRGB, metallic /
    smoothness RGBA, normal, emission linear or None), size x size float images."""
    attrs, idx, part = _merge([(a, i) for a, i, _ in parts])
    tris = np.asarray(idx).reshape(-1, 3)
    tri, bary = textures.rasterize(attrs['TEXCOORD_2'], idx, size)
    cov = tri >= 0; t = np.maximum(tri, 0); which = np.where(cov, part[t], -1)
    uv0 = textures.interpolate(attrs['TEXCOORD_0'], idx, tri, bary)
    swatch = attrs['TEXCOORD_3'][tris].mean(1) if 'TEXCOORD_3' in attrs else np.zeros((len(tris), 2), np.float32)
    colour = np.full(tri.shape + (3,), 0.5, np.float32); ao = np.ones(tri.shape, np.float32)
    rough = np.full(tri.shape, 0.5, np.float32); metal = np.zeros(tri.shape, np.float32)
    ts = np.zeros(tri.shape + (3,), np.float32); ts[..., 2] = 1; emit = np.zeros(tri.shape + (3,), np.float32)
    for n, (_, _, r) in enumerate(parts):
        m = which == n
        if not m.any(): continue
        u = uv0[m]
        if r['kind'] in ('trim', 'plating'):
            sw = swatch[t[m]]
            if r.get('colors'): colour[m] = textures.sample(_img(r['colors'], True), sw)[:, :3]
            if r.get('data'): metal[m] = textures.sample(_img(r['data']), sw)[:, 0]
        if r['kind'] == 'trim':
            if r.get('aro'):
                s = textures.sample(_img(r['aro']), u); ao[m] = s[:, 2]; rough[m] = s[:, 1]
            if r.get('emissive'):
                e = textures.sample(_img(r['emissive'], True), u)[:, :3] @ np.asarray(r['tints'], np.float32) * r['amount']
                if r.get('uvshift'): e *= (np.floor(u[:, 1:2]) != 0)   # (only the strips shifted out of the sheet's row)
                emit[m] = e
        elif r['kind'] == 'plating':
            if r.get('albedo'): colour[m] *= textures.sample(_img(r['albedo'], True), u)[:, :3]
            if r.get('orm'):
                s = textures.sample(_img(r['orm']), u); ao[m] = s[:, 0]; rough[m] = s[:, 1]; metal[m] = np.maximum(metal[m], s[:, 2])
        elif r['kind'] == 'panel':
            if r.get('diffuse'): colour[m] = textures.sample(_img(r['diffuse'], True), u)[:, :3]
            if r.get('rmo'):
                s = textures.sample(_img(r['rmo']), u); rough[m] = s[:, 0]; metal[m] = s[:, 1]; ao[m] = s[:, 2]
            if r.get('emissive'):
                emit[m] = textures.sample(_img(r['emissive']), u)[:, :3] @ np.asarray(r['tints'], np.float32) * r['amount']
        if r.get('normal'): ts[m] = textures.sample(_img(r['normal']), u)[:, :3] * 2 - 1   # (DirectX, kept)
    c = textures.linear_to_srgb(colour * (1.0 - textures.AO_STRENGTH * (1.0 - ao[..., None])))
    ms = np.stack([metal, metal, metal, 1.0 - rough], -1)
    n = textures.interpolate(attrs['NORMAL'], idx, tri, bary)
    n /= np.maximum(np.linalg.norm(n, axis=-1, keepdims=True), 1e-8)
    pos = np.asarray(attrs['POSITION'], np.float64)
    T0, B0 = _frames(pos, attrs['TEXCOORD_0'], tris); T2, B2 = _frames(pos, attrs['TEXCOORD_2'], tris)
    t0, b0 = _ortho(T0[t].astype(np.float32), B0[t].astype(np.float32), n)
    t2, b2 = _ortho(T2[t].astype(np.float32), B2[t].astype(np.float32), n)
    world = ts[..., :1] * t0 + ts[..., 1:2] * b0 + ts[..., 2:3] * n
    out = np.stack([(world * t2).sum(-1), (world * b2).sum(-1), (world * n).sum(-1)], -1)
    out /= np.maximum(np.linalg.norm(out, axis=-1, keepdims=True), 1e-8)
    out[~cov] = [0, 0, 1]
    e = textures.dilate(emit, cov) if emit.max() > 1e-3 else None
    return textures.dilate(c, cov), textures.dilate(ms, cov), textures.dilate(out * 0.5 + 0.5, cov), e


def bake_trim_hull(attrs, idx, maps, size=2048):
    """One M_NPCShipTrimMaster primitive baked over UV set 2 (bake_hull with a single part). maps: 'colors', 'data',
    'aro', 'normal'. -> (colour sRGB, metallic / smoothness RGBA, normal)."""
    c, ms, n, _ = bake_hull([(attrs, idx, dict(maps, kind='trim'))], size)
    return c, ms, n


def _layout(attrs, idx=None):
    """The UV set the hull bake draws over, its lightmap layout: UV set 2 when it lies in 0..1, else UV set 1 when that
    does (the support drone's), else UV set 2 rescaled from its bounds into 0..1 (the gunships' spill out to -1..2:
    a unique layout stays unique). -> uv array or None."""
    def inside(uv): return uv is not None and float(uv.min()) >= -0.01 and float(uv.max()) <= 1.01 and float(np.ptp(uv[:, 0])) > 0.05
    for key in ('TEXCOORD_2', 'TEXCOORD_1'):
        if inside(attrs.get(key)): return attrs[key]
    uv = attrs.get('TEXCOORD_2')
    if uv is None or float(np.ptp(uv[:, 0])) < 0.05: return None
    lo, hi = uv.min(0), uv.max(0)
    return ((uv - lo) / np.maximum(hi - lo, 1e-6) * 0.98 + 0.01).astype(np.float32)


def _unique_uv2(attrs):
    uv = attrs.get('TEXCOORD_2')
    return uv is not None and float(uv.min()) >= -0.01 and float(uv.max()) <= 1.01 and float(np.ptp(uv[:, 0])) > 0.05


# ---- materials --------------------------------------------------------------------------------------------------------
def _own(export, mod, stem, mat, mi, p, master, low):
    """A material drawn from its own maps (UV set 0)."""
    texnames = {v['ObjectName'].split("'")[1] for v in (mi or {}).get('Textures', {}).values()} | set((p.textures if p else {}).values())
    names = {'diffuse': _tex(mi or {}, 'Albedo', 'PM_Diffuse', 'Diffuse', 'BaseColor', 'B - D'),
             'normal': _tex(mi or {}, 'Normal', 'Normalmap', 'PM_Normals', 'B - N'),
             'rmo': _tex(mi or {}, 'RMO', 'RMAO', 'Metalness_Roughness_AO', 'Roughness_Metalic_AO', 'B - MRO', 'PM_SpecularMasks'),
             'emissive': _tex(mi or {}, 'Emissive', 'Emissive Masks', 'PM_Emissive')}
    if p:
        for key, keys in (('diffuse', ('Albedo', 'BaseColor', 'B - D')), ('normal', ('Normal', 'Normalmap', 'B - N')),
                          ('rmo', ('RMO', 'Metalness_Roughness_AO', 'Roughness_Metalic_AO', 'B - MRO', 'MRO')), ('emissive', ('Emissive Masks', 'Emissive'))):
            if not names.get(key) and p.texture(*keys): names[key] = p.texture(*keys)
    for t in texnames:
        for key, suf in (('diffuse', '_D'), ('normal', '_N'), ('rmo', '_RMO'), ('rmo', '_RMAO'), ('rmo', '_MRO'), ('emissive', '_E')):
            if not names.get(key) and t.endswith(suf) and 'dirt' not in t.lower(): names[key] = t
    rmo = names.get('rmo') or ''
    layout = 'MRO' if (p and (p.texture('Metalness_Roughness_AO') or p.texture('B - MRO', 'MRO'))) or rmo.endswith('_MRO') else 'RMO'
    if master == 'M_Phoenix':
        colours = _colours(p, force='thruster' in low)
    elif master and master.startswith('M_TG_Atlas_'):
        colours = [(0, [1, 0, 0], 1.0), (1, [0, 1, 0], 1.0), (2, [0, 0, 1], 1.0)]   # (its emissive map is a colour map)
    else:
        amount = p.scalar('Emissive Amount', 1.0) if p else 1.0
        colours = [(i, list(p.vector(k)), amount) for i, k in enumerate(('Emissive R Channel Color', 'Emissive G Channel Color', 'Emissive B Channel Color'))
                   if p and p.vector(k)] if (not p or p.switch('Use Emissive', True)) else []
    found = next((_png(export, names[k]) for k in ('diffuse', 'normal', 'rmo') if names.get(k) and _png(export, names[k])), None)
    if not found:
        return {'material': mat, 'color': [0.35, 0.35, 0.37], 'smoothness': 0.4}
    # (each map from wherever it was exported: the instance's folder, its parents' or a shared library)
    for key in ('diffuse', 'normal', 'rmo', 'emissive'):
        f = _png(export, names.get(key))
        if f and os.path.dirname(f) != os.path.dirname(found):
            names[key] = os.path.relpath(f, os.path.dirname(found))[:-4]
    entry = {'material': mat}
    entry.update(textures.convert_material(os.path.dirname(found), names, colours, os.path.join(mod, 'maps'), stem, size=1024, small=512, layout=layout))
    mask = _png(export, p.texture('Colormasks')) if p else None
    if mask and 'diffuse' in entry:
        # M_Terran_Hull's colour masks (the Atlas Mk II / III): red the primary hull, green the secondary, blue the metal,
        # each tinting the white albedo in its Colormask_Color_*
        out = os.path.join(mod, entry['diffuse'])
        c = textures._load(out)[..., :3]
        m = np.asarray(Image.open(mask).convert('RGB').resize(c.shape[1::-1], Image.BILINEAR), np.float32) / 255.0
        cols = np.asarray([p.vector(k, [1, 1, 1]) for k in ('Colormask_Color_Hull_Prim', 'Colormask_Color_Hull_Sec', 'Colormask_Color_Metal')], np.float32)
        tint = m @ cols + np.clip(1.0 - m.sum(-1, keepdims=True), 0, 1)
        textures._save(textures.linear_to_srgb(textures.srgb_to_linear(c) * tint), out, 0, 'RGB')
    return entry


def _faceless(export, mod, stem, mat, p):
    ao = p.texture('Ambient Occlusion'); nrm = p.texture('Normal'); thick = p.texture('Thickness Map')
    outer = p.vector('Outer Glow Color', [0.17, 0.0, 0.0]); inner = p.vector('Inner Glow Color', [3.0, 0.0, 0.08])
    core = p.vector('Inner Core Color') if p.switch('Enable Core') else None
    maps = os.path.join(mod, 'maps'); entry = {'material': mat}
    a = textures._load(_png(export, ao))[..., :1] if _png(export, ao) else None
    if a is not None:
        textures._save(textures.linear_to_srgb(a * np.asarray(outer, np.float32)[None, None, :]), os.path.join(maps, stem + '_c.png'), 1024, 'RGB')
        entry['diffuse'] = f'maps/{stem}_c.png'
    else:
        entry['color'] = outer
    if _png(export, nrm):
        textures._save(textures.flip_normal(textures._load(_png(export, nrm)))[..., :3], os.path.join(maps, stem + '_n.png'), 1024, 'RGB')
        entry['normal'] = f'maps/{stem}_n.png'
    glow = core or inner
    mask = textures._load(_png(export, thick))[..., :1] if (_png(export, thick) and not core) else a
    peak = float(max(max(glow), 1e-3))
    if mask is not None:
        mask = mask ** max(p.scalar('Inner Contrast', 1.0), 1.0)   # (the master's glow contrast)
        textures._save(textures.linear_to_srgb(mask * (np.asarray(glow, np.float32) / peak)[None, None, :]), os.path.join(maps, stem + '_e.png'), 1024, 'RGB')
        entry.update({'emission': f'maps/{stem}_e.png', 'emissionColor': [1, 1, 1], 'emissionIntensity': round(min(peak, 2.5), 3)})
    else:
        entry.update({'emissionColor': [v / peak for v in glow], 'emissionIntensity': round(min(peak, 2.5), 3)})
    return entry


def _norm(c):
    m = max(max(c), 1e-6)
    return [round(v / m, 3) for v in c]


def _convert(export, mod, sid, meshes, resolver=None, size=1024, override=None):
    """meshes: [prims] per source mesh; override: {material: pak path of the instance drawn in its place}. -> (the prims
    to save, ships.json materials)."""
    override = override or {}
    keep, mats, done = [], [], set()
    maps = os.path.join(mod, 'maps')
    for k, prims in enumerate(meshes):
        bake = []
        for mat, attrs, idx in prims:
            if mat in override:   # (a variant's paint: another instance in this material's place)
                path = override[mat]; mat = path.rsplit('/', 1)[1]; mi, mi_dir = None, None
            else:
                mi, mi_dir = _find_mi(export, mat)
                path = os.path.relpath(os.path.join(mi_dir, mat), export) if mi_dir else None
            low = mat.lower()
            p = _params(export, path, resolver) if path else None
            master = p.chain[-1] if p and p.chain else None
            if master in DROP or 'decal' in low or 'shieldwings' in low: continue
            r = _recipe(export, p, master) if p else None
            layout = _layout(attrs, idx) if r is not None and 'NORMAL' in attrs else None
            if layout is not None:
                bake.append((mat, dict(attrs, TEXCOORD_2=layout), idx, r)); continue
            stem = f'{sid}_{low}'
            if mat not in done:
                if master in GLOWS:
                    key, strength, engine = GLOWS[master]
                    col = (p.vector(key) if key else None) or p.vector('Color') or [1.0, 0.6, 0.3]
                    e = {'material': mat, 'color': [0.03, 0.03, 0.03], 'emissionColor': _norm(col), 'emissionIntensity': strength}
                    if engine: e.update({'engine': True, 'engineIdle': 0.25})
                    mats.append(e)
                elif master in FLAT:
                    c, sm = FLAT[master]
                    col = p.vector(c) if isinstance(c, str) else c
                    e = {'material': mat, 'color': list(col or [0.4, 0.4, 0.4]), 'smoothness': sm}
                    if master == 'M_Guilt_Shell' and p.vector('Emissive Color'):
                        e.update({'emissionColor': _norm(p.vector('Emissive Color')), 'emissionIntensity': 0.15})
                    mats.append(e)
                elif master in FACELESS:
                    mats.append(_faceless(export, mod, stem, mat, p))
                elif mi is not None or p is not None:
                    mats.append(_own(export, mod, stem, mat, mi, p, master, low))
                else:
                    mats.append({'material': mat, 'color': [0.35, 0.35, 0.37], 'smoothness': 0.45})
                done.add(mat)
            keep.append((mat, attrs, idx))
        if bake:
            name = f'{sid}_hull{k}'
            c, ms, n, e = bake_hull([(a, i, r) for _, a, i, r in bake], size)
            textures._save(c, os.path.join(maps, name + '_c.png'), 0, 'RGB')
            textures._save(ms, os.path.join(maps, name + '_ms.png'), min(size, 1024), 'RGBA')
            textures._save(textures.flip_normal(n), os.path.join(maps, name + '_n.png'), 0, 'RGB')
            entry = {'material': name, 'diffuse': f'maps/{name}_c.png', 'metallicSmoothness': f'maps/{name}_ms.png', 'normal': f'maps/{name}_n.png'}
            if e is not None:
                peak = float(e.max())
                textures._save(textures.linear_to_srgb(e / peak), os.path.join(maps, name + '_e.png'), min(size, 1024), 'RGB')
                entry.update({'emission': f'maps/{name}_e.png', 'emissionColor': [1, 1, 1], 'emissionIntensity': round(min(peak, 3.0), 3)})
            mats.append(entry)
            for _, a, i, _ in bake:   # the baked maps' layout, with tangents for it (the export's follow UV set 0)
                keep.append((name, dict(a, TEXCOORD_0=a['TEXCOORD_2'], TANGENT=_tangents(a, i, 'TEXCOORD_2')), i))
    return keep, mats


# ---- placing ----------------------------------------------------------------------------------------------------------
# (turns that bring the nose to +X: rotations about the up axis)
ROT = {'+x': lambda v: v, '-x': lambda v: v * np.array([-1, 1, -1], np.float32),
       '+z': lambda v: v[:, [2, 1, 0]] * np.array([1, 1, -1], np.float32), '-z': lambda v: v[:, [2, 1, 0]] * np.array([-1, 1, 1], np.float32)}


def _nose(prims):
    """Which way the hull points: away from its thruster glow, else Unreal's forward (+X)."""
    lo, hi = glb.bounds(prims); ctr = (lo + hi) / 2; ext = np.maximum(hi - lo, 1e-6)
    thr = [a['POSITION'] for m, a, _ in prims if 'thruster' in m.lower()]
    if thr:
        off = (np.concatenate(thr).mean(0) - ctr) / ext
        ax = 0 if abs(off[0]) >= abs(off[2]) else 2
        if abs(off[ax]) > 0.1: return ('-' if off[ax] > 0 else '+') + 'xyz'[ax]
    return '+x'


def _turn(prims, nose):
    f = ROT[nose]
    out = []
    for m, a, i in prims:
        a = dict(a)
        for k in ('POSITION', 'NORMAL'):
            if k in a: a[k] = f(np.asarray(a[k], np.float32)).astype(np.float32)
        if 'TANGENT' in a:
            t = np.asarray(a['TANGENT'], np.float32); a['TANGENT'] = np.concatenate([f(t[:, :3]), t[:, 3:]], 1).astype(np.float32)
        out.append((m, a, i))
    return out


def _humanize(asset, strip=('BP_NPC_Ship_', 'FinalBoss_', 'Child_', 'SM_', 'SK_', 'TG_', 'TF_', 'TER_', 'NPC_', 'JTU_')):
    """An asset's name as words: BP_NPC_Ship_PirateQueen -> Pirate Queen, SM_TG_Atlas_MK2 -> Atlas Mk II."""
    n = asset.rsplit('/', 1)[-1]
    changed = True
    while changed:
        changed = False
        for p in strip:
            if n.startswith(p): n = n[len(p):]; changed = True
    n = re.sub(r'_?MK(\d)', lambda m: '_Mk' + {'2': 'II', '3': 'III'}.get(m.group(1), m.group(1)), n)
    words = []
    for part in n.split('_'):
        words += re.findall(r'[A-Z]{2,}(?=[A-Z][a-z]|\d|$)|[A-Z]?[a-z]+|[A-Z]+|\d+', part)
    return ' '.join(w if not w.isupper() or len(w) <= 3 else w.capitalize() for w in words)


def _display(path):
    """A blueprint's display name (its "Enemy" text: the lock-on name), or None."""
    found = []
    def walk(o):
        if isinstance(o, dict):
            k, v = o.get('Key'), o.get('LocalizedString') or o.get('SourceString')
            if isinstance(k, str) and isinstance(v, str) and k.startswith('Enemy') and v.strip(): found.append((k, v.strip()))
            for x in o.values(): walk(x)
        elif isinstance(o, list):
            for x in o: walk(x)
    walk(json.load(open(path, encoding='utf-8')))
    found.sort(key=lambda kv: (not kv[0].endswith('.Name'), not kv[0].startswith('Enemy_')))
    return found[0][1] if found else None


def names(resolver, work):
    """{ship id: its name}: the NPC blueprint's display name (read from the pak at build time), else, for a character's
    ship, its asset's name; else this importer's own words (the table's)."""
    folder = os.path.join(work, 'bp'); os.makedirs(folder, exist_ok=True)
    bps = sorted({s['bp'] for s in SHIPS if s.get('bp')})
    todo = [b for b in bps if not os.path.exists(os.path.join(folder, b.rsplit('/', 1)[1] + '.json'))]
    if todo and resolver is not None:
        resolver.run('jsonall', '^(' + '|'.join(re.escape(b) for b in todo) + r')\.uasset$', folder, capture=True)
    out, source = {}, {}
    for s in SHIPS:
        f = os.path.join(folder, s['bp'].rsplit('/', 1)[1] + '.json') if s.get('bp') else None
        shown = _display(f) if f and os.path.exists(f) else None
        how, sid = s.get('name_from'), s['id']
        if shown: out[sid], source[sid] = shown, 'Chorus'
        elif how == 'bp' and s.get('bp'): out[sid], source[sid] = _humanize(s['bp']), 'asset'
        elif how == 'mesh': out[sid], source[sid] = _humanize(s['meshes'][0]), 'asset'
        elif how == 'variant' and s.get('bp'):
            out[sid], source[sid] = f"{s['name']} ({_humanize(s['bp'].rsplit('/', 1)[1].split('CivilianShip_', 1)[-1])})", 'asset'
        else: out[sid], source[sid] = s['name'], 'importer'
    # (for tools/sheet.py: where each name came from)
    json.dump(source, open(os.path.join(work, 'names.json'), 'w'), indent=1)
    return out


def material_paths(export):
    """The exported NPC hulls' material instances (pak paths, for mi.Resolver.prefetch)."""
    out = set()
    for s in SHIPS:
        for mesh in s['meshes']:
            src = os.path.join(export, mesh + '.glb')
            if not os.path.exists(src): continue
            for m, _, _ in glb.static_mesh(src, keep=('POSITION',)):
                _, d = _find_mi(export, m)
                if d: out.add(os.path.relpath(os.path.join(d, m), export))
        out |= set(s.get('override', {}).values())
    return sorted(out)


def texture_paths(resolver, export):
    """The pak paths of every texture the NPC hulls' instances use, their parents' included (to export the missing)."""
    out = set()
    for path in material_paths(export):
        out |= set(resolver.get(path).texture_paths.values())
    return sorted(out)


KEEP = ('POSITION', 'NORMAL', 'TANGENT', 'TEXCOORD_0', 'TEXCOORD_1', 'TEXCOORD_2', 'TEXCOORD_3')


def build(export, mod, resolver=None, only=None, work=None):
    """The NPC ships' models, maps and ships.json entries (those exported; only: a set of ids)."""
    os.makedirs(os.path.join(mod, 'models', 'npc'), exist_ok=True); os.makedirs(os.path.join(mod, 'maps'), exist_ok=True)
    _PNG.clear()   # (textures exported since the last call)
    shown = names(resolver, work or os.path.dirname(os.path.abspath(export)))
    out = []
    for s in SHIPS:
        sid = s['id']
        if only and sid not in only: continue
        srcs = [os.path.join(export, m + '.glb') for m in s['meshes']]
        if not os.path.exists(srcs[0]):
            print(f'  {sid}: not exported'); continue
        meshes = [glb.static_mesh(f, keep=KEEP) for f in srcs if os.path.exists(f)]
        nose = s.get('nose') or _nose(meshes[0])
        meshes = [_turn(m, nose) for m in meshes]
        lo, hi = glb.bounds([p for m in meshes for p in m])
        length_m = float(hi[0] - lo[0]) * SCALE
        role = s['role']
        if role == 'fighter' and length_m > MAX_TRAFFIC: role = 'boss'
        cap = {'boss': MAX_BOSS, 'capital': MAX_CAPITAL, 'freighter': MAX_CAPITAL}.get(role)
        shrink = min(1.0, cap / length_m) if cap else 1.0
        size = 2048 if length_m > 500 else 1024
        prims, mats = _convert(export, mod, sid, meshes, resolver, size, s.get('override'))
        name = shown.get(sid, s['name'])
        if not prims:
            print(f'  {sid}: nothing to draw'); continue
        glb.save(os.path.join(mod, 'models', 'npc', sid + '.glb'),
                 [(m, {k: v for k, v in a.items() if k not in ('TEXCOORD_1', 'TEXCOORD_2', 'TEXCOORD_3')}, i) for m, a, i in prims], sid)
        k = K * shrink   # game units per model metre (the hull scaled down past its cap)
        game = lambda v: [round(-float(v[2]) * k, 1), round(float(v[1]) * k, 1), round(float(v[0]) * k, 1)]
        mid_y = float(lo[1] + hi[1]) / 2
        half = float(min(hi[1] - lo[1], hi[2] - lo[2])) / 6
        mounts = [{'slotType': 0, 'position_engine': game([hi[0], mid_y, 0.0])},
                  {'slotType': 3, 'position_engine': game([lo[0], mid_y, 0.0]), 'turretAngles': [0.35, 0.35, 0.35],
                   'glowColor': s['glow'], 'glowSize': [round(half * k), round(half * k), 40]}]
        race = 9 if s['races'] == [9] else (8 if 8 in s['races'] else s['races'][0])
        if role == 'player':
            w = float(hi[2] - lo[2])
            mounts = [{'slotType': 0, 'position_engine': game([hi[0] * 0.4, mid_y, w * 0.25])},
                      {'slotType': 0, 'position_engine': game([hi[0] * 0.4, mid_y, -w * 0.25])},
                      {'slotType': 1, 'position_engine': game([hi[0] * 0.8, lo[1] * 0.5, 0.0])}, mounts[1]]
            e = {'id': sid, 'name': name, 'race': s['races'][0],
                 'description': "Nara's Forsaken from Chorus, supercharged: its wings sheathed in energy, faster and harder "
                                'hitting than the fighter it grew from.',
                 'armor': s['armor'], 'cargo': 35, 'handling': 170, 'price': 5600000, 'priceDefault': 0,
                 'slots': {'primary': 2, 'secondary': 1, 'turret': 0, 'equipment': 12},
                 'model': f'models/npc/{sid}.glb', 'icon': f'icons/{sid}.png', 'modelLength': round(length_m / 0.05), 'modelYaw': 90,
                 'hangarHeight': round(-float(lo[1]) * k + 20), 'engineGlowColor': s['glow'], 'mounts': mounts, 'materials': mats,
                 'lounge': {'systemRace': -1, 'minCampaign': 50, 'minRank': 14, 'chance': 3}, 'flightStyle': 'chorus'}
            print(f'  {sid}: player ship, {length_m:.0f} m, nose {nose}, {len(mats)} materials')
            out.append(e); continue
        if role == 'fighter':
            traffic = {'weight': s.get('weight', 1), 'races': s['races']}
            if s.get('traffic_role'): traffic['role'] = s['traffic_role']
        elif role == 'boss':
            traffic = {'boss': True}
        else:
            traffic = {'capital': 'freighter' if role == 'freighter' else 'battleship', 'weight': s.get('weight', 1)}
            if role == 'freighter': traffic['races'] = s['races']   # (every race's orbits)
        e = {'id': sid, 'name': name, 'description': f"A ship from Chorus: the {name}.", 'race': race,
             'armor': s['armor'], 'cargo': 20 if role == 'fighter' else 200, 'handling': 120 if s['armor'] < 300 else 90,
             'price': s['armor'] * 2500, 'priceDefault': 0,
             'slots': {'primary': 1, 'secondary': 1, 'turret': 0, 'equipment': 6},
             'model': f'models/npc/{sid}.glb', 'modelLength': round(length_m * shrink / 0.05), 'modelYaw': 90,
             'hangarHeight': round(-float(lo[1]) * k + 20), 'engineGlowColor': s['glow'], 'mounts': mounts, 'materials': mats,
             'traffic': traffic}
        if role in ('capital', 'freighter'): e['explosionScale'] = round(min(20.0, max(2.0, length_m * shrink / 150)), 1)
        print(f'  {sid} ({name}): {role}, {length_m * shrink:.0f} m{" (from %.0f)" % length_m if shrink < 1 else ""}, nose {nose}, {len(mats)} materials')
        out.append(e)
    return out
