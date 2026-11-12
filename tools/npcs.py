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
      (LayerColors, by UV set 3) times the tiling diffuse (UV set 1), its metalness the swatch's LayerData blue (plus the
      tiling RMO's), its roughness between LayerData red and green by the tiling RMO (TRIM_SHADER, from the compiled
      shader); the trim sheet (UV set 0) gives the ambient occlusion (Trim AAO blue) and normals; the trim emissive lights the strips whose UVs are
      shifted out of the sheet's row ("Use UV shift to mask trim emissive"), its channels in their tints
    M_PlatingMaster: the palette swatch times the plating's albedo (UV set 0), its ORM and normal map
    M_SimpleMaster (tech panels): their own maps over UV set 0; the emissive mask's channels in the channel colours
    The normals are carried from UV set 0's tangent frame into UV set 2's.
  windows: M_TER_SimpleWindows01 its pane atlas (each pane's brightness) lit in emissive_Color; M_WindowMaster its mask's
    glass lit in Tint 1 (the interior cube left out)
  flat glows: station lights (four channels by vertex colour; only black is read, the fourth channel: the Prophet's
    blue, the Circle warships' red; the rest the first), running lights (Color Emissive), thruster glows (StandingColor /
    Color, following the engines)
  their own maps: single-texture hulls (the Atlases' M_Terran_Hull: Metalness_Roughness_AO), the Omen bones, the Forsaken
    master's (M_Phoenix: the Elder ship); the Prophet's Omen crystal (M_JTU_Blend) with its red inner glow and specks
  a blueprint's material overrides by hand (the table's override): the Prophet's lights
  Omen tissue (M_JTU_Faceless, no colour map): the Outer Glow Color as the base colour times the ambient occlusion, and
    the Inner Glow Color glowing through the thin parts (the thickness map, to the power of its Inner Contrast); the cores
    (Enable Core) glow in the Inner Core Color (with the Chorus layers: the remake's "tissue" layer, the cores' term too)
  Sav's and Ree's hulls (M_NPC_Trim_SavRee): a layer per panel from an RGB index mask (UV set 3), the coat tiled and tinted
    in the instance's Coat01 tints, bare metal for blue; their floaters (M_NPC_Floater_Simple) a sheet over UV set 1
  decals (M_DecalMaster_Labels: hull numbers, labels, emblems): their sheet cut out by its alpha (alphaClip), one map per
    sheet shared by every ship; normal-only decals (M_DecalMaster_N) left out
  Guilt's shell (M_Guilt_Shell, masked): cut to its body-and-arms mask (T_Guilt_A), with its faint red glow
  the supercharged Forsaken's energy wings: an additive glow, the feather mask in its Main Color
  left out: normal-only decals, the thruster flames and other effect materials (Guilt's portal core)
"""
import glob, json, os, re
import numpy as np
from PIL import Image
from . import capital, glb, rig, textures, warships, wrecks
from .ships import K, SCALE, _tex, _params, _colours, nozzle_faces

UP = 'SpacePrototype/Content/UnleashedPrototype/'
SMALL, LARGE, NPC = UP + 'ArtAssets/Vehicles/Small/', UP + 'ArtAssets/Vehicles/Large/', UP + 'NPC/Ships/'
PLAYER = UP + 'ArtAssets/Vehicles/Playerships/'
OMEN_GLOW = [1.0, 0.1, 0.05]   # (the engine glow: the Omen's Inner Glow Color, dimmed)
CIRCLE_GLOW, PIRATE_GLOW, TER_GLOW = [1.0, 0.25, 0.1], [0.6, 0.8, 0.1], [0.05, 0.45, 1.0]
# (Chorus's freighters are human-built, "TER" in their files: they fly the Terran systems, the Chorus systems among them,
# and leave the Vossk, Nivelian and Midorian orbits to their own races' freighters)
FREIGHT_RACES = [0]
MAX_TRAFFIC, MAX_BOSS, MAX_CAPITAL = 150.0, 400.0, 4500.0   # metres (Modding/README)


def S(sid, name, meshes, role, races, armor, glow, **kw):
    """A ship: id, fallback name (this importer's own words; "bp" reads Chorus's from the pak), meshes, role, races, armour,
    engine glow; options: bp (its NPC blueprint: the display name), name_from ('bp' / 'mesh': a character's ship, named
    by its asset), override ({material: pak path}: a variant's materials), nose, weight, traffic_role, attach ({part mesh:
    [socket names]}: a blueprint's parts mounted on the first mesh's sockets), place ({part mesh: [(x, y, z) cm]}: a blueprint's parts
    at their components' offsets), scale (its blueprint's scale on the mesh). A blueprint's in-place parts (its thrusters,
    modelled where they sit) are simply further meshes; children inherit their parent blueprint's."""
    return dict(id=sid, name=name, meshes=[meshes] if isinstance(meshes, str) else meshes, role=role, races=races,
                armor=armor, glow=glow, **kw)


def _civ(n, kind):   # the numbered civilian traffic models
    return LARGE + f'Civilian_Ship_Traffic/SM_TER_CIV_Ship_Traffic_{kind}_{n:03d}'


