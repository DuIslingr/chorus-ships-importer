# Chorus ships importer

Builds the **chorus_ships** mod for the Galaxy on Fire 2 Unity Remake from **your own copy of Chorus**:
- **Ships sold by Space Lounge visitors,** each with its own sounds and the remake's Chorus flight:
  - the **Forsaken**, Nara's fighter, as a customizable ship whose mounted Chorus guns show on its weapon platforms;
  - the **Elder Buddy** (the Forsaken in the Elder's colours, also a skin in its Customize screen);
  - the **Argus**.
- **Chorus's fifteen weapons** in the shops: the gatlings, lasers and missile launchers of every tier, under their Chorus
  names.
- **Every other Chorus ship, flown by the remake's NPCs:**
  - the Circle's and the pirates' fighters, scouts, support ships and drones with the pirates, the Omen's drone, bat swarm
    and warden with the Void;
  - the gunships, the Prophet, Sav, Ree, Aryana's ship and the Omen fortress as pirate bosses;
  - the civilian liners, transports, haulers, couriers, container ship, Atlases and traffic ships as freighters;
  - the frigates, dropship, battleship, the Circle's warships, Kardoh's ship, the Omen's elite fortress as capital
    ships (the Terran ones parked in the orbits, the Circle's and the Omen's hostile).
- **Chorus's regions as new systems:** Stega, Amarok, Nimika and Tarris, past Pescal Inartu at the top of the map, each
  under its region's sky and with its stations' planets as Chorus draws them (below). `--no-world` leaves them out.

`python3 tools/sheet.py` renders a contact sheet of every ship (`chorus_ships_sheet.png`).

This importer contains **nothing from Chorus**: no models, textures, game data or encryption key, only the code that
reads the files of your own installation. The mod it builds does contain Chorus's models and textures (© Deep Silver
FISHLABS), so it is for your own use: **don't share or upload the built mod**. Share this importer instead.

## What you need

- The **Galaxy on Fire 2 Unity Remake**, a build with its Chorus layers (GoF2/Hull's `chorus` materials, 2026-11-11) for the
  NPC hulls' trim sheets; with an older one, build with `--bake-hulls`.
- **Chorus**, installed (Steam, Epic or GOG: the PC game, with its `SpacePrototype/Content/Paks` folder).
- The **.NET 10 SDK** (dotnet.microsoft.com) to build the exporter.
- A checkout of **CUE4Parse** (`git clone https://github.com/FabianFG/CUE4Parse`), the library that reads Unreal
  Engine archives. By default it is expected beside this folder (`../CUE4Parse`); `--cue4parse` points elsewhere.
- **Python 3.9 or newer** with numpy and Pillow (`python3 -m pip install numpy pillow`).
- **ffmpeg** on the PATH, for the sounds. Without it the ship and weapons keep the game's sounds.
- Optional: **Blender** (4.2 or newer) on the PATH or given with `--blender`, for the shop icon and the mod's preview
  image. Without it the ship uses the default icon.

No FModel, no AES key and no mappings file are needed:
- **The key:** Chorus's archive is encrypted. The exporter finds the key in your own copy of the game
  (`Chorus-Win64-Shipping.exe`), the same way key finder tools do.
- **The mappings:** Chorus's packages carry their own property types, so no `.usmap` file is needed.

## Building the mod

```
python3 import.py --game "C:/Program Files (x86)/Steam/steamapps/common/Chorus"
```

The first run builds the exporter (`exporter/`, a small CUE4Parse console program). It then finds the key, exports the
Forsaken's mesh, materials and textures into `chorus_work/`, converts them, and writes `chorus_ships/`. Copy that
folder (or link it) into the remake's **Mods** folder. Later runs reuse the export; `--fresh` exports again.

Settings can also go in `config.json` (copy `config.example.json`); the command line wins.

### For phones

`--mobile` also writes a lighter copy for phones, `chorus_ships_phone/` and `chorus_ships_phone.zip` (on the phone: Mods >
Import mod, and pick the zip). It has the same mod id, so saves move between devices. It needs Blender (4.2 or newer:
`--blender`, or on the PATH). `tools/mobile.py` and `tools/decimate_blender.py`, after the ES2 importer's:

- **Models:** Blender decimates the stations, the rocks and the NPC hulls without animations to `--ratio` of their
  triangles (default 0.25). It works on each material on its own, so none is lost. Engine flames, lights,
  holograms and any material with under 1500 triangles stay whole. Every UV set and the vertex colours are kept for
  Chorus's layers. The player ships, the rigged and skinned NPCs, the weapons and the turrets stay as built (their
  bones, clips and marker nodes must stay exactly).