ATLAS2 = SMALL + 'TG_Atlas_MK2/'
SHIPS = [
    # -- the Circle's and the pirates' fighters (their names: the blueprints' display names, read at build time) ----------
    S('circle_fighter', 'Circle Fighter', [SMALL + 'TF_terranfighter/TF_Fighter', SMALL + 'TF_terranfighter/SM_TF_Fighter_ThrusterCheap'], 'fighter', [8], 180, CIRCLE_GLOW, bp=NPC + 'Fighter/BP_NPC_Ship_Fighter'),
    S('circle_fighter_snipe', 'Circle Sniper', [SMALL + 'TF_terranfighter_02/SM_TF_terranfighter_02', SMALL + 'TF_terranfighter/SM_TF_Fighter_ThrusterCheap'], 'fighter', [8], 200, CIRCLE_GLOW,
      bp=NPC + 'FighterSnipe/BP_NPC_Ship_Fighter_Snipe', traffic_role='sniper'),
    S('circle_fighter_net', 'Circle Elite Fighter', [SMALL + 'TF_terranfighter_Elite/SM_TF_terranfighter_Elite', SMALL + 'TF_terranfighter/SM_TF_Fighter_ThrusterCheap'], 'fighter', [8], 240, CIRCLE_GLOW,
      bp=NPC + 'FighterNet/BP_NPC_Ship_Fighter_Net', traffic_role='webber'),
    S('student_fighter', 'Student Fighter', [SMALL + 'TF_Fighter_Student/TF_Fighter_Student', SMALL + 'TF_terranfighter/SM_TF_Fighter_ThrusterCheap'], 'fighter', [8], 150, CIRCLE_GLOW,
      bp=NPC + 'FactionStudent/BP_NPC_Ship_Fighter_Student'),
    S('circle_scout', 'Circle Scout', [SMALL + 'TS_Scout01/TS_Scout01', SMALL + 'TS_Scout01/SM_TS_Scout_ThrusterCheap'], 'fighter', [8], 140, CIRCLE_GLOW, bp=NPC + 'Scout/BP_NPC_Ship_Scout'),
    S('circle_support', 'Circle Support Ship', [SMALL + 'TS_SupportShip/SM_TS_Supportship', SMALL + 'TS_SupportShip/SM_TS_SupportShip_ThrusterCheap'], 'fighter', [8], 200, CIRCLE_GLOW,
      bp=NPC + 'SupportShip/BP_NPC_Ship_SupportShip', traffic_role='shieldCharger', scale=0.9),   # (its blueprint's 0.9)
    S('circle_support_drone', 'Circle Support Drone', SMALL + 'SupportDrone/SM_TER_SupportDrone', 'fighter', [8], 90, CIRCLE_GLOW),
    S('disruptor', 'Disruptor', UP + 'ArtAssets/Affordances/SM_TER_Disruptor/SM_TER_Disruptor', 'fighter', [8], 220, CIRCLE_GLOW,
      bp=NPC + 'Disruptor/BP_NPC_Ship_Disruptor', name_from='bp', traffic_role='jumpSuppressor', nose='+y'),
    S('pirate_fighter', 'Pirate Fighter', [SMALL + 'TF_Fighter_Pirate/TF_Fighter_Pirate', SMALL + 'TF_terranfighter/SM_TF_Fighter_ThrusterCheap'], 'fighter', [8], 170, PIRATE_GLOW,
      bp=NPC + 'Pirate/FighterPirate/BP_NPC_Ship_Fighter_Pirate'),
    S('pirate_scout', 'Pirate Scout', [SMALL + 'TS_Scout01_Pirate/TS_Scout01_Pirate', SMALL + 'TS_Scout01/SM_TS_Scout_ThrusterCheap'], 'fighter', [8], 130, PIRATE_GLOW,
      bp=NPC + 'Pirate/ScoutPirate/BP_NPC_Ship_ScoutPirate'),
    S('elder_ship', 'Elder Ship', NPC + 'Elder/Base/SM_NPC_Ship_Elder_Base', 'fighter', [0], 400, [0.0, 0.61, 1.0], weight=0.3),
    # (SM_TU_Ufo left out: an unfinished placeholder, its material slots empty and no material, texture or blueprint for it
    # anywhere in the pak, so Chorus never draws it and there is no look to rebuild)
    # -- gunships and the characters' ships: bosses --------------------------------------------------------------------
    S('circle_gunship', 'Circle Gunship', [SMALL + 'TG_Gunship/TG_gunship', SMALL + 'TG_Gunship/SM_TG_Gunship_ThrusterCheap'], 'boss', [8], 900, CIRCLE_GLOW, bp=NPC + 'Gunship/BP_NPC_Ship_Gunship',
      place={SMALL + 'TG_Gunship_Gunpod/SK_Gunship_Gunpod': [(590.0, 0.0, -460.0)]}),
    S('circle_gunship_apex', 'Circle Heavy Gunship', [SMALL + 'TG_Gunship_02/SM_TG_Gunship_02', SMALL + 'TG_Gunship/SM_TG_Gunship_ThrusterCheap'], 'boss', [8], 950, CIRCLE_GLOW, bp=NPC + 'Gunship2/BP_NPC_Ship_Gunship2',
      place={SMALL + 'TG_Gunship_Mine/SK_Gunship_MineThrower': [(590.0, 0.0, -1024.0)]}),
    S('circle_gunship_elite', 'Circle Elite Gunship', [SMALL + 'TG_Gunship_Elite/SM_TG_Gunship_Elite', SMALL + 'TG_Gunship/SM_TG_Gunship_ThrusterCheap'], 'boss', [8], 1100, CIRCLE_GLOW,
      bp=NPC + 'GunshipElite/BP_NPC_Ship_GunshipElite'),
    S('student_gunship', 'Student Gunship', SMALL + 'TG_Gunship_Elite_Cerene/SM_TG_Gunship_Elite_Cerene', 'boss', [8], 1200, CIRCLE_GLOW,
      bp=NPC + 'FactionStudent/BP_NPC_Ship_Cerene_Student', name_from='bp'),
    # (no blueprint flies this mesh, TG_terrangunship_MK2: "Terran" is only the files' tag; Chorus's gunships are its Vultures)
    S('terran_gunship', 'Vulture Mk II', SMALL + 'TG_terrangunship_MK2/SM_TS_terran_gunship2', 'boss', [8], 950, TER_GLOW),
    S('pirate_gunship', 'Pirate Gunship', [SMALL + 'TG_Gunship_Pirate/TG_Gunship_Pirate', SMALL + 'TG_Gunship/SM_TG_Gunship_ThrusterCheap'], 'boss', [8], 900, PIRATE_GLOW,
      bp=NPC + 'Pirate/GunshipPirate/BP_NPC_Ship_Gunship_Pirate'),
    S('pirate_queen', 'Pirate Leader', [SMALL + 'TF_Fighter_Sniper_Pirate/TF_Fighter_Sniper_Pirate', SMALL + 'TF_terranfighter/SM_TF_Fighter_ThrusterCheap'], 'boss', [8], 1200, PIRATE_GLOW,
      bp=NPC + 'Pirate/PirateQueen/BP_NPC_Ship_PirateQueen', name_from='bp'),
    S('prophet', 'Final Boss', [SMALL + 'SM_NPC_Prophet/SM_NPC_Prophet', SMALL + 'SM_NPC_Prophet/SM_NPC_Prophet_Thrusters'], 'boss', [8], 1500, CIRCLE_GLOW,
      # (its blueprint's four weapon pods, on the hull's weapon sockets)
      attach={SMALL + 'SM_NPC_Prophet/SM_NPC_Prophet_Weapon': ['WeaponBack_L', 'WeaponBack_R', 'WeaponFront_L', 'WeaponFront_R']},
      bp=NPC + 'FinalBoss/Prophet/BP_NPC_Ship_FinalBoss_Prophet', name_from='bp',
      # (its blueprint's override of the lights slot: the station lights in the Prophet's colours)
      override={'MI_TER_StationLights01': UP + 'ArtAssets/Environment/FactionMining/MI_TER_StationLights01_Porphet'}),
    S('sav', 'Named Ship 1', [LARGE + 'SM_Sav/SM_Sav', LARGE + 'SM_Sav/SM_Thrusters_Sav_Slim', LARGE + 'SM_Sav/SM_Thrusters_Sav_Wide'], 'boss', [8], 1000, TER_GLOW, bp=NPC + 'Sav/BP_NPC_Ship_Sav', name_from='bp'),
    S('ree', 'Named Ship 2', [LARGE + 'SM_Ree/SM_Ree', LARGE + 'SM_Ree/SM_Thrusters_Ree'], 'boss', [8], 1000, TER_GLOW, bp=NPC + 'Ree/BP_NPC_Ship_Ree', name_from='bp'),
    S('aryana', 'Named Ship 3', [LARGE + 'SM_NPC_Aryana/SM_NPC_Aryana', LARGE + 'SM_NPC_Aryana/SM_NPC_Thrusters_Aryana'], 'boss', [8], 1300, TER_GLOW, bp=NPC + 'Aryana/BP_NPC_Ship_Aryana', name_from='bp'),
    # -- the Omen ------------------------------------------------------------------------------------------------------
    S('omen_drone', 'Omen Drone', NPC + 'OmenDrone/Art/SM_OmenDrone', 'fighter', [9], 160, OMEN_GLOW, bp=NPC + 'OmenDrone/BP_NPC_Ship_OmenDrone'),
    S('omen_bat_swarm', 'Omen Swarm', NPC + 'BatSwarm/Art/SM_BatSwarm', 'fighter', [9], 120, OMEN_GLOW, bp=NPC + 'BatSwarm/BP_NPC_Ship_BatSwarm'),
    S('omen_support', 'Omen Support', NPC + 'OmenSupport/Art/SK_OmenSupport_02', 'fighter', [9], 420, OMEN_GLOW, bp=NPC + 'OmenSupport/BP_NPC_Ship_OmenSupport',
      idle=NPC + 'OmenSupport/Art/A_OmenSupport_Idle'),
    S('omen_fortress', 'Omen Fortress', NPC + 'Fortress/Art/SM_JTU_Fortress_02_Merged', 'boss', [9], 2000, OMEN_GLOW, bp=NPC + 'Fortress/BP_NPC_Ship_Fortress'),
    S('omen_fortress_elite', 'Omen Elite Fortress', NPC + 'FortressElite/Art/SM_FortressElite_Merged', 'capital', [9], 5000, OMEN_GLOW,
      bp=NPC + 'FortressElite/BP_NPC_Ship_Fortress_Elite'),
    # Guilt (SK_Guilt): in Chorus not a ship but an invincible Faceless that hunts Nara through the temples and tombs: the
    # remake's "pursuer" role (BT_Guilt's chase, its wither and screen), never in the traffic; npcships.json sends it now and
    # then into the Omen-haunted orbits (PURSUERS)
    S('guilt', 'Guilt', NPC + 'Guilt/Art/SK_Guilt', 'boss', [9], 3000, OMEN_GLOW, bp=NPC + 'Guilt/BP_NPC_Guilt', scale=0.17,
      idle=NPC + 'Guilt/Art/Anims/A_Guilt_Idle03', skinned=True, traffic=False, traffic_role='pursuer'),
    # -- civilians: freighters -----------------------------------------------------------------------------------------
    # Chorus's civilian ship (BP_NPC_Ship_CivilianShip: SM_TG_Atlas_MK2_002 in M_TG_Atlas_01) and its variants' paint
    S('civilian_ship', 'Civilian Ship', [ATLAS2 + 'SM_TG_Atlas_MK2_002', ATLAS2 + 'SM_NPC_Thrusters_CivilianShip'], 'freighter', FREIGHT_RACES, 1500, TER_GLOW,
      bp=NPC + 'CivilianShip/BP_NPC_Ship_CivilianShip'),
    S('civilian_ship_blinkrace', 'Civilian Ship', [ATLAS2 + 'SM_TG_Atlas_MK2_002', ATLAS2 + 'SM_NPC_Thrusters_CivilianShip'], 'freighter', FREIGHT_RACES, 1500, TER_GLOW,
      bp=NPC + 'CivilianShip/BP_NPC_Ship_CivilianShip_Child_BlinkRace', name_from='variant', override={'M_TG_Atlas_01': ATLAS2 + 'M_TG_Atlas_02'}),
    S('civilian_ship_kirrim', 'Civilian Ship', [ATLAS2 + 'SM_TG_Atlas_MK2_002', ATLAS2 + 'SM_NPC_Thrusters_CivilianShip'], 'freighter', FREIGHT_RACES, 1500, TER_GLOW,
      bp=NPC + 'CivilianShip/BP_NPC_Ship_CivilianShip_Kirrim', name_from='variant', override={'M_TG_Atlas_01': ATLAS2 + 'M_TG_Atlas_03'}),
    S('civ_shuttle', 'Civilian Shuttle', [LARGE + 'Civilian_Ship_Small/SM_TER_CIV_Ship_Small01', LARGE + 'Civilian_Ship_Small/SM_TER_CIV_Ship_Small01_Emissives',
                                          LARGE + 'Civilian_Ship_Small/SM_TER_CIV_Ship_Small01_windows', LARGE + 'Civilian_Ship_Small/SM_NPC_Thrusters_Civilian'], 'freighter', FREIGHT_RACES, 2000, TER_GLOW,
      bp=NPC + 'Civilian02/BP_NPC_Ship_Civilian02'),
    S('civ_transport', 'Civilian Transport', [LARGE + 'Civilian_Ship_Medium/SM_TER_CIV_Ship_Medium01', LARGE + 'Civilian_Ship_Medium/SM_TER_CIV_Ship_Medium01_Emissives',
                                              LARGE + 'Civilian_Ship_Medium/SM_TER_CIV_Ship_Medium01_windows', LARGE + 'Civilian_Ship_Medium/SM_Thrusters_ShipMedium'], 'freighter', FREIGHT_RACES, 3000, TER_GLOW),
    S('civ_liner', 'Civilian Liner', [LARGE + 'Civilian_Ship_Large/SM_TER_CIV_Ship_Large01', LARGE + 'Civilian_Ship_Large/SM_Thrusters_ShipLarge'], 'freighter', FREIGHT_RACES, 4000, TER_GLOW),
    S('container_ship', 'Container Ship', [LARGE + 'Containership/SM_TER_ContainerShip01_ConfigA', LARGE + 'Containership/SM_TER_ContainerShip01_SetDressing01',
                                           LARGE + 'Containership/SM_TER_ContainerShip01_SetDressing01_Emissives', LARGE + 'Containership/SM_ContainerShipThrusterCheap'], 'freighter', FREIGHT_RACES, 4000, TER_GLOW,
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
    S('circle_warship', 'Circle Warship', [LARGE + 'SM_SmallWarship/SM_SmallWarship', warships.CONFIGS['circle_warship'][2]], 'capital', [8], 9000, CIRCLE_GLOW),
    S('circle_destroyer', 'Circle Destroyer', [LARGE + 'SM_MediumWarship/SM_MediumWarship', warships.CONFIGS['circle_destroyer'][2]], 'capital', [8], 12000, CIRCLE_GLOW),
    S('circle_dreadnought', 'Circle Dreadnought', [LARGE + 'SM_LargeWarship/SM_LargeWarship', warships.CONFIGS['circle_dreadnought'][2]], 'capital', [8], 16000, CIRCLE_GLOW),
    # (the warship the player takes over in the story: a Terran capital ship here)
    S('captured_warship', 'Captured Warship', PLAYER + 'PlayerControlledLargeShip/SM_PlayerControlledLargeShip01', 'capital', [0], 7000, TER_GLOW),
    # -- the warships' parts (tools/warships.py): models for their subsystems, flown by no one ---------------------------
] + [S(pid, pname, mesh, 'prop', [-1], 1000, CIRCLE_GLOW, nose='+x') for pid, pname, mesh in warships.PROPS] + [
    # -- flown by the player -------------------------------------------------------------------------------------------
    S('forsaken_supercharged', 'Forsaken (Supercharged)', PLAYER + 'SuperchargedShip/SK_SuperChargedShip', 'player', [0], 640,
      [0.0, 0.61, 1.0], nose='+x', rig=True),   # (its glowing wing sheaths, "thruster" too, would turn it round; the Forsaken's skeleton: its drift)
]
EXPORTS = [m for s in SHIPS for m in s['meshes']] + [m for s in SHIPS for m in s.get('attach', {})] + [m for s in SHIPS for m in s.get('place', {})]

# Instances the mesh exports don't bring along (named differently in the mesh: "MI_" for the asset's "Mi_")
MATERIAL_PATHS = {'MI_SuperChargedShieldWings_Sheets': PLAYER + 'SuperchargedShip/Materials/Mi_SuperChargedShieldWings_Sheets'}

# How a master material is drawn (the last of an instance's chain, tools/mi.py)
TRIM = {'M_NPCShipTrimMaster', 'M_TrimLayersMaster'}
PLATING, PANEL, FACELESS = {'M_PlatingMaster'}, {'M_SimpleMaster'}, {'M_JTU_Faceless'}
GLOWS = {'M_TER_SimpleWindows01': ('emissive_Color', 2.0, False), 'M_TER_StationLights_MASTER': ('Emissive_01_Color', 3.0, False),
         'M_RunningLights_Opaque': ('Color Emissive', 3.0, False), 'M_Thruster_Glow_Masked': ('StandingColor', 3.0, True),
         'M_ThrusterTraffic': ('StandingColor', 3.0, True), 'M_Warship_Thrusters': ('Color', 3.0, True),
         'M_Thruster_Master': (None, 3.0, True)}
WINDOWS = {'M_TER_SimpleWindows01', 'M_WindowMaster'}   # (_windows)
FLAT = {}   # (master: (colour, smoothness): none left; the bat swarm's bone has its own maps, Guilt's shell _guilt_shell)
DROP = {'M_DecalMaster_N', 'M_P_Boost_Edge_Argus', 'M_P_Glow_Engine', 'M_Warpin_Omen_Portal',
        'M_BlockoutGrid', 'M_MaskBlend_Placeholder'}


def _find_mi(export, mat):
    hits = glob.glob(os.path.join(export, '**', mat + '.json'), recursive=True)
    if not hits:   # (a mesh may name its material in another case than the pak: MI_TER_PlatingTrim01_CIV_Ship_Small01)
        hits = [f for f in _jsons(export) if os.path.basename(f)[:-5].lower() == mat.lower()]
    # -> (its json, the pak path of the instance as the pak spells it), or (None, None)
    return (json.load(open(hits[0], encoding='utf-8')), os.path.relpath(hits[0], export)[:-5]) if hits else (None, None)


_JSONS = {}
def _jsons(export):
    if export not in _JSONS: _JSONS[export] = glob.glob(os.path.join(export, '**', '*.json'), recursive=True)
    return _JSONS[export]


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
# What the masters compute, from their compiled base-pass pixel shaders (`import.py`'s exporter `shaders` command on
# MI_TER_TechTrim03_Cult / MI_TER_PlatingTrim02_Cult, disassembled with d3dcompiler; the vertex shader confirms which UV
# set each interpolant carries):
#   TRIM_SHADER (M_TrimLayersMaster)  base colour = LayerColors(uv3) x Tiling Diffuse(uv1 x Base UV Tile Amount)
#                                     metallic    = saturate((LayerData.b - 0.5) x 2 + Tiling RMO.g)
#                                     roughness   = lerp(LayerData.r, LayerData.g, Tiling RMO.r)
#                                     occlusion   = Tiling RMO.b x lerp(1, Trim AAO.b(uv0), Trim AO Intensity)
#                                     (then the dirt layer, by the vertex colour's red: left out; no emissive in the
#                                     Cult's permutation)
#   PLATING_SHADER (M_PlatingMaster)  base colour = LayerColors(uv3) x Albedo; metallic = saturate((LayerData.b - 0.5) x 2
#                                     + ORM.b); roughness = lerp(LayerData.r, LayerData.g, ORM.g); occlusion = ORM.r
#   SAVREE_SHADER (M_NPC_Trim_SavRee) T_RGB_Mask (uv2): R bare metal, G Coat01 Tint 2, B Tint 3, black Tint 1; the coat (x the
#                                     tint x Base_Color_Add), metal and rust layers (D / ORM / N) tiled over uv1; T_Floater_01_EOA
#                                     (uv0): G rust, R bare metal over all that, B glow x Emissive Color x Emissive Multiplier
# So LayerData's blue is a metal flag (the off-white swatches of the Cult palette are bare, fairly glossy metal) and
# its red / green the roughness range. A metal swatch's colour on screen is mostly what it reflects: on the Prophet in
# its arena (a red glow overhead, dark fog around) the upward plates of its head show red and the V down its blade,
# facing the fog, black, while the grey paint on its sides and wing tops is lit pale. The remake's URP Lit hull
# reflects the system's sky the same way (Modding/README "Ship and station materials"), so the colours come from the
# same maps as in Chorus; only the surroundings differ.
DATA_METAL = 2


def _data_metal(data):
    """LayerData's metal flag as both masters read it: saturate((blue - 0.5) x 2)."""
    return np.clip((data[:, DATA_METAL] - 0.5) * 2.0, 0.0, 1.0)


def _recipe(export, p, master):
    """What the bake samples for one material instance: {'kind', maps (paths), colours}, or None (not baked)."""
    png = lambda n: _png(export, p.texture(n))
    if master in TRIM:
        r = {'kind': 'trim', 'colors': png('LayerColors'), 'data': png('LayerData'), 'aro': png('Trim AAO'), 'normal': png('Trim Normal'),
             # (the tiling layer over UV set 1 x Base UV Tile Amount: its diffuse tints the swatch, its RMO (or the
             # Uniform values without "Use RMO Texture") drives roughness, adds metal and carries the AO; TRIM_SHADER)
             'tdiff': png('Tiling Diffuse'), 'trmo': png('Tiling RMO') if p.switch('Use RMO Texture', True) else None,
             'tile': p.scalar('Base UV Tile Amount', 1.0), 'ao_amount': p.scalar('Trim AO Intensity', 1.0),
             'uniform': (p.scalar('Uniform Roughness', 0.5), p.scalar('Uniform Metallic', 0.0))}
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
    if master == 'M_NPC_Trim_SavRee':
        # Sav's and Ree's hulls (SAVREE_SHADER, their compiled base pass: MI_NPC_Trim_Sav): T_RGB_Mask over UV set 2 picks
        # the layer per texel: red bare metal, green the coat in Coat01 Tint 2, blue in Tint 3, black in Tint 1 (the coat x
        # Base_Color_Add); the coat, metal and rust layers each tiled over UV set 1; T_Floater_01_EOA over UV set 0 lays
        # rust (G) and bare metal (R) over that and glows (B, x Emissive Color x Emissive Multiplier).
        ref = lambda n: _png(export, p.texture('ref:' + n))
        return {'kind': 'layers', 'mask': ref('T_RGB_Mask'), 'eoa': ref('T_Floater_01_EOA'),
                'tints': [p.vector(f'Coat01 Tint {i}', [0.5, 0.5, 0.5]) for i in (1, 2, 3)],
                'add': p.vector('Base_Color_Add', [1, 1, 1]),
                'glow': [c * p.scalar('Emissive Multiplier', 1.0) for c in (p.vector('Emissive Color') or [0, 0, 0])[:3]],
                'coat': (ref('T_Coat_01_D'), ref('T_Coat_01_N'), ref('T_Coat_01_ORM'), p.scalar('Tiling_Coat_01', 2.0), p.scalar('Coat01Layer Roughness Bias', 0.0)),
                'metal': (ref('T_Metallic_01_D'), ref('T_Metallic_01_N'), ref('T_Metallic_01_ORM'), p.scalar('Tiling_Metallic_01', 4.0), p.scalar('MetallicLayer Roughness Bias', 0.0)),
                'rust': (ref('T_Rust_01_D'), ref('T_Rust_01_N'), ref('T_Rust_01_ORM'), p.scalar('Tiling_Rust_01', 1.0), 0.0)}
    if master in PANEL:
        r = {'kind': 'panel', 'diffuse': png('BaseColor'), 'rmo': png('RMO'), 'normal': png('Normal')}
        if p.switch('Use Emissive') and png('Emissive'):
            r['emissive'] = png('Emissive'); r['amount'] = p.scalar('Emissive Amount', 1.0)
            r['tints'] = [p.vector(f'Emissive {c} Channel Color', [0, 0, 0]) for c in 'RGB']
        return r
    return None


# ---- Chorus's layers in the remake (its GoF2/Hull ChorusLayers; Modding/README "chorus") -----------------------------------
# The trim and plating masters are drawn in the remake as Chorus draws them (TRIM_SHADER / PLATING_SHADER above) from their
# own maps over the hull's own UV sets, instead of a bake: a 2K bake over a 4 km warship's lightmap layout is metres a texel,
# and the trim sheet's panel lines, accent strips and lit windows went with it. The maps go once into maps/chorus/, shared
# by every ship that uses them.
CHORUS_LAYERS = True   # (import.py --bake-hulls: False, the bake for a remake without them)
CHORUS_TRIM_SIZE, CHORUS_TILING_SIZE, CHORUS_DIRT_SIZE = 2048, 1024, 512
CHORUS_EMISSION_PEAK = 3.0   # (the brightest glow at most this: Chorus's HDR colours x25 for its exposure, the remake's bloom)
CHORUS_KEEP = ('POSITION', 'NORMAL', 'TANGENT', 'TEXCOORD_0', 'TEXCOORD_1', 'TEXCOORD_2', 'TEXCOORD_3', 'COLOR_0')


def _chorus_map(mod, src, size, kind='colour'):
    """One of Chorus's maps into maps/chorus/ (once): kind 'colour' / 'data' as they are, 'normal' DirectX -> Unity (green
    flipped, blue rebuilt from the two channels the pak keeps). -> its path in the mod, or None."""
    if not src: return None
    name = os.path.splitext(os.path.basename(src))[0].lower()
    rel = f'maps/chorus/{name}.png'
    out = os.path.join(mod, rel)
    if not os.path.exists(out):
        os.makedirs(os.path.dirname(out), exist_ok=True)
        im = Image.open(src).convert('RGB')
        if im.size[0] > size: im = im.resize((size, size * im.size[1] // im.size[0]), Image.LANCZOS)
        if kind == 'normal':
            a = np.asarray(im, np.float32) / 255.0
            xy = a[..., :2] * 2.0 - 1.0
            z = np.sqrt(np.clip(1.0 - (xy ** 2).sum(-1), 0.0, 1.0))
            a = np.concatenate([a[..., :1], 1.0 - a[..., 1:2], z[..., None] * 0.5 + 0.5], -1)
            im = Image.fromarray((np.clip(a, 0, 1) * 255 + 0.5).astype(np.uint8), 'RGB')
        im.save(out, optimize=True)
    return rel


def _chorus_palette(mod, colors, data):
    """LayerColors (its colours made linear) and LayerData side by side, as the remake's ChorusLayers reads them by texel."""
    if not colors or not data: return None
    rel = f"maps/chorus/pal_{os.path.splitext(os.path.basename(colors))[0].lower()}.png"
    out = os.path.join(mod, rel)
    if not os.path.exists(out):
        os.makedirs(os.path.dirname(out), exist_ok=True)
        c = textures.srgb_to_linear(np.asarray(Image.open(colors).convert('RGB'), np.float32) / 255.0)
        d = np.asarray(Image.open(data).convert('RGB').resize((c.shape[1], c.shape[0]), Image.NEAREST), np.float32) / 255.0
        Image.fromarray((np.clip(np.concatenate([c, d], 1), 0, 1) * 255 + 0.5).astype(np.uint8), 'RGB').save(out, optimize=True)
    return rel


def _chorus(export, mod, p, master, r):
    """A trim / plating master's "chorus" block (TRIM_SHADER / PLATING_SHADER): its maps written, its values resolved through
    the instance's parents. The kicker's fade is in Chorus's centimetres here; build() turns it into the remake's units."""
    png = lambda n: _png(export, p.texture(n))
    plating = master in PLATING
    c = {'kind': 'plating' if plating else 'trim', 'palette': _chorus_palette(mod, r.get('colors'), r.get('data'))}
    if plating:
        c.update({'tilingDiffuse': _chorus_map(mod, png('Albedo'), CHORUS_TRIM_SIZE),
                  'tilingRmo': _chorus_map(mod, png('ORM'), CHORUS_TRIM_SIZE, 'data'),
                  'tilingNormal': _chorus_map(mod, png('Normal'), CHORUS_TRIM_SIZE, 'normal'),
                  'tiling': p.scalar('Tiling', 1.0)})
    else:
        npc = master == 'M_NPCShipTrimMaster'   # (its permutation: the accent, the far kicker and boost, no dirt)
        c.update({'tilingDiffuse': _chorus_map(mod, png('Tiling Diffuse'), CHORUS_TILING_SIZE),
                  'tilingRmo': _chorus_map(mod, png('Tiling RMO'), CHORUS_TILING_SIZE, 'data') if p.switch('Use RMO Texture', True) else None,
                  'tilingNormal': _chorus_map(mod, png('Tiling Normal'), CHORUS_TILING_SIZE, 'normal'),
                  'trimAo': _chorus_map(mod, png('Trim AAO'), CHORUS_TRIM_SIZE, 'data'),
                  'trimNormal': _chorus_map(mod, png('Trim Normal'), CHORUS_TRIM_SIZE, 'normal'),
                  'tiling': p.scalar('Base UV Tile Amount', 1.0), 'aoIntensity': p.scalar('Trim AO Intensity', 1.0)})
        if npc or p.switch('Enable Accent 1 (Wear)'):
            c.update({'accentColor': p.vector('Accent 1 Color', [0.72, 0.72, 0.72]), 'accentMetal': p.scalar('Accent 1 Metallic Override', 1.0),
                      'accentRoughness': p.scalar('Accent 1 Roughness Bias', 0.0),
                      'accentNormal': p.scalar('Accent 1 Tiling Base Normal Intensity', 1.0)})
        if png('Trim Emissive') and (npc or p.switch('Enable Trim Emissive')):
            tints = [p.vector(f'Trim Emissive {ch} Channel Tint', [0, 0, 0]) for ch in 'RGB']
            amount, near = p.scalar('Trim Emissive Amount', 1.0), 2.0 if npc else 1.0
            c.update({'trimEmissive': _chorus_map(mod, png('Trim Emissive'), CHORUS_TRIM_SIZE), 'emissiveR': tints[0], 'emissiveG': tints[1],
                      'emissiveB': tints[2], 'emissiveAmount': amount, 'nearEmission': near,
                      'emissiveUvShift': p.switch('Use UV shift to mask trim emissive', True)})
            peak = max(max(t) for t in tints) * amount * near
            if peak > CHORUS_EMISSION_PEAK: c['emissionScale'] = round(CHORUS_EMISSION_PEAK / peak, 4)
            if npc:
                c.update({'distanceBoost': p.scalar('Emissive Channel Distance Boost', 1.0), 'kickerColor': p.vector('Kicker Color', [1, 0, 0]),
                          'kickerExp': p.scalar('Kicker Exp', 5.0), 'kickerFadeOffset': p.scalar('Kicker Fade Offset', 15000.0),
                          'kickerFadeLength': p.scalar('Kicker Fade Length', 90000.0)})
    # (M_NPCShipTrimMaster's dirt permutation, the Disruptor's, decompiled: by the vertex alpha instead of the red, and over
    # the trim emissive; the fighters' instances compile without it, their Enable Dirt off)
    npc_dirt = master == 'M_NPCShipTrimMaster'
    if p.switch('Enable Dirt') and png('Dirt BaseColor'):
        c.update({'dirt': _chorus_map(mod, png('Dirt BaseColor'), CHORUS_DIRT_SIZE), 'dirtMask': _chorus_map(mod, png('Dirt Mask'), CHORUS_DIRT_SIZE, 'data'),
                  'dirtRoughness': _chorus_map(mod, png('Dirt Roughness'), CHORUS_DIRT_SIZE, 'data'), 'dirtTint': p.vector('Dirt Tint', [0.1, 0.1, 0.1]),
                  'dirtUvScale': p.scalar('Dirt UV Scale', 1.0), 'dirtMaskUvScale': p.scalar('Dirt Mask UV Scale', 0.5),
                  'dirtAo': p.scalar('Dirt from Material AO Intensity', 1.0), 'dirtContrast': p.scalar('Dirt Contrast', 0.0), 'dirtAlpha': plating,
                  'dirtByAlpha': npc_dirt, 'dirtOverEmissive': npc_dirt})
    return {k: (round(v, 5) if isinstance(v, float) else v) for k, v in c.items() if v is not None}


def bake_hull(parts, size):
    """parts: [(attrs, idx, recipe)] of one source mesh (its UV set 2 a unique layout). -> (colour sRGB, metallic /
    smoothness RGBA, normal, emission linear or None), size x size float images."""
    attrs, idx, part = _merge([(a, i) for a, i, _ in parts])
    tris = np.asarray(idx).reshape(-1, 3)
    tri, bary = textures.rasterize(attrs['TEXCOORD_2'], idx, size)
    cov = tri >= 0; t = np.maximum(tri, 0); which = np.where(cov, part[t], -1)
    uv0 = textures.interpolate(attrs['TEXCOORD_0'], idx, tri, bary)
    uv1 = textures.interpolate(attrs['TEXCOORD_1'], idx, tri, bary) if 'TEXCOORD_1' in attrs else uv0
    swatch = attrs['TEXCOORD_3'][tris].mean(1) if 'TEXCOORD_3' in attrs else np.zeros((len(tris), 2), np.float32)
    maskuv = textures.interpolate(attrs['MASKUV'], idx, tri, bary) if 'MASKUV' in attrs else uv0   # (the original UV set 2)
    frame1 = np.zeros(tri.shape, bool)   # (texels whose normals are in UV set 1's frame: the tiled layers)
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
            data = textures.sample(_img(r['data']), sw) if r.get('data') else None
            if data is not None: metal[m] = _data_metal(data)
        if r['kind'] == 'trim':
            # (TRIM_SHADER: the tiling layer over UV set 1, the trim sheet's occlusion over UV set 0)
            ut = uv1[m] * r.get('tile', 1.0)
            if r.get('tdiff'): colour[m] *= textures.sample(_img(r['tdiff'], True), ut)[:, :3]
            if r.get('trmo'):
                s = textures.sample(_img(r['trmo']), ut); rf, mg, occ = s[:, 0], s[:, 1], s[:, 2]
            else:
                ro, mu = r.get('uniform', (0.5, 0.0)); n_ = int(m.sum())
                rf, mg, occ = np.full(n_, ro, np.float32), np.full(n_, mu, np.float32), np.ones(n_, np.float32)
            metal[m] = np.clip(metal[m] + mg, 0, 1)
            rough[m] = data[:, 0] + (data[:, 1] - data[:, 0]) * rf if data is not None else rf
            ao[m] = occ
            if r.get('aro'):
                k_ = r.get('ao_amount', 1.0)
                ao[m] = occ * (1.0 + (textures.sample(_img(r['aro']), u)[:, 2] - 1.0) * k_)
            if r.get('emissive'):
                e = textures.sample(_img(r['emissive'], True), u)[:, :3] @ np.asarray(r['tints'], np.float32) * r['amount']
                # (the masters' UV-shift mask, as compiled: only faces whose palette UV (set 3) is shifted below 0)
                if r.get('uvshift'): e *= (swatch[t[m]][:, 1:2] < 0)
                emit[m] = e
        elif r['kind'] == 'plating':
            if r.get('albedo'): colour[m] *= textures.sample(_img(r['albedo'], True), u)[:, :3]
            if r.get('orm'):
                s = textures.sample(_img(r['orm']), u); ao[m] = s[:, 0]; rough[m] = s[:, 1]; metal[m] = np.clip(metal[m] + s[:, 2], 0, 1)
                if data is not None: rough[m] = data[:, 0] + (data[:, 1] - data[:, 0]) * s[:, 1]
        elif r['kind'] == 'layers':
            # (SAVREE_SHADER: the mask per texel over UV set 2, the tiled layers over UV set 1, the EOA sheet over UV set 0)
            n_ = int(m.sum()); u1 = uv1[m]
            mask = textures.sample(_img(r['mask']), maskuv[m])[:, :3] if r.get('mask') else np.zeros((n_, 3), np.float32)
            eoa = textures.sample(_img(r['eoa']), u)[:, :3] if r.get('eoa') else np.zeros((n_, 3), np.float32)
            def layer(spec, linear_colour=True):
                d, nm, orm, tiling, bias = spec; uu = u1 * tiling
                col = textures.sample(_img(d, True), uu)[:, :3] if d else np.full((n_, 3), 0.5, np.float32)
                o = textures.sample(_img(orm), uu)[:, :3] if orm else np.tile([1.0, 0.5, 0.0], (n_, 1)).astype(np.float32)
                nrm = textures.sample(_img(nm), uu)[:, :3] * 2 - 1 if nm else np.tile([0.0, 0.0, 1.0], (n_, 1)).astype(np.float32)
                return col, o[:, 0], np.clip(o[:, 1] + bias, 0, 1), o[:, 2], nrm
            cc, cao, cro, cme, cn = layer(r['coat']); mc, mao, mro, mme, mn = layer(r['metal']); rc, rao, rro, rme, rn = layer(r['rust'])
            t1, t2, t3 = (np.asarray(x, np.float32) for x in r['tints'])
            tint = t1 + (t2 - t1) * mask[:, 1:2]; tint = tint + (t3 - tint) * mask[:, 2:3]
            lerp = lambda a, b, f: a + (b - a) * (f[:, None] if a.ndim == 2 else f)
            mr, er, eg = mask[:, 0], eoa[:, 0], eoa[:, 1]
            col = lerp(cc * np.asarray(r.get('add', [1, 1, 1]), np.float32) * tint, mc, mr)
            col = np.clip(lerp(lerp(col, rc, eg), mc, er), 0, 1)
            me = np.clip(lerp(lerp(lerp(cme, mme, mr), rme, eg), mme, er), 0, 1)
            oc = np.clip(lerp(lerp(lerp(cao, mao, mr), rao, eg), mao, er), 0, 1)
            ro = np.clip(lerp(lerp(lerp(cro, mro, mr), rro, eg), mro, er), 0, 1)
            nn = lerp(lerp(lerp(cn, mn, mr), rn, eg), mn, er)
            colour[m], rough[m], metal[m], ao[m], ts[m] = col, ro, me, oc, nn
            frame1[m] = True
            if max(r.get('glow') or [0]) > 0: emit[m] = eoa[:, 2:3] * np.asarray(r['glow'], np.float32)
        elif r['kind'] == 'sheet':
            if r.get('diffuse'): colour[m] = textures.sample(_img(r['diffuse'], True), u)[:, :3]
            if r.get('orma'):
                s_ = textures.sample(_img(r['orma']), u); ao[m] = s_[:, 0]; rough[m] = s_[:, 1]; metal[m] = s_[:, 2]
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
    if frame1.any() and 'TEXCOORD_1' in attrs:
        T1, B1 = _frames(pos, attrs['TEXCOORD_1'], tris)
        t1_, b1_ = _ortho(T1[t].astype(np.float32), B1[t].astype(np.float32), n)
        t0 = np.where(frame1[..., None], t1_, t0); b0 = np.where(frame1[..., None], b1_, b0)
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
    uv = next((attrs[k] for k in ('TEXCOORD_2', 'TEXCOORD_1') if inside(attrs.get(k))), attrs.get('TEXCOORD_2'))
    if uv is None or float(np.ptp(uv[:, 0])) < 0.05: return None
    # stretched to fill the map (a lightmap often uses only part of 0..1: Sav's half of it); a unique layout stays unique
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


FACELESS_BREATH = 0.25   # (the breath curve's value at rest: CA_BaseVFX's row isn't exported; the master clamps to 0.5 - 1)


def _faceless(export, mod, stem, mat, p):
    """Omen tissue (M_JTU_Faceless). Its compiled base pass (the exporter's `shaders` on MI_JTU_Faceless_LowerFortress_Elite)
    writes a black base colour and no metal: the tissue is all glow, lerp(Outer Glow Color x (T_Dirt_02.b + Outer Variation),
    Inner Glow Color x (the scrolling Ice_Substance mask x the inverse fresnel + Inner Variation), saturate((Outer + Inner
    Variation) x saturate(1 / (Thickness.r x Strength)) + the breath curve) clamped to 0.5 - 1), the variations through a
    parallax offset of Thickness.r x Depth; roughness lerp(RoughnessIntensity, 0.05, Thickness.g). Baked here as seen head-on
    (no parallax, the fresnel term 0.96) with the breath at rest; the pulse, the scroll and the dissolve edge left out. The
    cores (Enable Core, another permutation) keep their glow through the thin parts (_faceless_core)."""
    if p.switch('Enable Core'): return _faceless_core(export, mod, stem, mat, p)
    tex = lambda n: _png(export, p.texture(n))
    maps = os.path.join(mod, 'maps'); n = 1024
    def load(path, ch, tile=1.0):
        if not path: return None
        a = np.asarray(Image.open(path).convert('RGB').resize((n, n), Image.BILINEAR), np.float32)[..., ch] / 255
        if tile != 1.0:   # (a tiled lookup over the same UVs: wrap the scaled coordinates)
            k = (np.arange(n) * tile).astype(int) % n
            a = a[np.ix_(k, k)]
        return a
    tile = p.scalar('NoiseTiling', 1.0)
    thick = load(tex('Thickness Map'), slice(0, 2), 1.0)
    ov = load(tex('Outer Variation'), 0); iv = load(tex('Inner Variation'), 0)
    dirt = load(_png(export, 'T_Dirt_02'), 2, tile); ice = load(_png(export, 'Ice_Substance_ColorMask-Crack-RoughnessBLend'), 0, tile)
    z = np.zeros((n, n), np.float32)
    ov, iv, dirt, ice = [x if x is not None else z for x in (ov, iv, dirt, ice)]
    r = thick[..., 0] if thick is not None else np.full((n, n), 0.5, np.float32)
    strength = p.scalar('Strength', 1.0)
    k = np.where(r * strength > 0, np.clip(1.0 / np.maximum(r * strength, 1e-6), 0, 1), 0.0)
    w = np.clip((ov + iv) * k + FACELESS_BREATH, 0.5, 1.0)[..., None]
    outer = np.asarray(p.vector('Outer Glow Color', [0.17, 0.0, 0.0])[:3], np.float32)
    inner = np.asarray(p.vector('Inner Glow Color', [3.0, 0.0, 0.08])[:3], np.float32)
    glow = (dirt + ov)[..., None] * outer * (1 - w) + (0.96 * ice + iv)[..., None] * inner * w
    peak = float(max(glow.max(), 1e-3))
    textures._save(textures.linear_to_srgb(glow / peak), os.path.join(maps, stem + '_e.png'), n, 'RGB')
    entry = {'material': mat, 'color': [0.0, 0.0, 0.0], 'metallic': 0.0, 'emission': f'maps/{stem}_e.png',
             'emissionColor': [1, 1, 1], 'emissionIntensity': round(min(peak, 2.5), 3)}
    if thick is not None:
        rough = np.clip(p.scalar('RoughnessIntensity', 1.0) + (0.05 - p.scalar('RoughnessIntensity', 1.0)) * thick[..., 1], 0, 1)
        entry['smoothness'] = round(float(1.0 - rough.mean()), 3)
    if tex('Normal'):
        textures._save(textures.flip_normal(textures._load(tex('Normal')))[..., :3], os.path.join(maps, stem + '_n.png'), n, 'RGB')
        entry['normal'] = f'maps/{stem}_n.png'
    return entry


def _faceless_core(export, mod, stem, mat, p):
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


def _energy_wings(export, mod, stem, mat, p):
    """The supercharged Forsaken's energy wings (M_SuperChargedShieldWings_Sheets, translucent): the remake's shimmer layer
    (additive, its pattern times a noise scrolling along it) over UV set 0: the feather mask's red (the feathers) in the
    Main Color and its green (their inner streaks) brighter, at the instance's Opacity, times the master's T_Soft_Noise.
    (Left out: the orange Accent Color.)"""
    mask = _png(export, p.texture('ref:T_FeatherSheetMask_M'))
    main = np.asarray(p.vector('Main Color', [0.9, 2.9, 7.0]), np.float32)
    peak = float(main.max()); col = main / max(peak, 1e-6)
    opacity = p.scalar('Opacity', 0.4)
    # (Chorus's colours are HDR for Unreal's exposure, the Main Color x7 at 37.5 %: as an intensity that whites out the blue,
    # so the glow is kept just under the remake's bloom, 1)
    e = {'material': mat, 'additive': True, 'ignoreVertexColors': True, 'emissionColor': [1, 1, 1],
         'emissionIntensity': round(min(peak * opacity * 0.35, 1.0), 3)}
    noise = _png(export, p.texture('ref:T_Soft_Noise'))
    if noise:   # the shimmer: the soft noise scrolling over the feathers (it halves their light on average: twice as bright)
        textures._save(textures._load(noise)[..., :3], os.path.join(mod, 'maps', stem + '_noise.png'), 512, 'RGB')
        e.update({'shimmer': True, 'flameNoise': f'maps/{stem}_noise.png', 'emissionIntensity': round(e['emissionIntensity'] * 2, 3)})
    if mask:
        m = textures._load(mask)
        glow = m[..., :1] * col[None, None, :] * 0.7 + m[..., 1:2] * (0.6 * col[None, None, :] + 0.4)
        glow = np.clip(glow, 0, 1)
        name = stem + '_e.png'
        textures._save(np.concatenate([textures.linear_to_srgb(glow), m[..., :1]], -1), os.path.join(mod, 'maps', name), 1024, 'RGBA')
        e['emission'] = f'maps/{name}'
    else:
        e['emissionColor'] = [round(float(v), 3) for v in col]
    return e


def _norm(c):
    m = max(max(c), 1e-6)
    return [round(v / m, 3) for v in c]


def _station_lights(p, attrs, idx):
    """M_TER_StationLights_MASTER, as its compiled pixel shader reads (the pak's shader library, disassembled): four
    channels, Emissive_0n_Color x Emissive_0n_Strength, picked per face by UV set 1: qx = ceil(u - 0.5), qy = ceil(v - 0.5),
    colour = lerp(lerp(c1, c2, qx), lerp(c4, c3, 1 - qx), qy) (u < .5, v < .5 the first; u >= .5 the second; v >= .5 the
    third and fourth; past 0..1 it extrapolates, as the shader does). -> [(quadrant tag, linear colour, face indices)]"""
    ch = [np.asarray((p.vector(f'Emissive_0{i}_Color') or [0, 0, 0])[:3], np.float32) * p.scalar(f'Emissive_0{i}_Strength', 5.0)
          for i in (1, 2, 3, 4)]
    tri = np.asarray(idx).reshape(-1, 3)
    uv = attrs['TEXCOORD_1'][tri].mean(1) if 'TEXCOORD_1' in attrs else np.zeros((len(tri), 2), np.float32)
    q = np.ceil(uv - 0.5).astype(int)
    out = []
    for qx, qy in sorted({tuple(x) for x in q}):
        sel = (q[:, 0] == qx) & (q[:, 1] == qy)
        lo = ch[0] + (ch[1] - ch[0]) * qx; hi = ch[3] + (ch[2] - ch[3]) * (1 - qx)
        col = np.maximum(lo + (hi - lo) * qy, 0)
        out.append((f'q{qx}{qy}'.replace('-', 'm'), [float(c) for c in col], tri[sel].reshape(-1).astype(np.uint32)))
    return out


def _jtu_blend(export, mod, stem, mat, mi, p, low):
    """Omen crystal (M_JTU_Blend: the Prophet's crown): two surfaces blended by vertex colour and mapped in world space,
    with red veins glowing beneath (the Inner Glow Color through a parallax heightmap) and emissive specks (B's mask
    x its Emissive Intensity). Here: the B surface's maps over UV set 0 (_own), and an emission map in the Inner Glow
    Color: a base glow, brighter through the veins' heightmap, plus the specks."""
    entry = _own(export, mod, stem, mat, mi, p, 'M_JTU_Blend', low)
    glow = _norm((p.vector('Inner Glow Color') or [1.0, 0.01, 0.01])[:3])
    veins, specks = _png(export, 'T_JantuVeins_H'), _png(export, 'T_JTU_Blend_02_A')
    n = 1024
    load = lambda f, c: np.asarray(Image.open(f).convert('RGB').resize((n, n), Image.BILINEAR), np.float32)[..., c] / 255
    h = load(veins, 2) if veins else np.full((n, n), 0.5, np.float32)
    s = load(specks, 1) if specks else np.zeros((n, n), np.float32)
    k = min(p.scalar('B - Emissive Intensity', 5.0), 5.0) / 5.0
    e = np.clip(0.35 + 0.4 * h + 2.0 * k * s, 0, 1)[..., None] * np.asarray(glow, np.float32)[None, None, :]
    textures._save(textures.linear_to_srgb(e), os.path.join(mod, 'maps', stem + '_e.png'), n, 'RGB')
    entry.update({'emission': f'maps/{stem}_e.png', 'emissionColor': [1, 1, 1], 'emissionIntensity': 1.5})
    return entry


def _breath_row(resolver, mod, row, mat, prefix='breath'):
    """A CA_BaseVFX row (the crystal's and the tissue's breath: R G B its curves; Guilt's core colours, prefix 'curve') as
    maps/chorus/<prefix>_<row>.png, 256 x 1."""
    from . import gate as _gate, planets as _planets
    try:
        rows = _planets._atlas_rows(resolver, _gate.VFX_ATLAS)
        a = _planets._curve_row(resolver, rows, row)
        rel = f'maps/chorus/{prefix}_{int(round(row))}.png'
        os.makedirs(os.path.join(mod, 'maps', 'chorus'), exist_ok=True)
        Image.fromarray(np.clip(np.round(np.asarray(a)[None] * 255), 0, 255).astype(np.uint8), 'RGBA').save(os.path.join(mod, rel))
        return rel
    except Exception as e:
        print(f'  {mat}: the {prefix} curve not baked ({e})')
        return None


def _chorus_file(export, mod, name, kind):
    """A Chorus map into maps/chorus/ (shared by every ship): 'colour' as it is, 'normal' Unreal's green flipped and z rebuilt
    (two-channel normal maps export it empty), 'data' as it is."""
    src = _png(export, name)
    if not src: return None
    rel = f'maps/chorus/{name.lower()}.png'
    dst = os.path.join(mod, rel)
    if not os.path.exists(dst):
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        a = textures._load(src)
        if kind == 'normal':
            n = textures.flip_normal(a)[..., :3]
            xy = n[..., :2] * 2 - 1
            n[..., 2] = (np.sqrt(np.clip(1 - (xy ** 2).sum(-1), 0, 1)) + 1) / 2
            textures._save(n, dst, 2048, 'RGB')
        else:
            textures._save(a[..., :3], dst, 2048, 'RGB')
    return rel


# ships whose tissue warps in (M_JTU_Faceless: Driver 0 -> 1, its Edge Thickness and Edge Glow Color), by ship id: the
# remake's ships.json "warpIn" (_convert records it, build writes it); its colour squeezed as the explosions' (8 / (8 + x))
WARP_IN = {}
WARP_SECONDS = 2.0   # (the Driver's run: its curve is in the warp-in blueprint's timeline, not read)


def _warp_in(p):
    col = p.vector('Edge Glow Color') if p else None
    if not col: return None
    c = np.array(col[:3], np.float64); peak = float(c.max())
    if peak <= 0: return None
    return {'seconds': WARP_SECONDS, 'edge': round(p.scalar('Edge Thickness', 0.02), 4),
            'color': [round(float(v), 4) for v in c * (8.0 / (8.0 + peak))]}


def _faceless_tissue(export, mod, mat, p, resolver):
    """Omen tissue (M_JTU_Faceless) drawn as its compiled base pass draws it, moving: the remake's Chorus layer "tissue"
    (GoF2/Hull's ChorusTissue): the ice mask scrolling, the breath rippling out from the origin, the variations through the
    thickness parallax, the inverse fresnel; its maps into maps/chorus/ (the hard-wired T_Dirt_02 and the ice mask too).
    With Enable Core (the Omen drones' and the bat swarms' cores, MI_JTU_OmenDroneCore's compiled base pass) its core too:
    Inner Core Color ^ Inner Contrast by N.V within the sphere (Sphere Offset, sphere radius), its colour held to the mod's
    glow peak (Chorus's 250 on the bat swarms: the remake's bloom)."""
    tex = lambda n: _chorus_file(export, mod, p.texture(n), 'data') if p.texture(n) else None
    c = {'kind': 'tissue', 'thickness': tex('Thickness Map'), 'outerVariation': tex('Outer Variation'),
         'innerVariation': tex('Inner Variation'), 'ao': tex('Ambient Occlusion'),
         'normal': _chorus_file(export, mod, p.texture('Normal'), 'normal') if p.texture('Normal') else None,
         'dirt': _chorus_file(export, mod, 'T_Dirt_02', 'data'),
         'ice': _chorus_file(export, mod, 'Ice_Substance_ColorMask-Crack-RoughnessBLend', 'data'),
         'outerGlow': list(p.vector('Outer Glow Color', [0.17, 0.0, 0.0]))[:3], 'innerGlow': list(p.vector('Inner Glow Color', [3.0, 0.0, 0.08]))[:3],
         'noiseTiling': p.scalar('NoiseTiling', 1.0), 'depth': p.scalar('Depth', 0.1), 'strength': p.scalar('Strength', 1.0),
         'roughnessIntensity': p.scalar('RoughnessIntensity', 1.0), 'breathInterval': p.scalar('Breath Interval', 0.0),
         'pulsePeriod': p.scalar('Pulse Wave Period UU', 4000000.0),
         'breath': _breath_row(resolver, mod, p.scalar('Breath Color Curve', 0.0), mat)}
    if not c['thickness']: return None
    peak = max(max(c['innerGlow']), max(c['outerGlow']))
    if peak > CHORUS_EMISSION_PEAK: c['emissionScale'] = round(CHORUS_EMISSION_PEAK / peak, 4)
    if p.switch('Enable Core') and p.vector('Inner Core Color'):
        core = [float(v) for v in list(p.vector('Inner Core Color'))[:3]]
        top = max(core) * c.get('emissionScale', 1.0)
        if top > CHORUS_EMISSION_PEAK: core = [v * CHORUS_EMISSION_PEAK / top for v in core]
        c.update({'coreColor': [round(v, 5) for v in core], 'coreContrast': p.scalar('Inner Contrast', 1.0),
                  'sphereOffset': [round(float(v), 3) for v in list(p.vector('Sphere Offset') or [0, 0, 0])[:3]],
                  'sphereRadius': p.scalar('sphere radius', 1000000.0)})
    c = {k: (round(v, 6) if isinstance(v, float) else v) for k, v in c.items() if v is not None}
    return {'material': mat, 'chorus': c}


def _jtu_crystal(export, mod, mat, p, resolver):
    """Omen crystal (M_JTU_Blend: the Prophet's crown) drawn as its compiled base pass draws it: the remake's Chorus layer
    "crystal" (its two world-mapped surfaces blended by the vertex colours, the veins' inner glow through a parallax
    heightmap, the breath rippling out from the origin; GoF2/Hull's ChorusCrystal). Its maps into maps/chorus/ (shared by
    every ship that uses them), the breath row baked from CA_BaseVFX."""
    from . import gate as _gate, planets as _planets
    out = os.path.join(mod, 'maps', 'chorus'); os.makedirs(out, exist_ok=True)
    def copy(param, kind):
        name = p.texture(param) if p else None
        src = _png(export, name)
        if not src: return None
        rel = f'maps/chorus/{name.lower()}.png'
        dst = os.path.join(mod, rel)
        if not os.path.exists(dst):
            a = textures._load(src)
            if kind == 'normal':   # (Unreal's green flipped; z rebuilt: the exports of two-channel normal maps leave it empty)
                n = textures.flip_normal(a)[..., :3]
                xy = n[..., :2] * 2 - 1
                n[..., 2] = (np.sqrt(np.clip(1 - (xy ** 2).sum(-1), 0, 1)) + 1) / 2
                textures._save(n, dst, 2048, 'RGB')
            elif kind == 'colour':
                textures._save(a[..., :3], dst, 2048, 'RGB')
            else:
                textures._save(a[..., :3], dst, 2048, 'RGB')
        return rel
    s_ = (lambda n, d: p.scalar(n, d)) if p else (lambda n, d: d)
    v_ = (lambda n, d: list((p.vector(n) or d))[:3]) if p else (lambda n, d: d)
    c = {'kind': 'crystal', 'diffuseA': copy('A - D', 'colour'), 'normalA': copy('A - N', 'normal'), 'mroA': copy('A - MRO', 'data'),
         'maskA': copy('A - EmissiveMask', 'data'), 'diffuseB': copy('B - D', 'colour'), 'normalB': copy('B - N', 'normal'),
         'mroB': copy('B - MRO', 'data'), 'maskB': copy('B - EmissiveMask', 'data'), 'heightmap': copy('Inner Heightmap', 'data'),
         'variation': copy('Inner Variation', 'data'),
         'scaleA': s_('A - Surface Textures World Scale', 25000.0), 'scaleB': s_('B - Surface Textures World Scale', 30000.0),
         'normalIntensityA': s_('A - NormalIntensity', 1.0), 'normalIntensityB': s_('B - NormalIntensity', 1.0),
         'roughnessBiasA': s_('A - Roughness Bias', 0.0), 'roughnessBiasB': s_('B - Roughness Bias', 0.0),
         'macroColor': v_('Macro Color', [0.0, 0.0, 0.0]), 'macroAmount': s_('Macro Color Amt', 1.0), 'macroTiling': s_('Macro Tiling Factor', 0.05),
         'macroRoughness': s_('Macro Roughness', 0.2), 'macroRoughnessAmount': s_('Macro Roughness Amt', 0.5),
         'innerGlow': v_('Inner Glow Color', [1.0, 0.05, 0.05]), 'glowA': s_('A - Emissive Intensity', 2.0),
         'glowPulseB': s_('B - Emissive Pulse Intensity', 1.0), 'glowB': s_('B - Emissive Intensity', 5.0),
         'innerRefraction': s_('Inner Refraction from Normal', 1.0), 'innerHeightRatio': s_('Inner HeightRatio', 0.37),
         'innerScale': s_('Inner Variation World Scale', 150000.0), 'noiseScale': s_('Noise World Scale', 50000.0),
         'noiseContrast': s_('Noise Contrast', 0.1), 'noiseOffset': s_('NoiseLeveOffset', 0.0),
         'breathInterval': s_('Breath Interval', 8.0), 'pulsePeriod': s_('Pulse Wave Period UU', 4000000.0),
         'breathAmount': s_('Breath Amount', 1.0), 'transitionSoftness': s_('VC Transition Softness', 0.44)}
    # the breath: its CA_BaseVFX row (R the glow, G the blend), 256 x 1
    c['breath'] = _breath_row(resolver, mod, s_('Breath Color Curve', 0.0), mat)
    peak = max(c['innerGlow']) * max(c['glowA'], c['glowPulseB'] * c['glowB'])
    if peak > CHORUS_EMISSION_PEAK: c['emissionScale'] = round(CHORUS_EMISSION_PEAK / peak, 4)
    c = {k: (round(v, 6) if isinstance(v, float) else v) for k, v in c.items() if v is not None}
    return {'material': mat + '__chorus', 'chorus': c}


def _decal(export, mod, mat, p):
    """Decals (M_DecalMaster_Labels: labels, hull numbers, hazard stripes, emblems on thin meshes over the hull, translucent
    in Chorus): the decal sheet with its alpha, cut out (alphaClip, Chorus's own mask clip value). One map per sheet,
    shared by every ship that uses it (maps/decal_<sheet>.png)."""
    sheet = p.texture('DecalSheet', 'PM_Diffuse') if p else None
    name = (sheet or '').rsplit('/', 1)[-1].split('.')[0]
    src = _png(export, name) if name else None
    if not src:
        return {'material': mat, 'color': [0.3, 0.3, 0.3], 'alphaClip': 0.5}
    out = f'maps/decal_{name.lower()}.png'
    if not os.path.exists(os.path.join(mod, out)):
        im = Image.open(src).convert('RGBA')
        if im.size[0] > 2048: im = im.resize((2048, 2048), Image.LANCZOS)
        im.save(os.path.join(mod, out), optimize=True)
    return {'material': mat, 'diffuse': out, 'alphaClip': 0.333, 'smoothness': round(1.0 - p.scalar('Roughness', 0.75), 3),
            'metallic': 0.0}


def _guilt_shell(export, mod, sid, mat, p, attrs, idx, unit=None):
    """Guilt's two shells (M_Guilt_Shell, masked, two-sided), after its compiled shaders (the base pass, the masked depth
    pass, the vertex shader; MI_Guilt_OuterShell_Small): a black (Base Color 0), half-metal body (Metallic / Roughness).
    The mask: ((T_Guilt_A.r + Arms Fade) x 0.5 + a screen dither - 0.5) x saturate(2 Coverage - (1 - n) x (1 -
    T_Guilt_A.g)^Erode Exponent) >= 1/3, n the obsidian rock's norm_spec_diff (its red) flowing over UV0 x Tiling along
    T_Guilt_Flow (RG), its phase FlowmapRandomness (Noise_01) at UV0 x Randomness Scale (the masked depth pass's five
    textures, in the master's referenced textures' order); the body T_Guilt_A's red, the arms its green: the inner shell
    (Coverage 0.42) near whole, the outer (0.17) a veil of wisps. Its normal the same norm_spec_diff's red and green at
    the flowed UVs. Its glow: (the obsidian rock's AO flowing the same way - Emissive Exponent) x Emissive Color x Emissive
    Intensity, x saturate(1 - distance from the centre / Center Emissive Radius)^2:
    the inner shell's red specks (Intensity 51.6), none on the outer (Exponent 20). The vertex shader pushes the shell out
    along its normals by Vertex Push + Vertex Strength B x (1 - n), world centimetres: the outer shell 3 - 9 m off the
    body. Baked here at rest (the flow at time 0, the dither at its mean); the flow, the dissolve's motion and the push's
    breathing left out. -> (ships.json entry, the primitive's attributes with the push applied)"""
    if unit is not None:
        # the remake's Chorus shell (GoF2/Hull ChorusShell) draws it moving, from these maps; lengths in the model's own
        # units (unit: model units per world metre: the skinned file keeps the mesh unscaled, 1 / the blueprint's 0.17)
        m_ = lambda n, k='data': _chorus_map(mod, _png(export, n), 1024, k)
        col = (p.vector('Emissive Color') or [1.0, 0.016, 0.016])[:3]
        peak = max(0.0, 1.0 - p.scalar('Emissive Exponent', 0.964)) * p.scalar('Emissive Intensity', 51.6) * max(col)
        c = {'kind': 'shell', 'mask': m_('T_Guilt_A'), 'noise': m_('asteroid_obsidian_rock_000_norm_spec_diff'),
             'flow': m_('T_Guilt_Flow'), 'phase': m_(p.texture('FlowmapRandomness') or 'Noise_01'),
             'glow': m_('asteroid_obsidian_rock_000_ao'),
             'tiling': p.scalar('Tiling', 8.0), 'randomness': p.scalar('Randomness Scale', 3.0), 'flowSpeed': p.scalar('FlowSpeed', 2.0),
             'flowStrength': p.scalar('Flow Map Strength', 3.0), 'armsFade': p.scalar('Arms Fade', 1.0), 'coverage': p.scalar('Coverage', 0.42),
             'erode': p.scalar('Erode Exponent', 1.0), 'masterAlpha': p.scalar('MasterAlpha', 1.0),
             'push': p.scalar('Vertex Push', 0.0) / 100.0 * unit, 'pushNoise': p.scalar('Vertex Strength B', 0.0) / 100.0 * unit,
             'baseColor': p.scalar('Base Color', 0.0), 'metal': p.scalar('Metallic', 0.5), 'roughness': p.scalar('Roughness', 0.5),
             'emissiveExponent': p.scalar('Emissive Exponent', 0.964), 'emissiveIntensity': p.scalar('Emissive Intensity', 51.6),
             'emissiveColor': list(col), 'centerRadius': p.scalar('Center Emissive Radius', 27430.0) / 100.0 * unit}
        if peak > CHORUS_EMISSION_PEAK: c['emissionScale'] = round(CHORUS_EMISSION_PEAK / peak, 4)
        return {'material': mat, 'doubleSided': True, 'chorus': {k: (round(v, 5) if isinstance(v, float) else v) for k, v in c.items()}}, attrs
    n_ = 1024
    A = _png(export, 'T_Guilt_A'); N = _png(export, 'asteroid_obsidian_rock_000_norm_spec_diff')
    G = _png(export, 'asteroid_obsidian_rock_000_ao')
    load = lambda f: np.asarray(Image.open(f).convert('RGB').resize((n_, n_), Image.BILINEAR), np.float32) / 255 if f else None
    a, noise, gl = load(A), load(N), load(G)
    tiling = p.scalar('Tiling', 8.0)
    uv = np.asarray(attrs['TEXCOORD_0'], np.float32)
    def tiled(img, u, k):   # (the image wrapped k times over the UVs)
        x = (np.mod(u[..., 0] * k, 1.0) * n_).astype(int) % n_; y = (np.mod(u[..., 1] * k, 1.0) * n_).astype(int) % n_
        return img[y, x]
    tri, bary = textures.rasterize(uv, idx, n_)
    cov = tri >= 0
    tuv = textures.interpolate(uv, idx, tri, bary)
    pos = textures.interpolate(np.asarray(attrs['POSITION'], np.float32), idx, tri, bary)
    A_ = a if a is not None else np.zeros((n_, n_, 3), np.float32)
    nz = tiled(noise, tuv, tiling)[..., 0] if noise is not None else np.full((n_, n_), 0.5, np.float32)
    erode = np.power(np.clip(1.0 - A_[..., 1], 1e-6, 1.0), p.scalar('Erode Exponent', 1.0))
    vis = ((A_[..., 0] + p.scalar('Arms Fade', 1.0)) * 0.5) * np.clip(2 * p.scalar('Coverage', 0.42) - (1 - nz) * erode, 0, 1) \
          - (1.0 - p.scalar('MasterAlpha', 1.0))
    alpha = np.clip(vis, 0, 1) * cov
    stem = f'{sid}_{mat.lower()}'
    rgba = np.zeros((n_, n_, 4), np.float32); rgba[..., 3] = alpha
    textures._save(textures.dilate(rgba, cov) if cov.any() else rgba, os.path.join(mod, 'maps', stem + '_c.png'), 0, 'RGBA')
    e = {'material': mat, 'diffuse': f'maps/{stem}_c.png', 'alphaClip': 0.333, 'doubleSided': True,
         'metallic': round(p.scalar('Metallic', 0.5), 3), 'smoothness': round(1.0 - p.scalar('Roughness', 0.5), 3)}
    ex, inten = p.scalar('Emissive Exponent', 0.964), p.scalar('Emissive Intensity', 51.6)
    if ex < 1.0 and inten > 0 and gl is not None:
        dist = np.linalg.norm(pos, axis=-1) * 100.0   # (world cm from the centre: the model is in Chorus's metres here)
        fall = np.clip(1.0 - dist / max(p.scalar('Center Emissive Radius', 27430.0), 1e-5), 0, 1) ** 2
        col = np.asarray((p.vector('Emissive Color') or [1.0, 0.016, 0.016])[:3], np.float32)
        glow = np.clip(tiled(gl, tuv, tiling) - ex, 0, None) * col * inten * fall[..., None] * cov[..., None]
        peak = float(glow.max())
        if peak > 1e-3:
            textures._save(textures.linear_to_srgb(textures.dilate(glow / peak, cov)), os.path.join(mod, 'maps', stem + '_e.png'), 0, 'RGB')
            e.update({'emission': f'maps/{stem}_e.png', 'emissionColor': [1, 1, 1], 'emissionIntensity': round(min(peak, 2.5), 3)})
    # the push, baked: out along the normals by Vertex Push + Vertex Strength B x (1 - n), centimetres -> metres
    push, strength = p.scalar('Vertex Push', 0.0), p.scalar('Vertex Strength B', 0.0)
    if (push or strength) and 'NORMAL' in attrs:
        nv = tiled(noise, uv, tiling)[..., 0] if noise is not None else np.full(len(uv), 0.5, np.float32)
        off = (push + strength * (1.0 - nv)) / 100.0
        attrs = dict(attrs, POSITION=(np.asarray(attrs['POSITION'], np.float32) + np.asarray(attrs['NORMAL'], np.float32) * off[:, None]).astype(np.float32))
    return e, attrs


def _guilt_core(export, mod, sid, mat, p, resolver=None):
    """Guilt's core (MP_Guilt_Core_Radial_02 on M_Warpin_Omen_Portal, its compiled translucent base pass): the remake's
    GoF2/ChorusPortal kind "core". About the card's middle its UVs pinched (use UV Pinch: Threads Pinch Max), in polar
    coordinates x (Tiling U, V), the Threads Texture read twice, panned by (Speed U, V) and (-Speed U, V); the core
    (1 - e^-(2.333 edge)^2)^Core Power x Core Mult; the colour the ColorCurve row of CA_BaseVFX (26, C_Omen_Warp) at threads
    + core; the alpha from the threads (^Threads Power x Threads Mult) and the core, x MasterAlpha, faded within Fade
    Distance of what is behind it. Its UV distortion (Strength 0 here) and CompAmount (the auto exposure's compensation)
    left out. The master's defaults where the instance doesn't set them."""
    s_ = p.scalar
    tex = _png(export, p.texture('Threads Texture') or 'T_Lu_Noise_17')
    stem = None
    if tex:
        stem = f'maps/{sid}_{mat.lower()}_threads.png'
        a = textures._load(tex)[..., :3]
        from . import planets as _planets
        if resolver is not None and _planets._srgb(resolver, getattr(p, 'texture_paths', {}).get(p.texture('Threads Texture') or 'T_Lu_Noise_17')):
            a = textures.srgb_to_linear(a)   # (the remake reads it as data: as Chorus samples it)
        textures._save(a, os.path.join(mod, stem), 512, 'RGB')
    row = s_('ColorCurve', 26.0)
    curve = _breath_row(resolver, mod, row, mat, 'curve') if resolver is not None else None
    if curve is None:
        # (no resolver: C_Omen_Warp's keys as read from the atlas: dark red where faint, hot pink-red, white at its brightest)
        keys = np.array([0.087, 0.391, 0.702, 1.0]); x = np.linspace(0, 1, 256)
        R, G, B = [0, 0.4, 1.0, 1.0], [0, 0, 0.2, 1.0], [0, 0.007, 0.213, 1.0]
        a = np.stack([np.interp(x, keys, ch) for ch in (R, G, B)] + [np.ones(256)], -1)
        curve = f'maps/chorus/curve_{int(round(row))}.png'
        os.makedirs(os.path.join(mod, 'maps', 'chorus'), exist_ok=True)
        Image.fromarray(np.clip(np.round(a[None] * 255), 0, 255).astype(np.uint8), 'RGBA').save(os.path.join(mod, curve))
    if not stem:
        return {'material': mat, 'additive': True, 'emissionColor': [1.0, 0.06, 0.03], 'emissionIntensity': 1.5}
    block = {'kind': 'core', 'noise': stem, 'curve': curve,
             'tilingU': s_('Tiling U', 1.0), 'tilingV': s_('Tiling V', 0.33), 'speedU': s_('Speed U', 0.05), 'panningV': s_('Speed V', 1.5),
             'pinch': s_('Threads Pinch Max', -1.6), 'corePower': s_('Core Power', 35.73694), 'coreMult': s_('Core Mult', 1.033816),
             'threadsPower': s_('Threads Power', 0.5), 'threadsMult': s_('Threads Mult', 5.0), 'masterAlpha': s_('MasterAlpha', 1.0),
             'depthFade': round(s_('Fade Distance', 10000.0) * K / 100.0, 3)}   # (cm to game units)
    return {'material': mat, 'portal': {k: (round(v, 5) if isinstance(v, float) else v) for k, v in block.items()}}


def _windows(export, mod, stem, mat, p, master):
    """Windows. M_TER_SimpleWindows01: an atlas of panes (T_TER_SimpleWindows01_D: each pane's brightness, some dim, the
    frames black) lit in emissive_Color x Emissive Power over UV set 0; the glass dark. M_WindowMaster (interior-cube
    windows): its mask's red the glass, lit in Tint 1 at its bright power (the interior cube and reflections left out);
    the rest a grey frame."""
    maps = os.path.join(mod, 'maps')
    if master == 'M_WindowMaster':
        src, col, power = _png(export, 'T_Windows01_M'), (p.vector('Tint 1') or [1.0, 0.707, 0.432]), p.scalar('EmissivePower Bright', 3.0)
    else:
        src, col, power = _png(export, 'T_TER_SimpleWindows01_D'), (p.vector('emissive_Color') or [1.0, 0.614, 0.315]), p.scalar('Emissive Power', 2.0)
    col = _norm(col[:3]); power = round(min(power, 2.5), 3)
    if not src:
        return {'material': mat, 'color': [0.03, 0.03, 0.03], 'emissionColor': col, 'emissionIntensity': power}
    a = np.asarray(Image.open(src).convert('RGB').resize((1024, 1024), Image.BILINEAR), np.float32)[..., :1] / 255
    textures._save(a * np.asarray(col, np.float32)[None, None, :], os.path.join(maps, stem + '_e.png'), 1024, 'RGB')
    frame = 0.25 if master == 'M_WindowMaster' else 0.03
    textures._save((frame * (1 - a) + 0.04 * a).repeat(3, -1), os.path.join(maps, stem + '_c.png'), 512, 'RGB')
    return {'material': mat, 'diffuse': f'maps/{stem}_c.png', 'smoothness': 0.85, 'emission': f'maps/{stem}_e.png',
            'emissionColor': [1, 1, 1], 'emissionIntensity': power}


def _convert(export, mod, sid, meshes, resolver=None, size=1024, override=None, unit=None):
    """meshes: [prims] per source mesh; override: {material: pak path of the instance drawn in its place}. -> (the prims
    to save, ships.json materials)."""
    override = override or {}
    keep, mats, done = [], [], set()
    maps = os.path.join(mod, 'maps')
    for k, prims in enumerate(meshes):
        bake = []
        for mat, attrs, idx in prims:
            colour = attrs.get('COLOR_0')   # (only Chorus's layers draw the vertex colours: their dirt)
            attrs = {k: v for k, v in attrs.items() if k != 'COLOR_0'}
            if mat in override:   # (a variant's paint: another instance in this material's place)
                path = override[mat]; mat = path.rsplit('/', 1)[1]; mi, mi_dir = None, None
            else:
                mi, path = _find_mi(export, mat)
                path = path or MATERIAL_PATHS.get(mat)
            low = mat.lower()
            p = _params(export, path, resolver) if path else None
            master = p.chain[-1] if p and p.chain else None
            if (master in DROP and not mat.startswith('MP_Guilt_Core')) or ('decal' in low and master != 'M_DecalMaster_Labels'): continue   # (normal-only decals)
            if master == 'M_SuperChargedShieldWings_Sheets' and p is not None:
                if mat not in done: mats.append(_energy_wings(export, mod, f'{sid}_{low}', mat, p))
                done.add(mat); keep.append((mat, attrs, idx)); continue
            if master == 'M_TER_StationLights_MASTER' and p is not None:
                # (one glow material per light colour: the master picks its channel per face, by UV set 1's quadrant)
                for q, col, sub in _station_lights(p, attrs, idx):
                    name = f'{mat}_{q}'
                    if name not in done:
                        peak = float(max(col))
                        e = {'material': name, 'color': [0.03, 0.03, 0.03]}
                        if peak > 1e-3: e.update({'emissionColor': _norm(col), 'emissionIntensity': round(min(peak * 0.3, 3.0), 3)})
                        mats.append(e); done.add(name)
                    keep.append((name, attrs, sub))
                continue
            if master == 'M_Guilt_Shell' and p is not None:   # (its push changes the geometry: _guilt_shell)
                e_, attrs = _guilt_shell(export, mod, sid, mat, p, attrs, idx, unit)
                if mat not in done: mats.append(e_); done.add(mat)
                keep.append((mat, attrs, idx)); continue
            if mat.startswith('MP_Guilt_Core') and p is not None:   # (GoF2/ChorusPortal's "core": its UVs, no vertex colours)
                if mat not in done: mats.append(_guilt_core(export, mod, sid, mat, p, resolver)); done.add(mat)
                keep.append((mat, attrs, idx)); continue
            r = _recipe(export, p, master) if p else None
            if master == 'M_JTU_Blend' and CHORUS_LAYERS and p is not None and resolver is not None:
                # (the crystal as its compiled base pass draws it: the remake's Chorus layer "crystal", with the vertex colours)
                name = mat + '__chorus'
                if name not in done:
                    mats.append(_jtu_crystal(export, mod, mat, p, resolver)); done.add(name)
                keep.append((name, dict(attrs, COLOR_0=colour) if colour is not None else attrs, idx)); continue
            if r is not None and CHORUS_LAYERS and r['kind'] in ('trim', 'plating') and r.get('colors') and r.get('data'):
                # drawn by the remake's Chorus layers over the hull's own UV sets (TRIM_SHADER), not baked
                name = mat + '__chorus'   # (the remake matches entries by "name contains": ..._Cult in ..._Cult_Emissive)
                if name not in done:
                    mats.append({'material': name, 'chorus': _chorus(export, mod, p, master, r)}); done.add(name)
                keep.append((name, dict(attrs, COLOR_0=colour) if colour is not None else attrs, idx)); continue
            if r is not None and CHORUS_LAYERS and r['kind'] == 'panel':
                r = None   # (the tech panels: their own maps over UV set 0, full size, as the master draws them)
            layout = _layout(attrs, idx) if r is not None and 'NORMAL' in attrs else None
            if layout is not None:
                a2 = dict(attrs, TEXCOORD_2=layout, MASKUV=attrs.get('TEXCOORD_2', layout))   # (the mask's own UV set 2)
                if r.get('uv') and r['uv'] in attrs: a2['TEXCOORD_0'] = attrs[r['uv']]   # (the floater sheet: UV set 1)
                bake.append((mat, a2, idx, r)); continue
            stem = f'{sid}_{low}'
            if mat not in done:
                if master in WINDOWS:
                    mats.append(_windows(export, mod, stem, mat, p, master))
                elif master == 'M_JTU_Blend':
                    mats.append(_jtu_blend(export, mod, stem, mat, mi, p, low))
                elif master in GLOWS:
                    key, strength, engine = GLOWS[master]
                    col = (p.vector(key) if key else None) or p.vector('Color') or [1.0, 0.6, 0.3]
                    e = {'material': mat, 'color': [0.03, 0.03, 0.03], 'emissionColor': _norm(col), 'emissionIntensity': strength}
                    if engine: e.update({'engine': True, 'engineIdle': 0.25})
                    mats.append(e)
                elif master == 'M_DecalMaster_Labels':
                    mats.append(_decal(export, mod, mat, p))
                elif master in FLAT:
                    c, sm = FLAT[master]
                    col = p.vector(c) if isinstance(c, str) else c
                    e = {'material': mat, 'color': list(col or [0.4, 0.4, 0.4]), 'smoothness': sm}
                    if master == 'M_Guilt_Shell' and p.vector('Emissive Color'):
                        e.update({'emissionColor': _norm(p.vector('Emissive Color')), 'emissionIntensity': 0.15})
                    mats.append(e)
                elif master in FACELESS:
                    # (moving, as its compiled base pass draws it: the remake's Chorus layer "tissue", the cores too; builds
                    # without the layers: the bake)
                    t_ = _faceless_tissue(export, mod, mat, p, resolver) if CHORUS_LAYERS and resolver is not None else None
                    mats.append(t_ or _faceless(export, mod, stem, mat, p))
                    if p is not None and sid not in WARP_IN and _warp_in(p): WARP_IN[sid] = _warp_in(p)
                elif master == 'M_NPC_Floater_Simple' and p is not None:
                    # Sav's and Ree's floater panels: one sheet (colour, normal, ORMA: R occlusion, G roughness, B
                    # metal) over UV set 1, which becomes their UV
                    names = {'diffuse': p.texture('ref:T_Floater_01_D'), 'normal': p.texture('ref:T_Floater_01_N'), 'rmo': p.texture('ref:T_Floater_01_ORMA')}
                    found = _png(export, names['diffuse'])
                    e = {'material': mat}
                    if found:
                        e.update(textures.convert_material(os.path.dirname(found), names, [], maps, stem, size=1024, small=512, layout='ORM'))
                    else:
                        e['color'] = [0.3, 0.3, 0.32]
                    mats.append(e)
                elif mi is not None or p is not None:
                    mats.append(_own(export, mod, stem, mat, mi, p, master, low))
                else:
                    mats.append({'material': mat, 'color': [0.35, 0.35, 0.37], 'smoothness': 0.45})
                done.add(mat)
            if master == 'M_NPC_Floater_Simple' and 'TEXCOORD_1' in attrs and 'NORMAL' in attrs:
                attrs = dict(attrs, TEXCOORD_0=attrs['TEXCOORD_1'], TANGENT=_tangents(attrs, idx, 'TEXCOORD_1'))
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


def _uniform(prims):
    """The primitives with the same attributes (CHORUS_KEEP): missing UV sets zero, missing vertex colours white."""
    out = []
    for m, a, i in prims:
        a = dict(a); n = len(a['POSITION'])
        for key in CHORUS_KEEP[3:7]:
            if key not in a: a[key] = np.zeros((n, 2), np.float32)
        if 'COLOR_0' not in a: a['COLOR_0'] = np.ones((n, 4), np.float32)
        if 'TANGENT' not in a: a['TANGENT'] = np.tile(np.array([1, 0, 0, 1], np.float32), (n, 1))
        out.append((m, a, i))
    return out


# ---- placing ----------------------------------------------------------------------------------------------------------
# (turns that bring the nose to +X: rotations about the up axis)
ROT = {'+x': lambda v: v, '-x': lambda v: v * np.array([-1, 1, -1], np.float32),
       '+z': lambda v: v[:, [2, 1, 0]] * np.array([1, 1, -1], np.float32), '-z': lambda v: v[:, [2, 1, 0]] * np.array([-1, 1, 1], np.float32),
       # (modelled pointing up: the blueprint pitches it -90, so its top is the nose; up -> forward, forward -> down)
       '+y': lambda v: v[:, [1, 0, 2]] * np.array([1, -1, 1], np.float32)}


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
                _, path = _find_mi(export, m)
                if path: out.add(path)
        out |= set(s.get('override', {}).values())
    out |= set(MATERIAL_PATHS.values())
    return sorted(out)


def texture_paths(resolver, export):
    """The pak paths of every texture the NPC hulls' instances use, their parents' included (to export the missing)."""
    out = set()
    for path in material_paths(export):
        out |= set(resolver.get(path).texture_paths.values())
    return sorted(out)


KEEP = ('POSITION', 'NORMAL', 'TANGENT', 'TEXCOORD_0', 'TEXCOORD_1', 'TEXCOORD_2', 'TEXCOORD_3', 'COLOR_0')

# ---- mounts ------------------------------------------------------------------------------------------------------------
MAX_TURRETS, MAX_EXHAUSTS = 8, 8   # (a capital ship's hardpoints carry at most 8 turrets in multiplayer copies)
MOD_ID = 'chorus_ships'
# which of Chorus's turrets (tools/turrets.py) a capital ship or boss carries on its turret mounts, in turn: the Circle's
# warships heavy and missile turrets (the dreadnought its sniper too), the captured warship heavy and light ones, the rest
# the light one
CHORUS_TURRETS = {'circle_warship': ['chorus_turret_heavy', 'chorus_turret_missile'],
                  'circle_destroyer': ['chorus_turret_heavy', 'chorus_turret_missile'],
                  'circle_dreadnought': ['chorus_turret_heavy', 'chorus_turret_sniper', 'chorus_turret_missile'],
                  'captured_warship': ['chorus_turret_heavy', 'chorus_turret_light'],
                  'dropship': ['chorus_turret_light', 'chorus_turret_mine']}
CHORUS_TURRETS_DEFAULT = ['chorus_turret_light']
TURRET = {1: 49}                   # npcTurrets by race: the Vossk L'ksaar; the others the Hammerhead D2A2 (48), as the GoF3 importer
TURRET_SOCKETS = re.compile(r'(?i)artillery|turret|npcattack')
THRUSTER_SOCKETS = re.compile(r'(?i)^thruster')
DAMAGE_SOCKETS = re.compile(r'(?i)^vfx_dt')


def _socket(work, mesh, name):
    """(Unreal location in cm, rotation matrix) of the static mesh socket 'name' (<work>/sockets, read by sockets()), or
    None."""
    f = os.path.join(work, 'sockets', mesh.rsplit('/', 1)[1] + '.json')
    if not os.path.exists(f): return None
    for e in json.load(open(f, encoding='utf-8')):
        pr = e.get('Properties', {}) if isinstance(e, dict) else {}
        if e.get('Type') != 'StaticMeshSocket' or pr.get('SocketName') != name: continue
        loc, rot = pr.get('RelativeLocation', {}), pr.get('RelativeRotation', {})
        sc = pr.get('RelativeScale') or {}
        return (np.array([loc.get(k, 0.0) for k in 'XYZ'], np.float32),
                _rotator(rot.get('Pitch', 0.0), rot.get('Yaw', 0.0), rot.get('Roll', 0.0)),
                np.array([sc.get(k, 1.0) for k in 'XYZ'], np.float32))
    return None


def _rotator(pitch, yaw, roll):
    """Unreal's FRotationMatrix (row vectors: v' = v @ M) of a rotator in degrees."""
    p, y, r = np.radians([pitch, yaw, roll])
    sp, cp, sy, cy, sr, cr = np.sin(p), np.cos(p), np.sin(y), np.cos(y), np.sin(r), np.cos(r)
    return np.array([[cp * cy, cp * sy, sp],
                     [sr * sp * cy - cr * sy, sr * sp * sy + cr * cy, -sr * cp],
                     [-(cr * sp * cy + sr * sy), cy * sr - cr * sp * sy, cr * cp]], np.float32)


def _place(prims, loc, rot, scale):
    """A part's prims (the export's frame: glTF metres, (x, z, y) of Unreal's) placed at a socket (Unreal cm)."""
    to_ue = lambda v: v[:, [0, 2, 1]]   # (the same swap both ways)
    out = []
    for mat, a, idx in prims:
        a = dict(a)
        if 'POSITION' in a: a['POSITION'] = (to_ue(to_ue(a['POSITION'] * 100.0) * scale @ rot + loc) / 100.0).astype(np.float32)
        if 'NORMAL' in a:
            n = to_ue(to_ue(a['NORMAL']) / scale @ rot); a['NORMAL'] = (n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-8)).astype(np.float32)
        if 'TANGENT' in a:
            t = a['TANGENT']; a['TANGENT'] = np.concatenate([to_ue(to_ue(t[:, :3]) @ rot), t[:, 3:]], 1).astype(np.float32)
        out.append((mat, a, idx))
    return out


def sockets(resolver, work):
    """{mesh pak path: [(socket name, glTF position, metres)]}: the NPC hulls' static mesh sockets (Chorus places its
    turrets, thrusters and damage effects there), read from the pak once into <work>/sockets."""
    folder = os.path.join(work, 'sockets'); os.makedirs(folder, exist_ok=True)
    meshes = sorted({m for s in SHIPS for m in s['meshes']})
    todo = [m for m in meshes if not os.path.exists(os.path.join(folder, m.rsplit('/', 1)[1] + '.json'))]
    if todo and resolver is not None:
        resolver.run('jsonall', '^(' + '|'.join(re.escape(m) for m in todo) + r')\.uasset$', folder, capture=True)
    out = {}
    for m in meshes:
        f = os.path.join(folder, m.rsplit('/', 1)[1] + '.json')
        if not os.path.exists(f): continue
        found = []
        for e in json.load(open(f, encoding='utf-8')):
            pr = e.get('Properties', {}) if isinstance(e, dict) else {}
            if e.get('Type') != 'StaticMeshSocket' or 'SocketName' not in pr: continue
            loc = pr.get('RelativeLocation', {})
            ue = [loc.get('X', 0.0), loc.get('Y', 0.0), loc.get('Z', 0.0)]
            found.append((pr['SocketName'], np.array([ue[0], ue[2], ue[1]], np.float32) / 100.0))   # (Unreal cm -> the export's metres)
        out[m] = found
    return out


def _spread(points, n):
    """At most n of the points, spread over the list."""
    if len(points) <= n: return list(points)
    return [points[int(round(i * (len(points) - 1) / (n - 1)))] for i in range(n)]


def _top_points(prims, lo, hi, n=4):
    """n points on the hull's back along its length (turret spots for a hull without turret sockets)."""
    pos = np.concatenate([np.asarray(a['POSITION']) for _, a, _ in prims])
    L, W = float(hi[0] - lo[0]), float(hi[2] - lo[2])
    out = []
    for f in np.linspace(0.2, 0.8, n):
        x = float(lo[0]) + f * L
        m = (np.abs(pos[:, 0] - x) < 0.04 * L) & (np.abs(pos[:, 2]) < 0.15 * W)
        if m.any(): out.append([x, float(pos[m, 1].max()), 0.0])
    return out


# npcships.json: the capital ships with escorts of their own side's fighters and spawn rules (they leave the ships.json
# traffic then: "weight" 0), the dropship launching fighters (Chorus's reveal text: it "deploys Circle forces")
MOD_ID = 'chorus_ships'
ESCORTS = {8: ['circle_fighter', 'circle_fighter_snipe', 'circle_fighter_net', 'circle_scout', 'circle_support'],
           9: ['omen_drone', 'omen_bat_swarm', 'omen_support']}
RACE_WORD = {0: 'terran', 1: 'vossk', 2: 'nivelian', 3: 'midorian', 8: 'pirates', 9: 'void'}
LAUNCHES = {'dropship': {'ships': ['circle_fighter', 'circle_scout'], 'perWave': 3, 'every': 25, 'total': 12}}


# Chorus's NPCs fire their own NPC weapons (BP_NPC_Weapon_*); their second weapon here is the mod's Chorus missile
# launchers (tools/weapons.py), carried by a share of them by the player's rank (ships.json "traffic.secondaries")
SECONDARIES = {'fighter': [{'item': f'{MOD_ID}:chorus_missiles_t1', 'maxRank': 9, 'share': 25},
                           {'item': f'{MOD_ID}:chorus_missiles_t2a', 'minRank': 10, 'share': 35}],
               'boss': [{'item': f'{MOD_ID}:chorus_missiles_t3a', 'share': 100}]}
# Their main gun (ships.json "traffic.primaries"): each hull's own BP_NPC_Weapon_* (its blueprint's weapon component, not
# the special attacks, scripted targets or snipes), its FireInterval and ProjectileDamage through its parents
# (BP_NPC_Weapon_Base: 0.25 s); its damage a second against the Circle fighter's (BP_NPC_Weapon_Fighter_Base: 70 every
# 0.25 s, the remake's NPC gun at the same level), its interval its own. The look the mod's nearest Chorus gun (the NPC
# projectiles' own BP_NPC_Projectile_* effects aren't converted), by the weapon's family; their speeds stay the remake's
# NPC gun's (Chorus's 1500 m/s, at the mod's scale, would all but hit at once).
PRIMARY_LOOKS = [('Scout', 'chorus_gatling_t1'), ('Elder', 'chorus_laser_t2a'), ('Omen', 'chorus_laser_t3b'), ('', 'chorus_laser_t2b')]
PRIMARY_SKIP = ('SpecialAttack', 'ScriptedTarget', 'Snipe', 'MainAttack')
WEAPON_BASELINE = 'BP_NPC_Weapon_Fighter_Base'


def _weapon_values(folder, name, resolver, seen=()):
    """(FireInterval, ProjectileDamage) of NPC weapon blueprint 'name', its parents' where it sets none (None unknown)."""
    f = os.path.join(folder, name + '.json')
    if not os.path.exists(f) and resolver is not None:
        resolver.run('jsonall', '/' + re.escape(name) + r'\.uasset$', folder, capture=True)
    if not os.path.exists(f) or name in seen: return None, None
    interval = damage = parent = None
    for e in json.load(open(f, encoding='utf-8')):
        if e.get('Type') == 'BlueprintGeneratedClass':
            parent = re.sub(r"^.*'(.*)_C'$", r'\1', (e.get('Super') or e.get('SuperStruct') or {}).get('ObjectName', '')) or None
        if e.get('Name', '').startswith('Default__'):
            p = e.get('Properties') or {}
            interval, damage = p.get('FireInterval'), p.get('ProjectileDamage')
    if (interval is None or damage is None) and parent and parent.startswith('BP_NPC_Weapon'):
        pi, pd = _weapon_values(folder, parent, resolver, seen + (name,))
        interval = interval if interval is not None else pi
        damage = damage if damage is not None else pd
    return interval, damage


def ai_kind(s, work):
    """The remake's "ai" for NPC ship entry 's' by its blueprint's behaviour tree: BT_Scout_* "chorusScout", BT_Gunship*
    "chorusGunship" (their own trees in Flight.ChorusDogfight), else "chorus" (BT_Fighter_CombatRoam's)."""
    f = os.path.join(work, 'bp', s['bp'].rsplit('/', 1)[1] + '.json') if s.get('bp') else None
    trees = re.findall(r"BehaviorTree'(BT_[A-Za-z0-9_]+)'", open(f, encoding='utf-8').read()) if f and os.path.exists(f) else []
    if any(t.startswith('BT_Scout') for t in trees): return 'chorusScout'
    if any(t.startswith('BT_Gunship') for t in trees): return 'chorusGunship'
    return 'chorus'


def primaries(s, work, resolver):
    """ships.json "traffic.primaries" for NPC ship entry 's' (PRIMARY_*), or None."""
    if not s.get('bp'): return None
    f = os.path.join(work, 'bp', s['bp'].rsplit('/', 1)[1] + '.json')
    if not os.path.exists(f): return None
    found = sorted(set(re.findall(r"(BP_NPC_Weapon_[A-Za-z0-9_]+)_C'", open(f, encoding='utf-8').read())))
    mains = [w for w in found if not any(k in w for k in PRIMARY_SKIP)]
    if not mains: return None
    folder = os.path.join(work, 'bp_npcw'); os.makedirs(folder, exist_ok=True)
    interval, damage = _weapon_values(folder, mains[0], resolver)
    bi, bd = _weapon_values(folder, WEAPON_BASELINE, resolver)
    if not (interval and damage and bi and bd): return None
    look = next(item for key, item in PRIMARY_LOOKS if key in mains[0])
    return [{'item': f'{MOD_ID}:{look}', 'factor': round((damage / interval) / (bd / bi), 3), 'reloadMs': round(interval * 1000)}]


# the pursuers' (Guilt's) npcships.json spawn: the Omen-haunted orbits, rarely, from rank 10
PURSUERS = {'guilt': {'chance': 5, 'stations': [f'{MOD_ID}:nimika_prime', f'{MOD_ID}:tarris_wormhole'], 'minRank': 10, 'distance': [6, 10]}}


def npc_ships(entries):
    """npcships.json entries for the capital ships among the built ships.json entries (and their traffic set to 0), and the
    pursuers' (PURSUERS: a "boss" alone, hostile)."""
    ids = {e['id'] for e in entries}
    out = []
    for e in entries:
        if e['id'] in PURSUERS and (e.get('traffic') or {}).get('role') == 'pursuer':
            out.append({'id': e['id'], 'kind': 'boss', 'ship': f"{MOD_ID}:{e['id']}", 'name': e['name'], 'race': RACE_WORD.get(e.get('race', 9), 'void'),
                        'hostile': True, 'escorts': {'count': 0}, 'spawn': dict(PURSUERS[e['id']])})
            continue
        t = e.get('traffic')
        if not isinstance(t, dict) or t.get('capital') != 'battleship': continue
        race = e.get('race', 0)
        t['weight'] = 0
        d = {'id': e['id'], 'kind': 'capital', 'ship': f"{MOD_ID}:{e['id']}", 'name': e['name'], 'race': RACE_WORD.get(race, 'terran')}
        if race in (8, 9): d['hostile'] = True
        escorts = [f'{MOD_ID}:{x}' for x in ESCORTS.get(race, []) if x in ids]
        d['escorts'] = {'count': [2, 4], **({'ships': escorts} if escorts else {})}
        # Terran ones in the inner systems now and then; the Circle's and the Omen's rarer, anywhere
        d['spawn'] = {'chance': 4, 'races': ['terran']} if race == 0 else {'chance': 2}
        if e['id'] in LAUNCHES:
            l = dict(LAUNCHES[e['id']]); l['ships'] = [f'{MOD_ID}:{x}' for x in l['ships'] if x in ids]
            if l['ships']: d['launches'] = l
        out.append(d)
    return out


def build(export, mod, resolver=None, only=None, work=None, anims=None):
    """The NPC ships' models, maps and ships.json entries (those exported; only: a set of ids)."""
    os.makedirs(os.path.join(mod, 'models', 'npc'), exist_ok=True); os.makedirs(os.path.join(mod, 'maps'), exist_ok=True)
    _PNG.clear()   # (textures exported since the last call)
    shown = names(resolver, work or os.path.dirname(os.path.abspath(export)))
    socks = sockets(resolver, work or os.path.dirname(os.path.abspath(export)))
    warships.blueprints(resolver, work or os.path.dirname(os.path.abspath(export)))
    capital.blueprints(resolver, work or os.path.dirname(os.path.abspath(export)))
    out = []
    for s in SHIPS:
        sid = s['id']
        if only and sid not in only: continue
        srcs = [os.path.join(export, m + '.glb') for m in s['meshes']]
        if not os.path.exists(srcs[0]):
            print(f'  {sid}: not exported'); continue
        meshes = [glb.static_mesh(f, keep=KEEP) for f in srcs if os.path.exists(f)]
        for part, names_ in s.get('attach', {}).items():   # (a blueprint's parts on the hull's sockets: one mesh group)
            src = os.path.join(export, part + '.glb')
            placed = [_socket(work or os.path.dirname(os.path.abspath(export)), s['meshes'][0], n) for n in names_] if os.path.exists(src) else []
            group = [p for t in placed if t for p in _place(glb.static_mesh(src, keep=KEEP), *t)]
            if group: meshes.append(group)
            else: print(f'  {sid}: {part.rsplit("/", 1)[1]} not placed')
        for part, locs in s.get('place', {}).items():   # (a blueprint's part at its component's offset, cm)
            src = os.path.join(export, part + '.glb')
            if not os.path.exists(src): print(f'  {sid}: {part.rsplit("/", 1)[1]} not exported'); continue
            meshes.append([p_ for l_ in locs for p_ in _place(glb.static_mesh(src, keep=KEEP), np.array(l_, np.float32), np.eye(3, dtype=np.float32), np.ones(3, np.float32))])
        nose = s.get('nose') or _nose(meshes[0])
        meshes = [_turn(m, nose) for m in meshes]
        sc = s.get('scale', 1.0)   # (the blueprint's scale on its mesh component: Guilt's 0.17)
        if sc != 1.0:
            meshes = [[(m_, dict(a_, POSITION=(np.asarray(a_['POSITION'], np.float32) * sc).astype(np.float32)), i_) for m_, a_, i_ in mesh]
                      for mesh in meshes]
        lo, hi = glb.bounds([p for m in meshes for p in m])
        length_m = float(hi[0] - lo[0]) * SCALE
        role = s['role']
        if role == 'fighter' and length_m > MAX_TRAFFIC: role = 'boss'
        cap = {'boss': MAX_BOSS, 'capital': MAX_CAPITAL, 'freighter': MAX_CAPITAL}.get(role)
        shrink = min(1.0, cap / length_m) if cap else 1.0
        size = 2048 if length_m > 500 and s['role'] != 'freighter' else 1024   # (the freighters' bakes at 1024: the mod's size)
        # (a skinned ship's file keeps its mesh unscaled: its shell's lengths in those units, 1 / the blueprint's scale)
        skinned = bool(s.get('skinned') and CHORUS_LAYERS and s.get('idle'))
        prims, mats = _convert(export, mod, sid, meshes, resolver, size, s.get('override'), (1.0 / s.get('scale', 1.0)) if skinned else None)
        if prims:   # (measured again on what is drawn: a thruster part's flame and glow cards are left out)
            lo, hi = glb.bounds(prims)
            length_m = float(hi[0] - lo[0]) * SCALE
            role = s['role']
            if role == 'fighter' and length_m > MAX_TRAFFIC: role = 'boss'
            cap = {'boss': MAX_BOSS, 'capital': MAX_CAPITAL, 'freighter': MAX_CAPITAL}.get(role)
            shrink = min(1.0, cap / length_m) if cap else 1.0
        name = shown.get(sid, s['name'])
        if not prims:
            print(f'  {sid}: nothing to draw'); continue
        k = K * shrink   # game units per model metre (the hull scaled down past its cap)
        if any('chorus' in e_ for e_ in mats) or any('COLOR_0' in a_ for _, a_, _ in prims):
            # Chorus's layers read UV sets 1 and 3 and the vertex colours: every primitive gets them (glTFast reads one
            # vertex layout per mesh), zero UVs and white where a part has none
            glb.save(os.path.join(mod, 'models', 'npc', sid + '.glb'), _uniform(prims), sid, keep=CHORUS_KEEP)
            for e_ in mats:   # (the kicker's fade: Chorus's centimetres -> model metres -> game units -> the remake's world)
                c_ = e_.get('chorus', {})
                for f_ in ('kickerFadeOffset', 'kickerFadeLength'):
                    if f_ in c_: c_[f_] = round(c_[f_] / 100.0 * k * 0.05, 2)
        else:
            glb.save(os.path.join(mod, 'models', 'npc', sid + '.glb'),
                     [(m, {k_: v for k_, v in a.items() if k_ not in ('TEXCOORD_1', 'TEXCOORD_2', 'TEXCOORD_3')}, i) for m, a, i in prims], sid)
        game = lambda v: [round(-float(v[2]) * k, 1), round(float(v[1]) * k, 1), round(float(v[0]) * k, 1)]
        if role == 'prop':   # (a warship part's model: no race, never flown; its origin the device's, tools/warships.py)
            out.append({'id': sid, 'name': name, 'description': f"A part of a Chorus warship: its {name.lower()}.", 'race': -1,
                        'armor': 1000, 'cargo': 0, 'handling': 10, 'price': 0, 'priceDefault': 0,
                        'slots': {'primary': 0, 'secondary': 0, 'turret': 0, 'equipment': 0},
                        'model': f'models/npc/{sid}.glb', 'modelLength': max(1, round(length_m / 0.05)), 'modelYaw': 90,
                        'materials': mats, 'traffic': {'weight': 0}, 'explosionScale': 2.0})
            print(f'  {sid} ({name}): warship part, {length_m:.0f} m')
            continue
        mid_y = float(lo[1] + hi[1]) / 2
        half = float(min(hi[1] - lo[1], hi[2] - lo[2])) / 6
        mounts = [{'slotType': 0, 'position_engine': game([hi[0], mid_y, 0.0])}]
        # the hull's sockets (in the turned frame): thrusters, turrets, damage effects
        sk = [(n_, ROT[nose](p_[None, :])[0] * sc) for m_ in s['meshes'] for n_, p_ in socks.get(m_, [])]
        exhausts = [(p_, half) for n_, p_ in sk if THRUSTER_SOCKETS.search(n_)]
        if not exhausts:   # else at the rear faces of its own thruster glow (the traffic ships', the warships')
            glows = {e_['material'] for e_ in mats if e_.get('engine')}
            exhausts = [(c_, max(h_)) for g_ in sorted(glows) for c_, h_ in nozzle_faces(prims, g_)]
        if not exhausts: exhausts = [(np.array([lo[0], mid_y, 0.0]), half)]
        for p_, h_ in _spread(sorted(exhausts, key=lambda e_: (float(e_[0][2]), float(e_[0][1]))), MAX_EXHAUSTS):
            mounts.append({'slotType': 3, 'position_engine': game(p_), 'turretAngles': [0.35, 0.35, 0.35],
                           'glowColor': s['glow'], 'glowSize': [max(round(h_ * k), 8), max(round(h_ * k), 8), 40]})
        turrets = []
        if role in ('capital', 'boss'):
            turrets = [p_ for n_, p_ in sk if TURRET_SOCKETS.search(n_)] or (_top_points(prims, lo, hi) if role == 'capital' else [])
            for p_ in _spread(turrets, MAX_TURRETS)[:MAX_TURRETS]:
                mounts.append({'slotType': 2, 'position_engine': game(p_)})
        smoke = _spread([p_ for n_, p_ in sk if DAMAGE_SOCKETS.search(n_)], 4)
        race = 9 if s['races'] == [9] else (8 if 8 in s['races'] else s['races'][0])
        if role == 'player':
            if s.get('rig') and anims and nose == '+x':   # (Chorus's drift on the Forsaken's skeleton: tools/rig.py)
                rig.save_rigged(os.path.join(mod, 'models', 'npc', sid + '.glb'), srcs[0], glb.static_mesh(srcs[0], keep=KEEP[:-1]), anims,
                                sid, keep_materials={m for m, _, _ in prims})
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
            if s.get('rig') and anims and nose == '+x': e['animations'] = rig.ANIMATIONS
            print(f'  {sid}: player ship, {length_m:.0f} m, nose {nose}, {len(mats)} materials')
            out.append(e); continue
        if role == 'fighter':
            traffic = {'weight': s.get('weight', 1), 'races': s['races'],   # (its tree: the remake's "chorus" / "chorusScout" / "chorusGunship")
                       'ai': ai_kind(s, work or os.path.dirname(os.path.abspath(export)))}
            if s.get('traffic_role'): traffic['role'] = s['traffic_role']
            traffic['secondaries'] = SECONDARIES['fighter']
            prim = primaries(s, work or os.path.dirname(os.path.abspath(export)), resolver)
            if prim: traffic['primaries'] = prim
        elif role == 'boss':
            traffic = {'boss': True, 'ai': 'chorus', 'secondaries': SECONDARIES['boss']}
            prim = primaries(s, work or os.path.dirname(os.path.abspath(export)), resolver)
            if prim: traffic['primaries'] = prim
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
        if s.get('traffic') is False:   # (in the mod, flown by no one as traffic: Guilt, a story hazard in Chorus, not a ship)
            del e['traffic']
            if s.get('traffic_role'): e['traffic'] = {'weight': 0, 'role': s['traffic_role']}   # (its role: npcships.json sends it)
        if s.get('description'): e['description'] = s['description']
        if role in ('capital', 'freighter'): e['explosionScale'] = round(min(20.0, max(2.0, length_m * shrink / 150)), 1)
        n_turrets = sum(1 for m_ in mounts if m_['slotType'] == 2)
        if n_turrets:   # Chorus's own turrets (tools/turrets.py's items), in turn along the mounts
            kinds = CHORUS_TURRETS.get(sid, CHORUS_TURRETS_DEFAULT)
            e['npcTurrets'] = [f'{MOD_ID}:{kinds[i % len(kinds)]}' for i in range(n_turrets)]
        if smoke: e['smoke'] = [game(p_) for p_ in smoke]
        if sid in WARP_IN: e['warpIn'] = WARP_IN[sid]   # (its Omen tissue materializing where it arrives)
        if sid in wrecks.WRECKS:   # (Chorus's wreck: the ship breaks into its pieces where it explodes)
            wrecks.apply(e, s, export, mod, resolver, nose, sc, size)
        if sid in warships.CONFIGS:   # (Chorus's warships: their parts as subsystems, its turrets among them)
            warships.apply(e, s, work or os.path.dirname(os.path.abspath(export)), mats, nose, sc, k, shrink)
            variants = warships.variants(e, s, work or os.path.dirname(os.path.abspath(export)), mats, nose, sc, k, shrink)
        # its own idle (rig.NPC_CLIPS), looped: a rigid skin as parts on its skeleton's nodes (tools/rig.py)
        idle = rig.npc_clip(work or os.path.dirname(os.path.abspath(export)), s['idle']) if s.get('idle') else None
        if idle is not None and nose == '+x' and s.get('scale', 1.0) == 1.0 and len(srcs) == 1 and rig.is_rigid(srcs[0]):
            raw = glb.static_mesh(srcs[0], keep=KEEP[:-1])
            if {m_ for m_, _, _ in prims} <= {m_ for m_, _, _ in raw}:   # (no material renamed by the conversion)
                rig.save_rigged(os.path.join(mod, 'models', 'npc', sid + '.glb'), srcs[0], raw, {'idle': idle}, sid,
                                keep_materials={m_ for m_, _, _ in prims})
                e['animations'] = {'idle': 'idle'}
        elif idle is not None and skinned and len(srcs) == 1:
            # a soft skin (Guilt's arms) kept skinned: the remake plays its idle on the bones (ships.json "skinned")
            rig.save_skinned(os.path.join(mod, 'models', 'npc', sid + '.glb'), srcs[0], {m_: m_ for m_, _, _ in prims}, {'idle': idle}, sid)
            e.update({'skinned': True, 'animations': {'idle': 'idle'}})
        print(f'  {sid} ({name}): {role}, {length_m * shrink:.0f} m{" (from %.0f)" % length_m if shrink < 1 else ""}, nose {nose}, {len(mats)} materials')
        out.append(e)
        if sid in warships.CONFIGS: out += variants   # (its other configurations, on the same model)
        if sid == capital.HOST:   # (Chorus's player capital ship on the same model: tools/capital.py)
            pe = capital.player_entry(e, s, work or os.path.dirname(os.path.abspath(export)), prims, nose, sc, k, export, mod,
                                      lambda ms: _convert(export, mod, sid, ms, resolver, size, s.get('override'))[0], resolver)
            if pe: out.append(pe)
    return out