- **Textures:** every image is halved, but Chorus's palettes (`maps/chorus/pal_*`, read texel by texel) and the planets'
  curve rows (`planets/*_curves.png`) stay as they are.

The Chorus systems' world part goes from about 1 GB to about 240 MB (2.8 million triangles to 750 000). The remake's
Low preset (a phone's default) draws the Chorus skies from their baked panoramas. `--zip` zips the desktop mod too.

## What the conversion does

- **Model:** the skeletal mesh becomes a static `.glb` in its rest pose, one primitive per material. It's sized at 3.6×
  Chorus's scale, like the EVERSPACE 2 importer's ships (`modelLength` 749, `modelYaw` 90: Unreal's nose is +X).
- **Materials:** written to `ships.json` "materials" with PNG maps.
  - The colour map is darkened by the baked ambient occlusion.
  - Normal maps are converted from DirectX to Unity (green flipped).
  - The RMO map (roughness, metallic, AO) becomes metallic / smoothness.
  - The emissive masks are baked with each material instance's colours and multipliers, read through its parents
    (`tools/mi.py`: an instance's own values, then its parent instances', then the master material's defaults).
  - Tangents get their handedness from the UVs (`glb.tangent_signs`: the export writes +1 everywhere, which turned the
    normal maps inside out on mirrored UV islands, a ship's other half).
  - The thrusters' glow follows the engines (`engine`).
- **Mounts:** the guns go on the skeleton's weapon platform bones (`SCK_Weapon_L/R`) and the launcher between the wing
  weapon attach points. The exhausts are found on the mesh, at the thrusters' rear-facing nozzle faces. The cockpit
  view is at the cockpit window bone.
- **Stats:** armour, cargo, handling, slots and price are this importer's choices for an elite fighter. Chorus's own
  numbers don't map onto Galaxy on Fire 2's.
- **Flight:** the Forsaken flies with the remake's **Chorus flight** (`"flightStyle": "chorus"`: forward thrust on Chorus's
  curves, speed-dependent turning, a held boost and a held drift), whatever the player's option. `--flight-style player`
  leaves it to the option; `free` / `original` set another style.

## Sounds

Chorus's sounds are FMOD Studio events in the loose banks of your install (`SpacePrototype/Content/UnleashedPrototype/
FMOD/Desktop`). The exporter reads the event names from `MasterBank.strings.bank`, finds the waves each event plays and
decodes them into `chorus_work/fmod`.

`tools/sounds.py` picks the waves for each of the remake's sound slots from the Forsaken's events:

| Slot | Chorus event |
|---|---|
| engine | Engine |
| boost start / loop / stop | Boost |
| drift start / loop / stop | Drift Start / Active / Stop Ignition |
| dodge | Dodge Roll |
| travel boost start / loop / stop | Travel Boost |

Each sound is set to the game's own level (a loop's loudness, a shot's loudest 60 ms) and written as Ogg Vorbis, with
4- or 6-channel waves mixed down to stereo. Chorus switches waves inside an event by its own parameters (rpm, speed),
which the remake doesn't have, so each slot takes the waves that fit it. `--no-sounds` leaves them out.

## Ships

- **Forsaken** (`tools/ships.py`, `tools/kit.py`): a ship kit with one hull part and Chorus's weapon model of each mounted
  Chorus gun (the Talon, Guardian Fang, ... models) on its platforms; other primaries a Talon or a Glow (energy weapons),
  secondaries none (their mount is inside the hull). The Customize screen can hide them. `--no-kit`: a plain ship.
- **Omen materials, moving** (`tools/npcs.py` `_jtu_crystal`, `_faceless_tissue`): the Prophet's crown and Omen crystal
  (M_JTU_Blend) and the Faceless tissue (M_JTU_Faceless) drawn as their compiled shaders draw them, by the remake's Chorus
  layer kinds "crystal" and "tissue": the crown's two surfaces blended by its vertex colours with red veins glowing
  beneath, the tissue's ice scrolling and its glow breathing out from the ship's middle. (Without the remake's layers:
  the bakes as before.)
- **Glow lines** (`tools/ships.py` `_wave`): the Forsaken's and the Elder Buddy's hex lines pulse as Chorus draws them
  (M_Phoenix's compiled base pass: Emissive02 Min / Max along a wave over T_HexPatternNoise_01_A), the remake's material
  `"wave"` block; the rest of their glow baked into the emission map as before.
- **Animations** (`tools/rig.py`, the exporter's `anim`): the Forsaken's skin is rigid (every vertex on one bone), so its
  hull is written as parts on its skeleton's nodes, with Chorus's idle and drift clips (phoenix_anim_driftStart / Loop /
  End) as node animations; ships.json `"animations"` has the remake play them while the player drifts. Also: the travel
  boost clips; the steering / thrust / brake flaps and the bank as poses weighted by the input; the weapons deploying
  while the player fires (the kit's primary guns ride the wpnPlatform bones: the mounts' `follow`); the dash's dodge
  roll, and its own dodge out of a drift. Each layered clip keys only the bones that differ from Chorus's idle (more
  than 1 cm or 0.003 in the quaternion), the bank's leave the root alone (the remake rolls the ship itself). The Elder
  Buddy and the supercharged Forsaken share the skeleton and the clips.
- **Supercharged Forsaken:** its energy wings (Mi_SuperChargedShieldWings_Sheets, translucent) as an additive glow: the
  feather mask in the Main Color, its streaks brighter, kept under the remake's bloom (Chorus's HDR colours white it out
  at full strength); their scrolling noise shimmer and orange accent are left out.
- **Elder Buddy:** the same hull in BP_Player_Ship_ElderBuddy's material set, a skin of the kit; its own engine, boost,
  drift and dash sounds. Its hull instances inherit their glow from the Forsaken's (through MI_Elder_Theia_* and
  MI_ElderAmaranth_*): the Forsaken's cyan lines and red accents; only its thrusters are its own orange.
- **Argus** (SK_TF_Argus): its MRO maps converted. Its hull glows from its vertex colours (M_Argus_Master's "Use VC as
  Emissve"; its emissive map is empty): red, the lit trim and vents (x EmissiveIntensity_R), and blue, its small lights
  (x _B), baked into an emission map; green, a soft gradient over whole panels, is the hull-heat mask (off at rest) and
  left out. Guns on its side weapon bones, the launcher under the nose, exhausts at its main nozzles; its own engine,
  boost, roll and travel boost sounds.
- **Everything else** (`tools/npcs.py`, about seventy ships): their role follows the remake's limits: a fighter (up to
  150 m) flies in the traffic, a longer one is a pirate boss (up to 400 m), and the big hulls are freighters or capital
  ships, scaled down past 4.5 km. Each is turned nose forward (away from its thruster glow, or along its longer axis).
  Their materials are rebuilt from Chorus's master materials, after their compiled shaders (the exporter's `shaders`
  command, disassembled; `tools/npcs.py` TRIM_SHADER / PLATING_SHADER has the formulas):
  - **Trim sheets and platings** (M_TrimLayersMaster, M_NPCShipTrimMaster, M_PlatingMaster: nearly every hull) are drawn
    by the remake's **Chorus layers** (GoF2/Hull, the material's `chorus` block) from Chorus's own maps over the hull's own
    UV sets, as Chorus draws them: a palette swatch per face (UV3), the tiling layer (UV1), the trim sheet's accent strips,
    occlusion, normals and lit strips (UV0), the dirt by the vertex colours, the gunships' red kicker rim far off. The
    maps are written once into `maps/chorus/` and shared. (A bake into one texture per hull, `--bake-hulls`, lost the
    trim sheet's detail on the big hulls: a 2K map over a 4 km warship is metres a texel. It needs a remake without the
    Chorus layers only.)
  - Tech panels from their own maps at full size; Sav's and Ree's hulls by their layer mask (a tinted coat or bare metal
    per panel, tiled; baked), their floater panels from their own sheet; decals (hull numbers, labels, emblems) cut out
    of their sheets; a blueprint's parts on the hull's sockets (the Prophet's weapon pods); windows as their pane atlas
    (each pane lit or dimmed) or their glass mask; lights and thruster glows as flat glows (a station light's channel
    by its UV quadrant, as the compiled shader picks it).
  - The Omen's tissue (M_JTU_Faceless) is all glow, as its shader has it (a black, unlit base): its outer glow mixed at
    least half with its inner glow over the variation maps, baked as seen head-on with its breathing pulse at rest; the
    cores glow through their thin parts. The Prophet's crystal crown glows red through its veins (its blueprint's lights
    override applied by hand).
  - Guilt is left out: in Chorus it's not a ship but an invincible Faceless that hunts Nara through the temples and
    tombs. (The importer can still draw it, kept skinned with its idle and its shells by the remake's Chorus shell, for a
    mod that wants it: npcs.py's comment where it was.)
  - Blueprint parts: the engine thrusters (nozzles and glows) of the fighters, scouts, Support Ship, gunships, Sav, Ree,
    Aryana and the civilian ships (a child blueprint's inherited from its parent), the liner's, transport's and container
    ship's; the gunship's gun pod and the Heavy Gunship's mine thrower at their components' offsets; a blueprint's mesh
    scale (the Support Ship's 0.9). The Omen Support's crystals play its idle (its rigid skin as parts on its
    skeleton). Left out: the frigates', Kardoh's, the warships' and the battleship's thrusters (placed by Chorus's levels,
    not modelled in place), and the wreck meshes ships break into when destroyed.
  - Normal-only decals and effect materials are left out, and so is the unfinished SM_TU_Ufo (no material for it in the
    pak). They fly with the remake's NPC hulls and guns: only the look is Chorus's.
- **Turrets** (`tools/turrets.py`): Chorus's light, heavy, missile, mine and sniper turrets as turret items (on the
  Hammerhead D2A2, NPC-only), their models split on their rigs (the base fixed, a `pivot` at baseYaw that turns, a
  `turret_gun` at basePitch that tilts, the barrel turned onto +Z), their materials Chorus's layers (the remake's turret
  `materials`). The Chorus capital ships carry them (the Circle's warships heavy and missile turrets, the dreadnought its
  sniper too) instead of the Hammerhead. Their mounts' hatches and the turrets' own animations are left out.
- **Mounts and escorts:** an NPC hull's exhausts sit at its mesh's Thruster sockets, else at the nozzles of its own
  thruster glow; a capital ship's turrets at its Artillery / NPCAttack sockets, else along its back (armed through
  `npcTurrets`: the Hammerhead D2A2, the Vossk L'ksaar for the Vossk); the warships smoke at their damage-effect
  sockets. `npcships.json` brings the capital ships with escorts of their own side's fighters (the Circle's Ravens,
  Crows and Harriers, the Omen's Emergents, swarms and Conduits) and the dropship launching Circle fighters.
- **Names:** an NPC ship's name is its Chorus blueprint's display name (BP_NPC_Ship_*: the name on its lock-on), read
  from your pak at build time; a character's ship without one is named by its asset (BP_NPC_Ship_PirateQueen -> Pirate
  Queen); the rest (the haulers, couriers, warships..., which Chorus places in its levels, not as NPC ships) get this
  importer's own descriptive names. `tools/sheet.py` labels which is which. The civilian ship is Chorus's
  BP_NPC_Ship_CivilianShip (SM_TG_Atlas_MK2_002) with its variants' paint (M_TG_Atlas_02 / _03); the Atlas, Mk II and
  Mk III hulls are flown by no NPC blueprint and keep their asset names. `python3 tools/sheet.py` also writes a page per
  role (`chorus_ships_sheet_<role>.png`).

## Weapons

`tools/weapons.py` writes `items.json`: all fifteen (T1, and the A / B branches of T2 and T3), named and described
from your copy (BP_PlayerEquipmentMasterData), damage per second in Chorus's ratios at a third (the original's scale), the
perks as the remake's echo blasts, salvos and EMP. The T1 weapons:
- **Gatling:** on the Mass Driver MD 10. The tracers are orange and it uses Chorus's gatling loop.
- **Laser rifle:** on the Berger Converge IV. It fires Chorus's 25-damage shots every 0.9 s, 0.62 of the gatling per
  second, as in Chorus.
- **Missiles:** a secondary on the Intelli Jet, fired in pairs, faster, red.

In Chorus all three are primaries. Galaxy on Fire 2 has no missile primaries, so the launcher fires secondary missiles.
The gun models are on the Forsaken's mounts through its ship kit (above).

## The Chorus systems

`tools/world.py` writes `systems.json` and `stations.json`: four systems (one jumpgate from Pescal Inartu into Stega, the
four linked among themselves) and seven stations, named from Chorus's own text. The game's systems are unchanged. The
world part is large (about 1.1 GB, most of it the seven stations).

- **Skies** (`tools/sky.py`): each region's sky material (MI_Skybox_Loc*) as the remake's `skybox` "chorus" block, drawn
  live by the remake's port of Chorus's sky shader (Options > Graphics "Live mod skies", on from Medium), and the same
  formula baked by numpy into a 4096 x 2048 panorama for Low and for the crossfade between systems. The gradient, the
  tiled star mask through its curve, up to four nebula / galaxy layers placed by heading, elevation, scale and rotation.
  A layer of a planet's atmosphere glow (T_LocASP_Atmosphere) is left out: Chorus hides its centre behind the region's
  planet, which the sky doesn't have.
- **Planets** (`tools/planets.py`): each station's planet as a `planetSphere` with `"look": "chorus"`: M_Planet03 (tiled
  terrain, macro height, water, flow-mapped clouds, the atmosphere's rim) or M_Planet_SurfaceCheap (diffuse, night lights,
  clouds, two rims), with its atmosphere shell where Chorus has one; their colour curves baked from the CA_Planets atlas.
- **Stations** (`tools/stations.py`): The Enclave (Stega), Helios and Eos (Amarok), Nimika's ring station (Nimika Prime)
  and Tarris's big station (Achunal Labs) rebuilt from their levels' merged
  meshes (Maps/<region>/<level>_GeoLOD/SM_MERGED_*: Chorus's HLOD proxies, placed in the level's space; the cooked
  prefabs hold no actors), their materials converted as the ships' (Chorus's layers drawn by the remake). Every LOD is
  exported (`export <list> <out> all`) and the largest meshes step down until a station fits 350 000 triangles (Stega's
  still 520 000 at its coarsest). Stega Belt and the Tarris Wormhole, which have no station in Chorus, take other levels'
  structures: LocASP03's military platform (its towers, docking port and platforms; its power cables and Cult lights
  kilometres off left out) and one of LocRSB14's antenna array.
- **Asteroids** (`tools/rocks.py`): the field asteroids as the orbits' asteroid fields (mined like the game's), the giant
  rocks and split rocks as props, their M_MaskBlend_Placeholder material (two tiled rock layers blended by a mesh mask,
  the mesh's normal map under the layers' by Unreal's angle-corrected blend) baked per rock over its own UVs. The magma
  rocks (M_Asteroid_Master: its albedo curve, its blackbody glow by temperature, masked by the vertex colours) baked
  over each rock's unique layout; Chorus's destroyed moon put back together at Nimika Prime (its three shell pieces at
  one place and scale, its loose rocks round it).
- **Jumpgate** (`tools/gate.py`): Chorus's own gate (SM_MERGED_Jumpgate_001, a ring tunnel at the front of a 9.7 km
  frame) in all four systems, its origin in the ring (systems.json jumpgate `"centre": false`), 50 000 units long, with
  Chorus's FTL portal in the ring (the Theia gate's card and glow, M_FTL_Portal / M_FTL_PortalGlow as material
  `"portal"` blocks: veins scrolling out in polar coordinates, the scene behind bent through it).
- **Factions** (`tools/factions.py`): the Circle and the Omen as the remake's hostile mod races (`races.json`): their
  fighters fly for them as well as for the game's pirates and the Void, their capital ships for them, the Chorus systems
  name both as raiders, and a rift stage can be theirs. Chorus's bosses join the remake's rift runs (`encounters.json`
  `rift` `bosses`): the Omen's elite fortress and the Circle's dreadnought, destroyer and warship as capital bosses, the
  Omen fortress, the Prophet, Sav, Ree and Aryana as fighter bosses with Chorus's guns.
- **Warships as boss fights** (`tools/warships.py`): the Circle's warship, destroyer and dreadnought carry Chorus's
  parts as the remake's capital ship subsystems, read from their blueprints (BP_<Size>Warship_Base and its configuration:
  the modules' weakpoints on the hull's sockets): turrets (at most 8, the heavier first), energy arrays shielding the core
  (stage 1; the barriers, SM_<Size>WarshipBarriers, shown as an energy field until they fall), the thrusters as weak spots
  and the reactor core (stage 2) whose destruction destroys the ship, the small warship's hangar launching Circle
  fighters. The hull itself shrugs hits off (`"hullDamage": 0`), as Chorus's does. The devices' meshes are prop ships
  (`chorus_part_*`, race -1, never flown), each set at its full turn (`"turretForward"`).
- **Wrecks** (`tools/wrecks.py`): the Circle's and the pirates' fighter, scout and gunships (each with its gun pod or mine
  thrower), the Disruptor, the Omen Support, the Atlas, and your own Forsaken, Elder Buddy and Argus break into Chorus's
  own wreck pieces where they explode (ships.json `"wreck"`): each wreck's skeletal mesh (SK_*_Wreck, a bone a piece) cut
  into pieces in its hull's frame, the pirates' repainted in the pirates' colours; the pieces glow where they burn, cool
  and disintegrate as Chorus's do.
- **Death explosions** (`tools/explosions.py`): every ship explodes as Chorus's do (ships.json `"deathFx"`): its
  fighters' fireball (P_Explosion_Main: the 16 x 8 fireball flipbook, sparks streaking out, tumble sparks) with
  sub-explosions and sparks over the death tumble (P_Explosion_Sub, P_Explosion_Small_Sparks), the big ships' (over
  400 m) P_Explosion_Large_M, read from the Cascade systems' emitters (their baked curves) into particle emitters: the
  fireballs with their dark smoke, the sparks, the flying rock impostors and the explosions' light flashes.
- **A capital ship of your own** (`tools/capital.py`): Chorus's player capital ship (the PCLS, BP_Player_Ship_Capital) as
  the Spirit-class Capital Ship, sold in a lounge late in the game (rank 18, 25 million): 2500 armour mending by 125 a
  second (Chorus's 250 of 5000), slow to turn, on the Captured Warship's hull with its own braking flaps (its skeletal
  mesh: A_PlayerControlledLargeShip01_LoopBraking's pose laid over by the brake) and its own shop icon, with its own
  weapons and device as items: the PCLS Artillery (an automatic turret, a turret slot on each of its 14 artillery
  sockets), the PCLS Death Ray (a beam held on, a hit every 0.05 s on everything within 360 m of its line out to 21 km,
  overheating after 6.5 s for 6 s), the PCLS Broadside Barrage (homing missile salvos with a wide blast) and the PCLS
  Shield Overcharge (the remake's device 22: the shield full and nothing past it for 5 s, every 10 s). The remake fits its
  camera to the hull and shrinks it on the hangar's turntable (a hull over 150 m).
- **The Rift** (`tools/rift.py`): Chorus's rift vortex (SM_Rift_Vortex with M_PortalRift_2, Nimika's
  MI_PortalRift_2_LocAST_Outside, as a material `"rift"` block: its swirl, red centre, lightning flipbooks and clouds,
  added, the funnel heaving as Chorus's vertex shader moves it). In the Chorus systems a rift run looks like Chorus's Rift
  (the `encounters.json` rift entry's `"look"`): the Rift seen from inside at the run's centre (LocRFA's vortex in
  M_PortalRift_BOTTOM), Chorus's FTL portal opening between its stages, and the inner Rift's sky
  (T_Omen_InnerRift_Cubemap_Tex) while it lasts. The dormant Rift hangs over Nimika Prime (an orbit prop facing the
  station).
- **Chorus's way of fighting:** its fighters and boss hulls fight as Chorus's do (the remake's `"ai": "chorus"`, from its
  fighters' behaviour tree: fast attack runs, passes, breaks when you aim at them, retreats, and jumps back when left far
  behind), some carrying Chorus missile launchers.
- **Guilt** (`tools/npcs.py`): Chorus's invincible Faceless, skinned and breathing, hunts you now and then in Nimika
  Prime's and the Tarris Wormhole's orbits (npcships.json, from rank 10) with the remake's `"pursuer"` role: it can't be
  harmed, closes in at Chorus's stepped speeds, withers your hull up close and darkens the screen as it nears. Outrun it.
- **Nimika Prime's broken planet** (`tools/brokenplanet.py`): LocAST's destroyed planet (its six parts in their shared
  frame, its lava core glowing, a dozen loose fragments) hangs below Nimika Prime's orbit beside its own planet, its
  materials baked from M_Planet_Broken's and M_BrokenPlanet_Core's compiled base passes.
- **Wrecks:** Nimika Prime's, Stega Belt's and the Tarris Wormhole's wreck fields use the mod's own Chorus freighters and
  frigates as hulks.

Skies and planets were decoded from Chorus's compiled shaders (the exporter's `shaders`, its preshader for each
constant's parameter), not approximated: see the remake's docs/notes/mods-world.md "Chorus skies" / "Chorus planets".

## Tests

```
python3 -m unittest discover -s tests
```

They check the conversions on synthetic data and need no game files.
